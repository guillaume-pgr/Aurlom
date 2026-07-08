"""Couche d'abstraction unique pour alimenter le dashboard.

``get_dashboard_data(mode)`` renvoie TOUJOURS la même structure (celle de
demo_data.build()), que le template consomme sans se soucier du mode.

- mode 'demo' : renvoie exactement les données du mockup.
- mode 'real' : part de la même structure puis remplace les blocs calculables
  depuis SQLite (CA YTD, EBITDA YTD, CA mensuel réel, P&L YTD par regroupement
  PCG). Les blocs non calculables (trésorerie, étudiants, prévisionnel,
  covenants…) restent issus de la démo et sont signalés via ``demo_blocks`` /
  le drapeau ``demo`` des KPIs.
"""
from __future__ import annotations

import demo_data
import mapping
from db import init_db, last_sync, query

# Mois de l'exercice dans l'ordre d'affichage du graphe P&L (sept -> juin).
_EXERCISE_MONTHS = [9, 10, 11, 12, 1, 2, 3, 4, 5, 6]


# --- Helpers de formatage (français) -----------------------------------
def _fr_millions(value: float) -> str:
    """Millions avec 2 décimales et virgule (ex: 1404000 -> '1,40')."""
    return f"{value / 1_000_000:.2f}".replace(".", ",")


# --- Lecture SQLite ----------------------------------------------------
def _load_entries() -> list[dict]:
    init_db()
    return query("SELECT account, debit, credit, period FROM entries")


def _month_of(period: str | None) -> int | None:
    """Extrait le numéro de mois d'un champ 'period' (formats mm/yyyy, yyyy-mm…)."""
    if not period:
        return None
    p = str(period)
    for sep in ("/", "-"):
        if sep in p:
            a, _, b = p.partition(sep)
            # mm/yyyy -> a=mois ; yyyy-mm -> b=mois
            cand = a if len(a) <= 2 else b
            try:
                m = int(cand)
                if 1 <= m <= 12:
                    return m
            except ValueError:
                return None
    return None


def _monthly_ca(entries: list[dict]) -> list[float]:
    """CA mensuel réel (k€) dans l'ordre de l'exercice (sept -> juin)."""
    sums = {m: 0.0 for m in _EXERCISE_MONTHS}
    for e in entries:
        poste, nature = mapping.classify(e.get("account"))
        if poste != "ca":
            continue
        m = _month_of(e.get("period"))
        if m in sums:
            sums[m] += mapping.entry_amount(nature, e.get("debit"), e.get("credit"))
    return [round(sums[m] / 1000, 1) for m in _EXERCISE_MONTHS]


# --- Construction mode real -------------------------------------------
def _apply_real(data: dict) -> dict:
    entries = _load_entries()
    pnl = mapping.aggregate_pnl(entries)

    ca = pnl["ca"]
    ebitda = pnl["ebitda"]
    marge = (ebitda / ca * 100) if ca else 0.0

    # KPI 1 (CA) et 2 (EBITDA) : valeurs réelles, pas de delta N-1 calculable.
    data["kpis"][0].update(val=_fr_millions(ca), chip="", demo=False)
    data["kpis"][1].update(
        val=_fr_millions(ebitda),
        sub=f"marge {marge:.1f}".replace(".", ",") + " %",
        chip="", demo=False,
    )
    # KPI 3, 4, 5 : non calculables depuis la compta -> démo.
    for i in (2, 3, 4):
        data["kpis"][i]["demo"] = True

    # Graphe CA mensuel : la série 'Réel' devient réelle ; budget/N-1 restent démo.
    data["charts"]["pnl"]["reel"] = _monthly_ca(entries)

    # Tableau P&L YTD reconstruit depuis le mapping PCG.
    # 'val' en nombres bruts (k€) ; le formatage (parenthèses/zéro) est fait
    # par fmt() dans le template, comme en mode démo.
    def ke(value: float) -> int:
        return int(round(value / 1000))

    data["pnl_note"] = "k€ · calculé depuis fulll (regroupement PCG)"
    data["pnl_table"] = [
        {"label": "Chiffre d'affaires", "val": ke(ca),
         "delta": "", "delta_cls": "", "cls": ""},
        {"label": "Achats", "val": ke(-pnl["achats"]),
         "delta": "", "delta_cls": "", "cls": ""},
        {"label": "Services extérieurs", "val": ke(-pnl["services_ext"]),
         "delta": "", "delta_cls": "", "cls": ""},
        {"label": "Impôts et taxes", "val": ke(-pnl["impots_taxes"]),
         "delta": "", "delta_cls": "", "cls": ""},
        {"label": "Masse salariale", "val": ke(-pnl["masse_salariale"]),
         "delta": "", "delta_cls": "", "cls": ""},
        {"label": "Autres charges de gestion", "val": ke(-pnl["autres_charges"]),
         "delta": "", "delta_cls": "", "cls": ""},
        {"label": "EBITDA", "pct": f"{marge:.1f}".replace(".", ",") + " %",
         "val": ke(ebitda), "delta": "", "delta_cls": "", "cls": "tot"},
        {"label": "Dotations amortissements", "val": ke(-pnl["dotations"]),
         "delta": "", "delta_cls": "", "cls": ""},
        {"label": "Résultat financier", "val": ke(pnl["resultat_financier"]),
         "delta": "", "delta_cls": "", "cls": ""},
        {"label": "Résultat exceptionnel", "val": ke(pnl["resultat_except"]),
         "delta": "", "delta_cls": "", "cls": ""},
        {"label": "Résultat net", "val": ke(pnl["resultat_net"]),
         "delta": "", "delta_cls": "", "cls": "tot"},
    ]

    # Info de synchro pour la barre latérale.
    row = last_sync()
    if row is not None:
        data["meta"]["sync_fulll"] = (row["finished_at"] or row["started_at"] or "").replace("T", " ")
        data["meta"]["sync_status"] = row["status"]

    # Footer : ce ne sont plus des données fictives (hors blocs démo).
    data["meta"]["footer"] = (
        "Source comptable : API fulll (dossier G2A) — P&L calculé en temps réel. "
        "Blocs marqués « démo » : non disponibles depuis la comptabilité."
    )

    # Blocs restés en démo (badge affiché en mode real).
    data["demo_blocks"] = ["alerts", "cash", "covenants", "echeances",
                           "etudiants", "previsionnel"]
    return data


# --- API publique ------------------------------------------------------
def get_dashboard_data(mode: str = "demo") -> dict:
    data = demo_data.build()
    # Drapeau démo par défaut sur chaque KPI (utile au template en mode real).
    for k in data["kpis"]:
        k.setdefault("demo", False)

    if mode == "real":
        try:
            return _apply_real(data)
        except Exception as exc:  # noqa: BLE001
            # En cas d'échec (base vide, etc.), on retombe sur la démo + message.
            data["meta"]["real_error"] = f"{type(exc).__name__}: {exc}"
            data["demo_blocks"] = ["alerts", "cash", "covenants", "echeances",
                                   "etudiants", "previsionnel", "pnl"]
    return data
