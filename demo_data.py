"""Données de démonstration = valeurs EXACTES du mockup dashboard_aurlom_mockup.html.

Ce module est l'unique source du mode ``demo``. La structure est volontairement
« data-driven » : le template Jinja2 se contente d'itérer sur ces objets, donc le
mode ``real`` peut réutiliser exactement le même gabarit en ne remplaçant que les
blocs calculables (cf. datasource.py).

Aucune valeur n'est codée en dur ailleurs que dans ce fichier.
"""
from __future__ import annotations

# Palette (identique au mockup / charte Aurlom).
VIOLET = "#5B2D8E"
VIOLET_SOFT = "#C9B8E4"   # 'VS' dans le mockup
WARN = "#9A6700"


def build() -> dict:
    """Retourne une copie neuve du jeu de données démo."""
    return {
        # --- En-tête & barre latérale ---------------------------------
        "meta": {
            "titre": "Tableau de bord Direction",
            "exercice": "2025-26",
            "ytd": "sept. → juin",
            "maj": "02/07/2026",
            "sync_fulll": "02/07 · 07:15",
            "sync_banques": "02/07 · 06:30",
            "footer": ("Source comptable : API fulll (dossier G2A) · "
                       "Banques : agrégation quotidienne · Scolarité : export SI "
                       "hebdo · Données fictives — mockup v1"),
        },

        # --- Bande des 5 KPIs -----------------------------------------
        "kpis": [
            {"lbl": "Chiffre d'affaires YTD", "val": "18,42", "unit": "M€",
             "sub": "vs N-1", "chip": "+9,2 %", "chip_cls": "up",
             "spark": "0,18 8,16 16,17 24,12 32,13 40,9 48,10 56,6 64,4",
             "spark_color": VIOLET},
            {"lbl": "EBITDA YTD", "val": "3,11", "unit": "M€",
             "sub": "marge 16,9 %", "chip": "+0,6 pt", "chip_cls": "up",
             "spark": "0,19 8,17 16,18 24,14 32,15 40,12 48,13 56,9 64,8",
             "spark_color": VIOLET},
            {"lbl": "Trésorerie nette", "val": "2,45", "unit": "M€",
             "sub": "30 jours", "chip": "+310 k€", "chip_cls": "up",
             "spark": "0,14 8,16 16,12 24,15 32,10 40,13 48,8 56,10 64,5",
             "spark_color": VIOLET},
            {"lbl": "Étudiants inscrits", "val": "2 810", "unit": "",
             "sub": "vs N-1", "chip": "+6,4 %", "chip_cls": "up",
             "spark": "0,20 8,19 16,17 24,16 32,13 40,11 48,9 56,6 64,4",
             "spark_color": VIOLET},
            {"lbl": "Créances OPCO", "val": "1,92", "unit": "M€",
             "sub": "DSO 74 j", "chip": "+9 j", "chip_cls": "warn",
             "spark": "0,16 8,14 16,15 24,12 32,13 40,10 48,11 56,8 64,6",
             "spark_color": WARN},
        ],

        # --- Alertes ---------------------------------------------------
        "alerts": [
            {"cls": "red", "pre": "Créances OPCO > 90 j : ", "b": "412 k€",
             "post": " (AKTO, Atlas)"},
            {"cls": "amb", "pre": "Marketing YTD : ", "b": "+14 %",
             "post": " vs budget"},
            {"cls": "vio", "pre": "Acompte IS : ", "b": "287 k€",
             "post": " — échéance 15/09"},
            {"cls": "vio", "pre": "Service dette Capza T3 : ", "b": "340 k€",
             "post": " — 30/09"},
        ],

        # --- Tableau P&L YTD synthétique ------------------------------
        # 'val' en nombres bruts (k€) : le formatage est fait par fmt() (négatifs
        # entre parenthèses, zéro '-'), appliqué dans le template.
        "pnl_note": "k€ · réel vs budget vs N-1",
        "pnl_table": [
            {"label": "Chiffre d'affaires", "val": 18420,
             "delta": "+9,2 %", "delta_cls": "d-up", "cls": ""},
            {"label": "dont alternance (OPCO)", "val": 9870,
             "delta": "+12,1 %", "delta_cls": "d-up", "cls": "sub"},
            {"label": "dont scolarité initiale", "val": 6940,
             "delta": "+5,8 %", "delta_cls": "d-up", "cls": "sub"},
            {"label": "dont stages & prépas", "val": 1610,
             "delta": "+3,4 %", "delta_cls": "d-up", "cls": "sub"},
            {"label": "Coûts pédagogiques", "val": -6310,
             "delta": "+10,4 %", "delta_cls": "d-down", "cls": ""},
            {"label": "Marge brute", "pct": "65,7 %", "val": 12110,
             "delta": "+8,6 %", "delta_cls": "d-up", "cls": "tot"},
            {"label": "Masse salariale support", "val": -4020,
             "delta": "+6,1 %", "delta_cls": "", "cls": ""},
            {"label": "Loyers campus", "val": -2340,
             "delta": "+2,9 %", "delta_cls": "", "cls": ""},
            {"label": "Marketing & admissions", "val": -1480,
             "delta": "+18,2 %", "delta_cls": "d-down", "cls": ""},
            {"label": "Autres opex", "val": -1160,
             "delta": "+4,0 %", "delta_cls": "", "cls": ""},
            {"label": "EBITDA", "pct": "16,9 %", "val": 3110,
             "delta": "+13,5 %", "delta_cls": "d-up", "cls": "tot"},
        ],

        # --- Covenants Capza ------------------------------------------
        # Covenants bancaires du LBO. status : green si conforme, red si breach.
        "covenants": [
            {"name": "Levier net (DN/EBITDA)", "value": "1,8×",
             "rule": "doit être < 2,0×", "status": "green"},
            {"name": "DSCR (CF libre / service dette)", "value": "1,6×",
             "rule": "doit être > 1,0×", "status": "green"},
        ],

        # --- Prochaines échéances LBO ---------------------------------
        # amount = échéance monétaire ; à défaut 'doc' = livrable non monétaire.
        "echeances": [
            {"label": "Reporting T2 2026 (J+60)", "date": "31/08", "doc": True},
            {"label": "Attestation de ratios au 30/06/2026", "date": "15/09", "doc": True},
            {"label": "Demande waiver capex", "date": "30/09", "doc": True},
            {"label": "Service dette T3", "date": "30/09", "amount": "340 k€"},
        ],

        # --- Acquisition ----------------------------------------------
        "acquisition": [
            {"label": "Leads qualifiés", "ytd": "11 240", "n1": "+8 %", "n1_cls": "d-up"},
            {"label": "Taux de conversion", "ytd": "14,2 %", "n1": "+1,1 pt", "n1_cls": "d-up"},
            {"label": "CAC moyen", "ytd": "132 €", "n1": "+11 €", "n1_cls": "d-down"},
            {"label": "CA moyen / étudiant", "ytd": "6 550 €", "n1": "+2,6 %", "n1_cls": "d-up"},
            {"label": "CA / CAC par étudiant", "ytd": "49,6×", "n1": "+1,2×", "n1_cls": "d-up"},
        ],

        # --- Performance par campus -----------------------------------
        "campus": [
            {"nom": "Paris — Roquette", "etu": "1 450", "cap": "1 600",
             "fill": 91, "ca": "9 620", "ebitda": "1 980", "marge": "20,6 %"},
            {"nom": "Paris — Nation", "etu": "620", "cap": "750",
             "fill": 83, "ca": "3 890", "ebitda": "640", "marge": "16,5 %"},
            {"nom": "Nice", "etu": "420", "cap": "520",
             "fill": 81, "ca": "2 710", "ebitda": "360", "marge": "13,3 %"},
            {"nom": "Lille", "etu": "360", "cap": "500",
             "fill": 72, "ca": "2 200", "ebitda": "130", "marge": "5,9 %"},
        ],

        # --- Données des graphiques (injectées telles quelles en JS) ---
        "charts": {
            "pnl": {
                "labels": ["sept.25", "oct.25", "nov.25", "déc.25", "janv.26",
                           "févr.26", "mars 26", "avr.26", "mai 26", "juin 26"],
                "reel":   [2450, 2210, 1580, 1490, 1980, 1760, 1690, 1720, 1830, 1710],
                "budget": [2350, 2150, 1550, 1500, 1900, 1750, 1700, 1680, 1780, 1690],
                "n1":     [2280, 2020, 1440, 1380, 1790, 1620, 1540, 1580, 1660, 1560],
                # Barres de totaux ajoutées en fin de graphe (k€).
                "total_n": 18420,       # YTD N    = 18,42 M€
                "total_budget": 18050,  # Budget N = 18,05 M€
            },
            "cash": {
                "labels": ["S23", "S24", "S25", "S26", "S27", "S28", "S29", "S30",
                           "S31", "S32", "S33", "S34", "S35", "S36", "S37", "S38", "S39"],
                "realise": [2.18, 2.31, 2.24, 2.45, None, None, None, None, None,
                            None, None, None, None, None, None, None, None],
                "projete": [None, None, None, 2.45, 2.38, 2.12, 1.86, 1.94, 1.71,
                            1.52, 1.44, 1.68, 2.05, 2.62, 3.18, 3.05, 2.88],
                "seuil": [1.0] * 17,
            },
            "inscr": {
                "labels": ["Jan", "Fév", "Mar", "Avr", "Mai", "Juin", "Juil", "Août", "Sept"],
                "d2026": [180, 420, 780, 1240, 1690, 2080, None, None, None],
                "d2025": [160, 380, 690, 1080, 1470, 1820, 2210, 2540, 2810],
            },
            "fil": {
                "labels": ["BTS MCO", "BTS NDRC", "BTS CG", "BTS CI", "BTS PI",
                           "Autres BTS", "Bachelors", "Prépas"],
                "data": [420, 380, 260, 240, 210, 350, 250, 700],
                "colors": [VIOLET, VIOLET, VIOLET, VIOLET, VIOLET,
                           VIOLET_SOFT, VIOLET_SOFT, VIOLET_SOFT],
            },
            "scen": {
                "labels": ["juil.26", "août 26", "sept.26", "oct.26", "nov.26",
                           "déc.26", "janv.27", "févr.27", "mars 27", "avr.27",
                           "mai 27", "juin 27"],
                "seuil": [1.0] * 12,
                "base": {
                    "ca":   [820, 610, 2680, 2390, 1710, 1620, 2140, 1900, 1830, 1860, 1980, 1850],
                    "eb":   [-160, -280, 780, 560, 240, 190, 420, 310, 280, 300, 340, 290],
                    "cash": [2.4, 1.9, 2.6, 3.4, 3.7, 3.6, 4.1, 4.3, 4.4, 4.6, 4.9, 5.0],
                },
                "low": {
                    "ca":   [820, 610, 2410, 2150, 1540, 1460, 1930, 1710, 1650, 1670, 1780, 1670],
                    "eb":   [-160, -280, 590, 400, 120, 80, 290, 190, 170, 180, 220, 180],
                    "cash": [2.4, 1.9, 2.3, 2.9, 3.0, 2.8, 3.1, 3.2, 3.2, 3.3, 3.5, 3.5],
                },
                "high": {
                    "ca":   [820, 610, 2950, 2630, 1880, 1780, 2350, 2090, 2010, 2050, 2180, 2040],
                    "eb":   [-160, -280, 970, 720, 360, 300, 550, 430, 390, 420, 460, 400],
                    "cash": [2.4, 1.9, 2.9, 3.9, 4.4, 4.4, 5.1, 5.5, 5.7, 6.0, 6.4, 6.6],
                },
            },
        },

        # Blocs marqués « démo » dans l'UI. Vide en mode demo (tout est démo).
        "demo_blocks": [],
    }
