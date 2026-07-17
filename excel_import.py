"""Import du fichier Excel en ligne de commande (équivalent de /admin/upload).

Usage :
    python excel_import.py donnees_dashboard_aurlom.xlsx            # valide + importe
    python excel_import.py donnees_dashboard_aurlom.xlsx --dry-run  # valide seulement
    python excel_import.py --rollback                               # annule le dernier import

En mode normal, le fichier est validé puis activé (le mode réel s'appuie
dessus). En --dry-run, on valide et on affiche le résumé SANS rien écrire.
"""
from __future__ import annotations

import argparse
import sys

import excel_source
import excel_store


def _print_diff(diff: dict) -> None:
    if diff.get("premier_import"):
        print("  (premier import — aucune donnée en place)")
    else:
        print(f"  date de mise à jour : {diff.get('date_maj_avant')} "
              f"-> {diff.get('date_maj_apres')}")
    for k in diff.get("kpis", []):
        marque = " *" if k["change"] else "  "
        print(f" {marque} {k['libelle']:16} {k['avant']:>14}  ->  {k['apres']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import Excel du dashboard Aurlom.")
    parser.add_argument("fichier", nargs="?", help="Chemin du classeur .xlsx")
    parser.add_argument("--dry-run", action="store_true",
                        help="Valider et afficher le résumé sans écrire en base.")
    parser.add_argument("--rollback", action="store_true",
                        help="Annuler le dernier import (réactiver le précédent).")
    args = parser.parse_args(argv)

    if args.rollback:
        restored = excel_store.rollback()
        if not restored:
            print("[ERREUR] Rien à annuler (un seul import ou aucun).")
            return 1
        print(f"[OK] Retour à l'import précédent : {restored.get('filename')} "
              f"(données au {restored.get('date_maj')}).")
        return 0

    if not args.fichier:
        parser.error("indiquez un fichier .xlsx (ou utilisez --rollback)")

    try:
        with open(args.fichier, "rb") as fh:
            content = fh.read()
    except OSError as exc:
        print(f"[ERREUR] Lecture impossible : {exc}")
        return 1

    # --- Validation ---
    try:
        dashboard, tables = excel_source.parse_and_validate(content)
    except excel_source.ExcelValidationError as exc:
        print(f"[ÉCHEC] {len(exc.errors)} erreur(s) de validation :")
        for e in exc.errors:
            print("  -", e)
        return 1

    volum = excel_source.volumetrie(tables)
    print(f"[OK] Fichier valide. Volumétrie : "
          f"{', '.join(f'{k}={v}' for k, v in volum.items())}")
    print("\nImpact (vs données en place) :")
    try:
        _print_diff(excel_store.compute_diff(dashboard))
    except Exception as exc:  # noqa: BLE001 - base éventuellement absente en dry-run
        print(f"  (comparaison indisponible : {type(exc).__name__})")

    if args.dry_run:
        print("\n[DRY-RUN] Aucune écriture effectuée.")
        return 0

    # --- Écriture ---
    try:
        new_id = excel_store.save_import(
            dashboard, filename=args.fichier,
            file_hash=excel_source.file_hash(content), volumetrie=volum, author="cli")
    except Exception as exc:  # noqa: BLE001
        print(f"[ERREUR] Écriture impossible : {type(exc).__name__} — {exc}")
        return 1

    print(f"\n[OK] Import #{new_id} activé — le mode réel affiche désormais "
          f"les données au {dashboard['meta']['maj']}.")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # pragma: no cover
        pass
    raise SystemExit(main())
