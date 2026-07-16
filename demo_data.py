"""Données de démonstration = valeurs EXACTES du mockup v4.

Source : ``dashboard_aurlom_mockup_v4_responsive.html`` (cible visuelle).

Ce module est l'unique source du mode ``demo``. La structure est volontairement
« data-driven » : le template Jinja2 se contente d'itérer sur ces objets et le
JS ne reçoit que du JSON, donc le mode ``real`` réutilise exactement le même
gabarit en ne remplaçant que les blocs calculables (cf. datasource.py).

Aucune valeur n'est codée en dur ailleurs que dans ce fichier : les ratios de
reconstitution du P&L par campus et la saisonnalité (qui vivaient dans le JS du
mockup) sont remontés ici et pré-calculés côté Python.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

# Palette (identique au mockup / charte Aurlom).
VIOLET = "#5B2D8E"        # 'V' dans le mockup
VIOLET_SOFT = "#C9B8E4"   # 'VS'
GRAY = "#C6C1D2"          # 'GRAY'


# --- Helpers de calcul/formatage ---------------------------------------
def _r(x: float) -> int:
    """Arrondi « half-up », identique à Math.round() du mockup.

    (round() de Python fait un arrondi « au pair le plus proche », ce qui
    donnerait des écarts d'une unité sur certaines valeurs.)
    """
    return int(Decimal(str(x)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _pct(value: float) -> str:
    """Pourcentage à 1 décimale, virgule française — équivaut à pctf() du mockup."""
    return f"{value * 100:.1f}".replace(".", ",") + " %"


def _sep(n: int) -> str:
    """Séparateur de milliers = espace (comme le fmt() du template)."""
    return f"{n:,}".replace(",", " ")


def gap_text(diff: int) -> str:
    """Écart réalisé/budget affiché au-dessus de la flèche à double pointe.

    Positif -> « +340 k€ » ; négatif -> « (340) k€ » (convention du mockup).
    Public : datasource.py le réutilise pour recalculer l'écart en mode réel.
    """
    if diff > 0:
        return f"+{_sep(diff)} k€"
    if diff < 0:
        return f"({_sep(abs(diff))}) k€"
    return "- k€"


def _cum(values: list[float]) -> list[float]:
    """Cumul progressif (équivaut à cum() du mockup)."""
    out, total = [], 0
    for v in values:
        total += v
        out.append(total)
    return out


# --- Vue globale : séries mensuelles LTM (juil. 25 -> juin 26) ---------
_L12 = ["juil.25", "août 25", "sept.25", "oct.25", "nov.25", "déc.25",
        "janv.26", "févr.26", "mars 26", "avr.26", "mai 26", "juin 26"]
_CA_M = [780, 590, 2450, 2210, 1580, 1490, 1980, 1760, 1690, 1720, 1830, 1710]
_EB_M = [-160, -280, 780, 560, 240, 190, 420, 310, 280, 300, 340, 290]
_BUDGET_CA = 19450
_BUDGET_EB = 3150


# --- Campus ------------------------------------------------------------
# Saisonnalité du CA sur les 12 mois LTM (somme ≈ 1). Vivait dans le JS du
# mockup (const seas) : remontée ici pour garder le template sans chiffres.
_CAMPUS_SEAS = [.041, .031, .133, .120, .086, .081, .107, .095, .092, .093, .099, .092]

# Ratios de reconstitution du P&L d'un campus à partir de son CA (idem : ex-JS).
_PNL_RATIOS = {
    "alternance": .536,
    "initiale": .377,
    "pedago": .343,
    "marketing": .08,
    "autres": .055,
}

# Couleurs des barres « étudiants par filière » d'un campus (6 filières).
CAMPUS_FIL_COLORS = [VIOLET, VIOLET, VIOLET, VIOLET, VIOLET_SOFT, VIOLET_SOFT]

# Données brutes des 8 campus (ordre d'affichage conservé).
#   et = étudiants · cap = capacité · ca/eb en k€ · alt = % alternance
#   classe = effectif moyen/classe · reu = % réussite BTS · att = % attrition
#   nps = satisfaction · loyer (k€) · m2 · prof = coût moyen chargé (k€)
_CAMPUS_BASE: dict[str, dict] = {
    "roquette": {
        "nom": "Paris — Roquette", "court": "Roquette",
        "adr": "48 rue de la Roquette, 75011",
        "et": 780, "cap": 850, "ca": 5515, "eb": 1255, "alt": 52,
        "classe": 20, "reu": 96, "att": 3.8, "nps": 64,
        "loyer": 610, "m2": 1450, "prof": 61,
        "fil": {"BTS MCO": 148, "BTS NDRC": 132, "BTS CG": 96, "BTS CI": 88,
                "Prépas": 196, "Autres": 120},
    },
    "parmentier": {
        "nom": "Paris — Parmentier", "court": "Parmentier",
        "adr": "16 avenue Parmentier, 75011",
        "et": 420, "cap": 500, "ca": 2955, "eb": 530, "alt": 55,
        "classe": 19, "reu": 95, "att": 4.2, "nps": 61,
        "loyer": 340, "m2": 820, "prof": 59,
        "fil": {"BTS MCO": 82, "BTS NDRC": 74, "BTS CG": 52, "BTS CI": 46,
                "Prépas": 98, "Autres": 68},
    },
    "sentier": {
        "nom": "Paris — Sentier", "court": "Sentier",
        "adr": "quartier Sentier, 75002",
        "et": 310, "cap": 380, "ca": 2180, "eb": 345, "alt": 58,
        "classe": 18, "reu": 94, "att": 4.5, "nps": 59,
        "loyer": 295, "m2": 610, "prof": 58,
        "fil": {"BTS MCO": 60, "BTS NDRC": 56, "BTS CG": 38, "BTS CI": 34,
                "Prépas": 74, "Autres": 48},
    },
    "jaures": {
        "nom": "Paris — Jaurès", "court": "Jaurès",
        "adr": "118 avenue Jean-Jaurès, 75019",
        "et": 360, "cap": 450, "ca": 2535, "eb": 425, "alt": 56,
        "classe": 19, "reu": 93, "att": 4.9, "nps": 58,
        "loyer": 285, "m2": 740, "prof": 58,
        "fil": {"BTS MCO": 70, "BTS NDRC": 64, "BTS CG": 44, "BTS CI": 40,
                "Prépas": 86, "Autres": 56},
    },
    "belair": {
        "nom": "Paris — Bel-Air", "court": "Bel-Air",
        "adr": "quartier Bel-Air, 75012",
        "et": 290, "cap": 350, "ca": 2040, "eb": 300, "alt": 54,
        "classe": 18, "reu": 94, "att": 4.4, "nps": 60,
        "loyer": 250, "m2": 560, "prof": 57,
        "fil": {"BTS MCO": 56, "BTS NDRC": 52, "BTS CG": 36, "BTS CI": 32,
                "Prépas": 68, "Autres": 46},
    },
    "boulogne": {
        "nom": "Boulogne", "court": "Boulogne",
        "adr": "59 rue de Billancourt, 92100",
        "et": 240, "cap": 320, "ca": 1690, "eb": 195, "alt": 51,
        "classe": 17, "reu": 92, "att": 5.2, "nps": 57,
        "loyer": 230, "m2": 520, "prof": 56,
        "fil": {"BTS MCO": 46, "BTS NDRC": 42, "BTS CG": 30, "BTS CI": 26,
                "Prépas": 58, "Autres": 38},
    },
    "lille": {
        "nom": "Lille", "court": "Lille",
        "adr": "centre-ville, Lille",
        "et": 220, "cap": 300, "ca": 1545, "eb": 135, "alt": 49,
        "classe": 16, "reu": 91, "att": 5.8, "nps": 55,
        "loyer": 175, "m2": 480, "prof": 54,
        "fil": {"BTS MCO": 42, "BTS NDRC": 38, "BTS CG": 28, "BTS CI": 24,
                "Prépas": 52, "Autres": 36},
    },
    "nice": {
        "nom": "Nice", "court": "Nice",
        "adr": "ICONIC, gare de Nice",
        "et": 190, "cap": 260, "ca": 1330, "eb": 85, "alt": 47,
        "classe": 15, "reu": 90, "att": 6.1, "nps": 54,
        "loyer": 168, "m2": 430, "prof": 54,
        "fil": {"BTS MCO": 36, "BTS NDRC": 32, "BTS CG": 24, "BTS CI": 20,
                "Prépas": 46, "Autres": 32},
    },
}


def _campus_pnl(c: dict) -> list[dict]:
    """Reconstitue le P&L LTM d'un campus depuis son CA et son EBITDA.

    Reprend à l'identique la fonction pnlCampus() du mockup, mais côté Python.
    'val' reste un nombre brut (k€) : le formatage (parenthèses) est fait au
    rendu, comme partout ailleurs.
    """
    ca, eb = c["ca"], c["eb"]
    r = _PNL_RATIOS
    alt = _r(ca * r["alternance"])
    init = _r(ca * r["initiale"])
    stages = ca - alt - init
    ped = _r(ca * r["pedago"])
    marge_brute = ca - ped
    mkt = _r(ca * r["marketing"])
    autres = _r(ca * r["autres"])
    # La masse salariale est le solde : elle absorbe l'écart jusqu'à l'EBITDA.
    masse = marge_brute - eb - c["loyer"] - mkt - autres
    return [
        {"label": "Chiffre d'affaires", "val": ca, "cls": ""},
        {"label": "dont alternance (OPCO)", "val": alt, "cls": "sub"},
        {"label": "dont scolarité initiale", "val": init, "cls": "sub"},
        {"label": "dont stages & prépas", "val": stages, "cls": "sub"},
        {"label": "Coûts pédagogiques", "val": -ped, "cls": ""},
        {"label": "Marge brute", "val": marge_brute, "cls": "tot",
         "pct": _pct(marge_brute / ca)},
        {"label": "Masse salariale support", "val": -masse, "cls": ""},
        {"label": "Loyers", "val": -c["loyer"], "cls": ""},
        {"label": "Marketing & admissions", "val": -mkt, "cls": ""},
        {"label": "Autres opex", "val": -autres, "cls": ""},
        {"label": "EBITDA", "val": eb, "cls": "tot", "pct": _pct(eb / ca)},
    ]


def _build_campus() -> list[dict]:
    """Enrichit chaque campus des valeurs dérivées (pré-calculées côté serveur).

    Renvoie une LISTE (et non un dict) et éclate les filières en deux listes
    parallèles : le filtre ``tojson`` de Jinja2 trie les clés des dictionnaires
    (policy ``sort_keys=True``), ce qui casserait l'ordre d'affichage des campus
    et des filières. Les listes, elles, conservent leur ordre à la sérialisation.
    """
    out: list[dict] = []
    for key, base in _CAMPUS_BASE.items():
        c = {k: v for k, v in base.items() if k != "fil"}
        c["key"] = key
        # Filières : listes parallèles (ordre d'affichage garanti).
        c["fil_labels"] = list(base["fil"].keys())
        c["fil_data"] = list(base["fil"].values())
        # CA mensuel du campus = CA LTM ventilé par la saisonnalité.
        c["ca_m"] = [_r(c["ca"] * p) for p in _CAMPUS_SEAS]
        c["fill"] = _r(c["et"] / c["cap"] * 100)          # taux de remplissage
        c["alternants"] = _r(c["et"] * c["alt"] / 100)    # effectif en alternance
        c["marge"] = _pct(c["eb"] / c["ca"])              # marge d'EBITDA
        c["pnl"] = _campus_pnl(c)
        out.append(c)
    return out


# --- Projections -------------------------------------------------------
_F12 = ["juil.26", "août 26", "sept.26", "oct.26", "nov.26", "déc.26",
        "janv.27", "févr.27", "mars 27", "avr.27", "mai 27", "juin 27"]


def build() -> dict:
    """Retourne une copie neuve du jeu de données démo (structure v4)."""
    return {
        # --- En-tête & barre latérale ---------------------------------
        "meta": {
            "titre": "Vue globale",
            "exercice": "2025-26",
            "ltm": "juil. 25 → juin 26",
            "maj": "02/07/2026",
            "sync": "02/07/2026",
            "footer": "Données fictives utilisées pour la version démo",
        },

        # --- Bande des 6 KPIs (vue globale) ---------------------------
        "kpis": [
            {"lbl": "Chiffre d'affaires LTM", "val": "19,79", "unit": "M€",
             "sub": "vs LTM N-1", "chip": "+9,2 %", "chip_cls": "up"},
            {"lbl": "EBITDA LTM", "val": "3,27", "unit": "M€",
             "sub": "marge 16,5 %", "chip": "+13,5 %", "chip_cls": "up"},
            {"lbl": "Trésorerie brute", "val": "2,45", "unit": "M€",
             "sub": "vs moy. 12M", "chip": "+0,3 M€", "chip_cls": "up"},
            {"lbl": "Emprunts", "val": "8,40", "unit": "M€",
             "sub": "vs N-1", "chip": "(0,9) M€", "chip_cls": "up"},
            {"lbl": "Étudiants inscrits", "val": "2 810", "unit": "",
             "sub": "vs N-1", "chip": "+6,4 %", "chip_cls": "up"},
            {"lbl": "Créances OPCO", "val": "1,92", "unit": "M€",
             "sub": "DSO 74 j", "chip": "+9 j", "chip_cls": "warn"},
        ],

        # --- Tableau P&L LTM synthétique ------------------------------
        # 'val' en nombres bruts (k€) : le formatage est fait par le filtre
        # fmt() du template (négatifs entre parenthèses, zéro '-').
        "pnl_note": "k€ · cumulé LTM vs budget",
        "pnl_table": [
            {"label": "Chiffre d'affaires", "val": 19790,
             "delta": "+9,2 %", "delta_cls": "d-up", "cls": ""},
            {"label": "dont alternance (OPCO)", "val": 10610,
             "delta": "+12,1 %", "delta_cls": "d-up", "cls": "sub"},
            {"label": "dont scolarité initiale", "val": 7450,
             "delta": "+5,8 %", "delta_cls": "d-up", "cls": "sub"},
            {"label": "dont stages & prépas", "val": 1730,
             "delta": "+3,4 %", "delta_cls": "d-up", "cls": "sub"},
            {"label": "Coûts pédagogiques", "val": -6780,
             "delta": "+10,4 %", "delta_cls": "d-down", "cls": ""},
            {"label": "Marge brute", "pct": "65,7 %", "val": 13010,
             "delta": "+8,6 %", "delta_cls": "d-up", "cls": "tot"},
            {"label": "Masse salariale support", "val": -4320,
             "delta": "+6,1 %", "delta_cls": "", "cls": ""},
            {"label": "Loyers campus", "val": -2810,
             "delta": "+2,9 %", "delta_cls": "", "cls": ""},
            {"label": "Marketing & admissions", "val": -1590,
             "delta": "+18,2 %", "delta_cls": "d-down", "cls": ""},
            {"label": "Autres opex", "val": -1020,
             "delta": "+4,0 %", "delta_cls": "", "cls": ""},
            {"label": "EBITDA", "pct": "16,5 %", "val": 3270,
             "delta": "+13,5 %", "delta_cls": "d-up", "cls": "tot"},
        ],

        # --- Covenants LBO --------------------------------------------
        # status : 'ok' (pastille verte) | 'ko' (pastille rouge).
        "covenants": [
            {"name": "Levier net (DN/EBITDA)", "value": "1,8×",
             "rule": "doit être < 2,0×", "status": "ok"},
            {"name": "DSCR (CF libre / service dette)", "value": "1,6×",
             "rule": "doit être > 1,0×", "status": "ok"},
        ],

        # --- Prochaines échéances LBO ---------------------------------
        # amount = échéance monétaire ; à défaut doc = livrable non monétaire.
        "echeances": [
            {"label": "Reporting T2 2026 (J+60)", "date": "31/08", "doc": True},
            {"label": "Attestation ratios 30/06/2026", "date": "15/09", "doc": True},
            {"label": "Demande waiver capex", "date": "30/09", "doc": True},
            {"label": "Service dette T3", "date": "30/09", "amount": "340 k€"},
        ],

        # --- Acquisition ----------------------------------------------
        "acquisition": [
            {"label": "Leads qualifiés", "ltm": "11 240", "n1": "+8 %", "n1_cls": "d-up"},
            {"label": "Taux de conversion", "ltm": "14,2 %", "n1": "+1,1 pt", "n1_cls": "d-up"},
            {"label": "CAC moyen", "ltm": "132 €", "n1": "+11 €", "n1_cls": "d-down"},
            {"label": "CA moyen / étudiant", "ltm": "6 550 €", "n1": "+2,6 %", "n1_cls": "d-up"},
            {"label": "CA / CAC par étudiant", "ltm": "49,6×", "n1": "+1,2×", "n1_cls": "d-up"},
        ],

        # --- Campus (8) : données + valeurs dérivées pré-calculées -----
        "campus": _build_campus(),
        "campus_fil_colors": list(CAMPUS_FIL_COLORS),

        # --- Données des graphiques (injectées en JSON vers le JS) -----
        "charts": {
            "l12": list(_L12),
            "ca_m": list(_CA_M),
            "eb_m": list(_EB_M),
            "budget_ca": _BUDGET_CA,
            "budget_eb": _BUDGET_EB,
            # Écart réalisé cumulé vs budget (flèche à double pointe).
            "gap_ca": gap_text(sum(_CA_M) - _BUDGET_CA),
            "gap_eb": gap_text(sum(_EB_M) - _BUDGET_EB),
            "budget_label": "Budget N",
            "leg_reel": "Réalisé cumulé",
            "leg_budget": "Budget",
            "cash": {
                "labels": ["S23", "S24", "S25", "S26", "S27", "S28", "S29", "S30",
                           "S31", "S32", "S33", "S34", "S35", "S36", "S37", "S38", "S39"],
                "realise": [2.18, 2.31, 2.24, 2.45, None, None, None, None, None,
                            None, None, None, None, None, None, None, None],
                "projete": [None, None, None, 2.45, 2.38, 2.12, 1.86, 1.94, 1.71,
                            1.52, 1.44, 1.68, 2.05, 2.62, 3.18, 3.05, 2.88],
                "seuil": [1.0] * 17,
                "leg_realise": "Réalisé",
                "leg_projete": "Projeté",
                "seuil_label": "Seuil covenant 1,0 M€",
            },
            "inscr": {
                "labels": ["août", "sept", "oct", "nov", "déc", "janv", "févr",
                           "mars", "avr", "mai", "juin", "juil", "août", "sept"],
                "d2026": [90, 180, 230, 290, 400, 460, 780, 1240, 1690, 2080, 2210,
                          None, None, None],
                "d2025": [70, 150, 190, 240, 330, 380, 690, 1080, 1470, 1820, 2210,
                          2540, 2700, 2810],
                "leg_2026": "Rentrée 2026",
                "leg_2025": "Rentrée 2025",
                "color_2026": VIOLET,
                "color_2025": GRAY,
            },
            "fil": {
                "labels": ["BTS MCO", "BTS NDRC", "BTS CG", "BTS CI", "BTS PI",
                           "Autres BTS", "Bachelors", "Prépas"],
                "data": [420, 380, 260, 240, 210, 350, 250, 700],
                "colors": [VIOLET, VIOLET, VIOLET, VIOLET, VIOLET,
                           VIOLET_SOFT, VIOLET_SOFT, VIOLET_SOFT],
            },
        },

        # --- Projections (3 scénarios) --------------------------------
        "projections": {
            "labels": list(_F12),
            # Le premier scénario est celui sélectionné au chargement.
            "scenarios": [
                {"key": "base", "label": "Base"},
                {"key": "low", "label": "Rentrée −10 %"},
                {"key": "high", "label": "Rentrée +10 %"},
            ],
            "seuil": [1.0] * 12,
            "seuil_label": "Seuil 1,0 M€",
            # Points numérotés posés sur la courbe de trésorerie (index du mois).
            "cash_pts": [{"i": 1, "n": "1"}, {"i": 3, "n": "2"},
                         {"i": 4, "n": "3"}, {"i": 6, "n": "4"}],
            "leg_ca": "CA",
            "leg_eb": "EBITDA",
            "leg_cash": "Trésorerie",
            "scen": {
                "base": {
                    "ca": [820, 610, 2680, 2390, 1710, 1620, 2140, 1900, 1830, 1860, 1980, 1850],
                    "eb": [-160, -280, 780, 560, 240, 190, 420, 310, 280, 300, 340, 290],
                    "cash": [2.4, 1.9, 2.6, 3.4, 2.9, 3.3, 4.1, 4.3, 4.4, 4.6, 4.9, 5.0],
                    "hyp": ["Rentrée sept. 2026 : <b>2 990 étudiants</b> (+6 %)",
                            "NPEC stables",
                            "Tarifs initiale : <b>+2 %</b>",
                            "Attrition : 4,8 %",
                            "Ouverture campus : <b>1</b>"],
                },
                "low": {
                    "ca": [820, 610, 2410, 2150, 1540, 1460, 1930, 1710, 1650, 1670, 1780, 1670],
                    "eb": [-160, -280, 590, 400, 120, 80, 290, 190, 170, 180, 220, 180],
                    "cash": [2.4, 1.9, 2.3, 2.9, 2.4, 2.7, 3.1, 3.2, 3.2, 3.3, 3.5, 3.5],
                    "hyp": ["Rentrée sept. 2026 : <b>2 690 étudiants</b> (−10 % vs base)",
                            "NPEC stables",
                            "Tarifs inchangés",
                            "Attrition : 5,5 %",
                            "Ouverture campus : <b>1</b> (décalée à janv. 27)"],
                },
                "high": {
                    "ca": [820, 610, 2950, 2630, 1880, 1780, 2350, 2090, 2010, 2050, 2180, 2040],
                    "eb": [-160, -280, 970, 720, 360, 300, 550, 430, 390, 420, 460, 400],
                    "cash": [2.4, 1.9, 2.9, 3.9, 3.4, 3.9, 5.1, 5.5, 5.7, 6.0, 6.4, 6.6],
                    "hyp": ["Rentrée sept. 2026 : <b>3 290 étudiants</b> (+10 % vs base)",
                            "NPEC stables",
                            "Tarifs initiale : <b>+2 %</b>",
                            "Attrition : 4,4 %",
                            "Ouverture campus : <b>1</b>"],
                },
            },
        },

        # --- Points clés du prévisionnel de trésorerie -----------------
        # Numérotés 1..n à l'affichage ; correspondent aux 'cash_pts' du graphe.
        "points_cles": [
            "Service de la dette (annuité) : <b>(1,5) M€</b> — creux d'août 26",
            "Encaissements rentrée (scolarité + acomptes) — pic sept.-oct. 26",
            "Liquidation IS : <b>(0,6) M€</b> — creux de nov. 26",
            "Premiers versements NPEC rentrée — janv.-févr. 27",
        ],

        # Blocs marqués « démo » dans l'UI. Vide en mode demo (tout est démo).
        "demo_blocks": [],
    }
