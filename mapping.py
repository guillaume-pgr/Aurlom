"""Mapping Plan Comptable Général (PCG) -> postes du P&L.

Sert au mode ``real`` : on classe chaque compte (classe 6 = charges,
classe 7 = produits) dans un poste de gestion, puis on agrège les
mouvements des écritures pour reconstituer un compte de résultat simplifié
et l'EBITDA.

Convention de signe retenue (vision "gestion") :
- Produits (classe 7) : montant = credit - debit  (un produit augmente au crédit).
- Charges (classe 6)  : montant = debit - credit   (une charge augmente au débit).
Ainsi CA et charges ressortent en valeurs positives.
"""
from __future__ import annotations

# Libellés des postes du compte de résultat, dans l'ordre d'affichage.
POSTES = {
    "ca": "Chiffre d'affaires",                     # 70x
    "autres_produits": "Autres produits",           # 71x 72x 74x 75x
    "achats": "Achats",                             # 60x
    "services_ext": "Services extérieurs",          # 61x 62x
    "impots_taxes": "Impôts et taxes",              # 63x
    "masse_salariale": "Masse salariale",           # 64x
    "autres_charges": "Autres charges de gestion",  # 65x
    "dotations": "Dotations amortissements",        # 68x
    "resultat_financier": "Résultat financier",     # 76x (produit) / 66x (charge)
    "resultat_except": "Résultat exceptionnel",     # 77x (produit) / 67x (charge)
}

# Regroupement par préfixe de numéro de compte (les plus longs d'abord).
# clé = préfixe PCG, valeur = (poste, nature) avec nature ∈ {'produit', 'charge'}.
_PREFIXES: list[tuple[str, str, str]] = [
    # --- Produits (classe 7) ---
    ("70", "ca", "produit"),
    ("71", "autres_produits", "produit"),
    ("72", "autres_produits", "produit"),
    ("74", "autres_produits", "produit"),
    ("75", "autres_produits", "produit"),
    ("76", "resultat_financier", "produit"),
    ("77", "resultat_except", "produit"),
    # --- Charges (classe 6) ---
    ("60", "achats", "charge"),
    ("61", "services_ext", "charge"),
    ("62", "services_ext", "charge"),
    ("63", "impots_taxes", "charge"),
    ("64", "masse_salariale", "charge"),
    ("65", "autres_charges", "charge"),
    ("66", "resultat_financier", "charge"),
    ("67", "resultat_except", "charge"),
    ("68", "dotations", "charge"),
]

# Postes entrant dans l'EBITDA (exploitation, hors dotations/financier/exceptionnel).
_EBITDA_PRODUITS = ("ca", "autres_produits")
_EBITDA_CHARGES = ("achats", "services_ext", "impots_taxes",
                   "masse_salariale", "autres_charges")


def classify(account_number: str) -> tuple[str | None, str | None]:
    """Retourne (poste, nature) pour un numéro de compte, ou (None, None)."""
    if not account_number:
        return None, None
    num = str(account_number).strip()
    for prefix, poste, nature in _PREFIXES:
        if num.startswith(prefix):
            return poste, nature
    return None, None


def entry_amount(poste_nature: str, debit: float, credit: float) -> float:
    """Montant orienté 'gestion' selon la nature du poste."""
    debit = debit or 0.0
    credit = credit or 0.0
    if poste_nature == "produit":
        return credit - debit
    return debit - credit  # charge


def aggregate_pnl(rows: list[dict]) -> dict:
    """Agrège des lignes {account, debit, credit} en postes de P&L.

    Retourne un dict : { poste: montant, ..., 'ebitda': x, 'ebit': y,
    'resultat_net': z }.
    """
    totals = {poste: 0.0 for poste in POSTES}
    for r in rows:
        poste, nature = classify(r.get("account"))
        if not poste:
            continue
        totals[poste] += entry_amount(nature, r.get("debit"), r.get("credit"))

    produits_expl = sum(totals[p] for p in _EBITDA_PRODUITS)
    charges_expl = sum(totals[c] for c in _EBITDA_CHARGES)
    ebitda = produits_expl - charges_expl
    ebit = ebitda - totals["dotations"]
    resultat_net = ebit + totals["resultat_financier"] + totals["resultat_except"]

    totals["ebitda"] = ebitda
    totals["ebit"] = ebit
    totals["resultat_net"] = resultat_net
    return totals
