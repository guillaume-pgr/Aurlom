"""Script one-shot : (re)crée le schéma des tables sur la base Turso.

À lancer une seule fois après avoir créé la base Turso, avec un fichier ``.env``
(ou des variables d'environnement) contenant au minimum :

    TURSO_DATABASE_URL=libsql://<votre-base>.turso.io
    TURSO_AUTH_TOKEN=<votre-token>

Usage :
    python migrate_to_turso.py

Le script s'appuie sur le même schéma que l'application (db.SCHEMA_STATEMENTS),
donc SQLite local et Turso restent parfaitement identiques.
"""
from __future__ import annotations

import sys

import config
import db


def main() -> int:
    if not config.TURSO_DATABASE_URL:
        print(
            "[ERREUR] TURSO_DATABASE_URL n'est pas défini.\n"
            "Renseignez-le (ainsi que TURSO_AUTH_TOKEN) dans votre .env ou vos "
            "variables d'environnement avant de lancer la migration."
        )
        return 1

    print(f"Connexion à Turso : {config.TURSO_DATABASE_URL}")
    # init_db() construit le backend Turso puis exécute SCHEMA_STATEMENTS.
    db.init_db()

    # Vérification : on liste les tables créées.
    tables = db.query(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    names = ", ".join(t["name"] for t in tables) or "(aucune)"
    print(f"Tables présentes : {names}")
    print("[OK] Schéma Turso prêt.")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # pragma: no cover
        pass
    raise SystemExit(main())
