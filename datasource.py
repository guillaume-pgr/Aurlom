"""Couche d'abstraction unique pour alimenter le dashboard.

``get_dashboard_data(mode)`` renvoie TOUJOURS la même structure (celle de
demo_data.build()), que le template consomme sans se soucier du mode.

- mode 'demo' : données du mockup v4 (demo_data.py).
- mode 'real' : données du **fichier Excel importé**, lues depuis la base
  (table import_history, version active). Le classeur est l'unique source du
  mode réel : tous les agrégats (cumuls, marges, croissances…) ont été calculés
  à l'import par excel_source.py.

Si aucun import n'a encore été effectué (base vide), on retombe proprement sur
les données démo, l'intégralité des blocs étant alors marquée « démo ».
"""
from __future__ import annotations

import demo_data

# Blocs marqués « démo » quand le mode réel n'a pas (encore) de données.
_ALL_BLOCKS = ["pnl", "cash", "covenants", "etudiants", "campus", "previsionnel"]


def _fallback_demo(data: dict, message: str) -> dict:
    """Mode réel sans données exploitables -> démo intégralement badgée."""
    data["meta"]["real_error"] = message
    data["demo_blocks"] = list(_ALL_BLOCKS)
    for k in data["kpis"]:
        k["demo"] = True
    return data


def get_dashboard_data(mode: str = "demo") -> dict:
    data = demo_data.build()
    # Drapeau démo par défaut sur chaque KPI (utile au template en mode real).
    for k in data["kpis"]:
        k.setdefault("demo", False)

    if mode != "real":
        return data

    # --- Mode réel : 100 % piloté par le dernier import Excel ---
    try:
        import excel_store

        dashboard = excel_store.load_active()
    except Exception as exc:  # noqa: BLE001 - base injoignable, schéma absent…
        return _fallback_demo(
            data, f"base indisponible ({type(exc).__name__}: {exc})")

    if not dashboard:
        return _fallback_demo(
            data, "aucun fichier Excel importé — importez-en un via /admin/upload")

    # Le payload stocké a exactement la structure attendue par le template :
    # il a été produit par excel_source._build_dashboard() à l'import.
    for k in dashboard.get("kpis", []):
        k.setdefault("demo", False)
    dashboard.setdefault("demo_blocks", [])
    return dashboard
