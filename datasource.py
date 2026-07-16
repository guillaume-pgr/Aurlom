"""Couche d'abstraction unique pour alimenter le dashboard.

``get_dashboard_data(mode)`` renvoie TOUJOURS la même structure (celle de
demo_data.build()), que le template consomme sans se soucier du mode.

- mode 'demo' : renvoie exactement les données du mockup v4.
- mode 'real' : part de la même structure puis remplace les blocs calculables
  depuis la comptabilité (CA LTM, EBITDA LTM, séries mensuelles CA/EBITDA,
  P&L LTM par regroupement PCG). Les blocs non calculables (trésorerie,
  étudiants, campus, projections, covenants…) restent issus de la démo et sont
  signalés via ``demo_blocks`` / le drapeau ``demo`` des KPIs.
"""
from __future__ import annotations

import demo_data
import mapping
from db import init_db, last_sync, query

# Mois de la période LTM dans l'ordre d'affichage (juil. -> juin), aligné sur
# les libellés demo_data._L12 injectés dans les graphiques.
_LTM_MONTHS = [7, 8, 9, 10, 11, 12, 1, 2, 3, 4, 5, 6]

# Blocs non reconstituables depuis la comptabilité : ils restent en démo et
# portent un badge « démo » en mode réel.
_DEMO_BLOCKS_REAL = ["cash", "covenants", "etudiants", "campus", "previsionnel"]


# --- Helpers de formatage (français) -----------------------------------
def _fr_millions(value: float) -> str:
    """Millions avec 2 décimales et virgule (ex: 1404000 -> '1,40')."""
    return f"{value / 1_000_000:.2f}".replace(".", ",")


def _fr_pct(value: float) -> str:
    """Pourcentage à 1 décimale, virgule française (ex: 16.52 -> '16,5 %')."""
    return f"{value:.1f}".replace(".", ",") + " %"


# --- Lecture base (SQLite ou Turso, transparent) -----------------------
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


def _entries_by_month(entries: list[dict]) -> dict[int, list[dict]]:
    """Regroupe les écritures par mois pour les séries mensuelles."""
    buckets: dict[int, list[dict]] = {m: [] for m in _LTM_MONTHS}
    for e in entries:
        m = _month_of(e.get("period"))
        if m in buckets:
            buckets[m].append(e)
    return buckets


def _monthly_series(entries: list[dict], poste: str) -> list[float]:
    """Série mensuelle (k€) d'un poste agrégé, dans l'ordre LTM (juil. -> juin)."""
    buckets = _entries_by_month(entries)
    return [round(mapping.aggregate_pnl(buckets[m])[poste] / 1000, 1)
            for m in _LTM_MONTHS]


# --- Construction mode real -------------------------------------------
def _apply_real(data: dict) -> dict:
    entries = _load_entries()
    pnl = mapping.aggregate_pnl(entries)

    ca = pnl["ca"]
    ebitda = pnl["ebitda"]
    marge = (ebitda / ca * 100) if ca else 0.0

    # KPI 1 (CA LTM) et 2 (EBITDA LTM) : valeurs réelles. Pas de N-1 calculable
    # depuis la seule compta courante -> on retire les chips de comparaison.
    data["kpis"][0].update(val=_fr_millions(ca), sub="", chip="", demo=False)
    data["kpis"][1].update(val=_fr_millions(ebitda), sub=f"marge {_fr_pct(marge)}",
                           chip="", demo=False)
    # KPI 3 à 6 (trésorerie, emprunts, étudiants, créances) : non calculables.
    for i in (2, 3, 4, 5):
        data["kpis"][i]["demo"] = True

    # Séries mensuelles réelles ; le budget reste celui de la démo (non calculable).
    ca_m = _monthly_series(entries, "ca")
    eb_m = _monthly_series(entries, "ebitda")
    data["charts"]["ca_m"] = ca_m
    data["charts"]["eb_m"] = eb_m
    # Écart réalisé cumulé vs budget recalculé sur les valeurs réelles.
    data["charts"]["gap_ca"] = demo_data.gap_text(
        round(sum(ca_m)) - data["charts"]["budget_ca"])
    data["charts"]["gap_eb"] = demo_data.gap_text(
        round(sum(eb_m)) - data["charts"]["budget_eb"])

    # Tableau P&L LTM reconstruit depuis le mapping PCG. Le détail « métier »
    # de la démo (alternance/scolarité/pédagogique) n'est pas déductible du PCG :
    # on affiche donc les postes comptables agrégés.
    # 'val' en nombres bruts (k€) ; le formatage est fait par fmt() dans le template.
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
        {"label": "EBITDA", "pct": _fr_pct(marge), "val": ke(ebitda),
         "delta": "", "delta_cls": "", "cls": "tot"},
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
        data["meta"]["sync"] = (row["finished_at"] or row["started_at"] or "").replace("T", " ")

    # Footer : ce ne sont plus des données fictives (hors blocs démo).
    data["meta"]["footer"] = (
        "Source comptable : API fulll (dossier G2A) — P&L LTM calculé en temps réel. "
        "Blocs marqués « démo » : non disponibles depuis la comptabilité."
    )

    # Blocs restés en démo (badge affiché en mode real).
    data["demo_blocks"] = list(_DEMO_BLOCKS_REAL)
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
            data["demo_blocks"] = list(_DEMO_BLOCKS_REAL) + ["pnl"]
    return data
