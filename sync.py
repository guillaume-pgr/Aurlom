"""Synchronisation : comptes + écritures de l'exercice en cours -> SQLite.

Exercice comptable Aurlom : 1er septembre -> 31 août. On synchronise donc
depuis septembre de l'exercice courant jusqu'au mois en cours.

Utilisable en CLI (``python sync.py``) ou via le bouton de l'UI (POST /sync).
"""
from __future__ import annotations

from datetime import datetime

import config
import db
from client_fulll import FulllClient


def _exercise_range(today: datetime | None = None) -> tuple[str, str]:
    """Période de l'exercice en cours au format API (mm/yyyy).

    L'exercice démarre en septembre : si on est en sept.-déc., il a commencé
    en septembre de l'année courante ; sinon (janv.-août) l'année précédente.
    """
    now = today or datetime.now()
    start_year = now.year if now.month >= 9 else now.year - 1
    period_start = f"09/{start_year}"
    period_end = now.strftime("%m/%Y")
    return period_start, period_end


def _norm_account(a: dict) -> dict:
    return {
        "id": str(a.get("id") or a.get("number")),
        "number": a.get("number"),
        "label": a.get("label"),
        "type": a.get("type"),
        "debit": _to_float(a.get("debit")),
        "credit": _to_float(a.get("credit")),
        "balance": _to_float(a.get("balance")),
        "status": a.get("status"),
    }


def _norm_entry(e: dict) -> dict:
    return {
        "lineid": str(e.get("lineid")),
        "header": e.get("header"),
        "number": e.get("number"),
        "book": e.get("book"),
        "period": e.get("period"),
        "day": e.get("day"),
        "account": e.get("account"),
        "label": e.get("label"),
        "debit": _to_float(e.get("debit")),
        "credit": _to_float(e.get("credit")),
        "letter": e.get("letter"),
        "due_date": e.get("due_date"),
        "account_type": e.get("account_type"),
    }


def _to_float(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def run_sync() -> dict:
    """Lance une synchro complète et journalise le résultat.

    Retourne un dict récapitulatif (status, counts, message).
    """
    db.init_db()
    period_start, period_end = _exercise_range()
    started = datetime.now().isoformat(timespec="seconds")
    sync_id = db.start_sync(started, period_start, period_end)

    try:
        client = FulllClient()

        accounts = [_norm_account(a) for a in client.get_accounts()]
        n_accounts = db.upsert_accounts(accounts)

        entries = [_norm_entry(e) for e in client.get_entries(period_start, period_end)]
        n_entries = db.upsert_entries(entries)

        db.finish_sync(
            sync_id,
            datetime.now().isoformat(timespec="seconds"),
            "ok",
            n_accounts,
            n_entries,
            message="Synchronisation réussie.",
        )
        return {"status": "ok", "accounts": n_accounts, "entries": n_entries,
                "period": f"{period_start} - {period_end}"}
    except Exception as exc:  # noqa: BLE001 - on journalise toute erreur
        db.finish_sync(
            sync_id,
            datetime.now().isoformat(timespec="seconds"),
            "error",
            0,
            0,
            message=f"{type(exc).__name__}: {exc}",
        )
        return {"status": "error", "message": f"{type(exc).__name__}: {exc}"}


if __name__ == "__main__":
    # Console Windows : forcer l'UTF-8 pour les caractères accentués.
    try:
        import sys
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # pragma: no cover
        pass
    result = run_sync()
    if result["status"] == "ok":
        print(f"[OK] Comptes: {result['accounts']} | "
              f"Écritures: {result['entries']} | Période: {result['period']}")
    else:
        print(f"[ERREUR] {result['message']}")
        raise SystemExit(1)
