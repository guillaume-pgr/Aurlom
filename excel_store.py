"""Stockage des données Excel importées (Turso en prod, SQLite en dev).

Le dashboard dérivé par excel_source est stocké **versionné** dans la table
``import_history`` : chaque import ajoute une ligne, et le drapeau ``active``
désigne la version servie par le mode réel.

Pourquoi un payload JSON versionné plutôt que 15 tables relationnelles :
- l'activation est **atomique** (un seul UPDATE bascule tout le dashboard) :
  jamais de dashboard à moitié importé, même si l'écriture est interrompue ;
- le **rollback** consiste à réactiver la version précédente, sans réécrire ni
  supprimer quoi que ce soit (l'historique reste auditable) ;
- la lecture ne coûte **qu'une requête**, ce qui compte en serverless où chaque
  aller-retour Turso est payé à froid.

Le classeur reste la source de vérité : la base n'en est qu'une projection.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --- Écriture ---------------------------------------------------------------
def save_import(dashboard: dict, *, filename: str, file_hash: str,
                volumetrie: dict, author: str = "") -> int:
    """Enregistre un import et l'active, en désactivant l'précédent.

    L'opération est transactionnelle : l'insertion de la nouvelle version et la
    bascule du drapeau ``active`` partent dans un même batch, donc le dashboard
    ne peut jamais se retrouver sans version active ni avec deux.

    Retourne l'id de la version créée.
    """
    payload = json.dumps(dashboard, ensure_ascii=False)
    date_maj = (dashboard.get("meta") or {}).get("maj", "")

    # Insertion + activation dans UNE transaction : à aucun moment le dashboard
    # ne peut être sans version active, ni en avoir deux. L'INSERT pose déjà
    # active=1 et l'UPDATE désactive les autres, donc même une lecture
    # concurrente voit toujours exactement une version active.
    db.batch([
        ("""
         INSERT INTO import_history
            (imported_at, filename, file_hash, date_maj, volumetrie, payload, active, author)
         VALUES (?, ?, ?, ?, ?, ?, 1, ?)
         """,
         [_now(), filename, file_hash, date_maj,
          json.dumps(volumetrie, ensure_ascii=False), payload, author]),
        ("UPDATE import_history SET active = 0 "
         "WHERE id <> (SELECT MAX(id) FROM import_history)", None),
    ])
    rows = db.query("SELECT MAX(id) AS id FROM import_history")
    return int(rows[0]["id"])


def rollback() -> dict | None:
    """Réactive la version précédant l'active (annulation du dernier import).

    Retourne la version réactivée, ou None s'il n'y a rien à annuler.
    """
    versions = db.query(
        "SELECT id, imported_at, filename, date_maj, active "
        "FROM import_history ORDER BY id DESC LIMIT 2"
    )
    if len(versions) < 2:
        return None
    courante, precedente = versions[0], versions[1]
    if not courante["active"]:
        # L'état actif n'est pas la dernière version : on ne devine pas, on sort.
        return None
    # Bascule atomique vers la version précédente (rien n'est supprimé).
    db.batch([
        ("UPDATE import_history SET active = CASE WHEN id = ? THEN 1 ELSE 0 END",
         [precedente["id"]]),
    ])
    return precedente


# --- Lecture ----------------------------------------------------------------
def load_active() -> dict | None:
    """Retourne le dashboard de la version active, ou None si aucun import."""
    rows = db.query(
        "SELECT payload FROM import_history WHERE active = 1 ORDER BY id DESC LIMIT 1"
    )
    if not rows:
        return None
    try:
        return json.loads(rows[0]["payload"])
    except (json.JSONDecodeError, TypeError):
        # Payload corrompu : on préfère le fallback démo à un dashboard cassé.
        return None


def active_info() -> dict | None:
    """Métadonnées de la version active (sans le payload, plus léger)."""
    rows = db.query(
        "SELECT id, imported_at, filename, file_hash, date_maj, volumetrie, author "
        "FROM import_history WHERE active = 1 ORDER BY id DESC LIMIT 1"
    )
    return rows[0] if rows else None


def history(limit: int = 10) -> list[dict]:
    """Derniers imports, du plus récent au plus ancien."""
    return db.query(
        "SELECT id, imported_at, filename, file_hash, date_maj, volumetrie, active, author "
        "FROM import_history ORDER BY id DESC LIMIT ?",
        [limit],
    )


def has_data() -> bool:
    """Y a-t-il une version active exploitable ?"""
    return load_active() is not None


# --- Staging (upload -> validation -> diff -> confirmation) ------------------
def compute_diff(dashboard: dict) -> dict:
    """Compare un dashboard candidat à la version active (résumé lisible).

    Ne compare que quelques indicateurs saillants : le but est de donner à
    l'utilisateur de quoi décider en connaissance de cause avant d'écraser.
    """
    ancien = load_active()

    def kpi(d: dict, i: int) -> str:
        try:
            k = d["kpis"][i]
            return f"{k['val']} {k.get('unit', '')}".strip()
        except (KeyError, IndexError, TypeError):
            return "—"

    lignes = []
    labels = ["CA LTM", "EBITDA LTM", "Trésorerie", "Emprunts", "Étudiants", "Créances OPCO"]
    for i, lbl in enumerate(labels):
        av = kpi(ancien, i) if ancien else "—"
        ap = kpi(dashboard, i)
        lignes.append({"libelle": lbl, "avant": av, "apres": ap,
                       "change": av != ap})
    return {
        "premier_import": ancien is None,
        "date_maj_avant": (ancien or {}).get("meta", {}).get("maj", "—") if ancien else "—",
        "date_maj_apres": dashboard.get("meta", {}).get("maj", "—"),
        "kpis": lignes,
        "nb_campus": len(dashboard.get("campus", [])),
    }


def stage_import(dashboard: dict, *, token: str, filename: str, file_hash: str,
                 volumetrie: dict, diff: dict) -> None:
    """Enregistre un import validé en attente de confirmation."""
    db.execute("DELETE FROM import_staging WHERE token = ?", [token])
    db.execute(
        """
        INSERT INTO import_staging
            (token, created_at, filename, file_hash, date_maj, volumetrie, payload, diff)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [token, _now(), filename, file_hash,
         (dashboard.get("meta") or {}).get("maj", ""),
         json.dumps(volumetrie, ensure_ascii=False),
         json.dumps(dashboard, ensure_ascii=False),
         json.dumps(diff, ensure_ascii=False)],
    )


def get_staged(token: str) -> dict | None:
    """Relit un import en attente (payload + métadonnées) par son token."""
    rows = db.query("SELECT * FROM import_staging WHERE token = ?", [token])
    if not rows:
        return None
    r = rows[0]
    return {
        "filename": r["filename"],
        "file_hash": r["file_hash"],
        "date_maj": r["date_maj"],
        "volumetrie": json.loads(r["volumetrie"]) if r["volumetrie"] else {},
        "dashboard": json.loads(r["payload"]),
        "diff": json.loads(r["diff"]) if r["diff"] else {},
    }


def clear_staged(token: str) -> None:
    db.execute("DELETE FROM import_staging WHERE token = ?", [token])
