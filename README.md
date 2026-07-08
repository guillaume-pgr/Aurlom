# Dashboard direction Aurlom (production)

Tableau de bord de pilotage pour la direction Aurlom, connecté à l'API
**fulll.io** (Accounting v1). Rendu fidèle au mockup `dashboard_aurlom_mockup.html`
(charte violet #5B2D8E, fond #F7F6F9, fonts Space Grotesk / Inter).

Deux modes de fonctionnement :
- **`demo`** (défaut) — affiche exactement les données du mockup (`demo_data.py`).
- **`real`** — calcule depuis SQLite ce qui est calculable (CA mensuel, P&L YTD
  par regroupement de comptes PCG, EBITDA) et complète le reste avec les données
  démo, signalées par un badge « démo ».

## Stack

- Python 3.11+, **FastAPI + Jinja2** (template issu du mockup) + **Chart.js** (CDN).
- **SQLite** (`DB_PATH`). Serveur **Uvicorn** sur `APP_PORT`, exposé sur le LAN
  (`host 0.0.0.0`).

## Architecture

| Fichier                   | Rôle                                                                    |
|---------------------------|-------------------------------------------------------------------------|
| `config.py`               | Lecture du `.env` (python-dotenv) + `APP_MODE` (demo/real).             |
| `client_fulll.py`         | Wrapper API fulll : Bearer, refresh auto sur 401, `get_accounts()`, `get_entries()`. |
| `sync.py`                 | Mode real : pull comptes + écritures de l'exercice (sept→auj.) → SQLite. |
| `mapping.py`              | Mapping PCG → postes P&L (70x=CA, 60x/61x/62x, 64x=masse salariale, EBITDA). |
| `demo_data.py`            | Données du mockup, en dur (source du mode demo).                        |
| `datasource.py`           | Couche unique `get_dashboard_data(mode)` → demo ou real.               |
| `db.py`                   | Schéma et accès SQLite (`accounts`, `entries`, `sync_log`).            |
| `templates/dashboard.html`| Mockup converti en template Jinja2 (zéro chiffre en dur).             |
| `main.py`                 | App FastAPI : routes `/`, `/sync`, `/health` + toggle de mode.         |

## Prérequis

Fichier d'environnement à la racine (le projet accepte `.env` **ou** `env`) :

```
FULLL_CLIENT_ID=...
FULLL_CLIENT_SECRET=...
FULLL_ACCESS_TOKEN=...
FULLL_REFRESH_TOKEN=...
FULLL_BASE_URL=https://api.fulll.io/accounting/v1
APP_PORT=8501
DB_PATH=data.db
```

> ⚠️ Le fichier d'environnement n'est **jamais** modifié. Les tokens rafraîchis
> sont persistés dans `.tokens.json` (ignoré par git). Aucun secret en dur.

Variables optionnelles : `APP_MODE` (`demo`|`real`), `FULLL_COMPANY_ID`
(header `X-Company` si requis), `FULLL_TOKEN_URL`.

## Installation

```powershell
cd C:\DEV\Dashboard_compta
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Lancement

```powershell
python -m uvicorn main:app --host 0.0.0.0 --port 8501
```

- Local : http://localhost:8501
- LAN (direction) : http://IP_DE_LA_MACHINE:8501 (ex : `http://192.168.0.73:8501`)

Trouver l'IP LAN : `ipconfig` (adresse IPv4). Ouvrir le port 8501 au pare-feu si besoin.

## Changer de mode

- Interface : bouton discret **demo ⇄ real** dans la sidebar (état gardé en session).
- Ou au démarrage : `APP_MODE=real` dans l'environnement.
- Le mode `real` requiert au moins une synchronisation préalable.

## Synchronisation (mode real)

- En CLI : `python sync.py` (pull comptes + écritures de l'exercice en cours).
- Via l'UI : bouton **Synchroniser** (POST `/sync`).

Chaque synchro est journalisée dans la table `sync_log` (début, fin, statut,
volumétrie, message). Les écritures sont en UPSERT (pas de doublon).

## Endpoints

| Méthode | Route     | Description                                   |
|---------|-----------|-----------------------------------------------|
| GET     | `/`       | Dashboard (respecte le mode courant).         |
| POST    | `/sync`   | Lance une synchro (mode real) puis redirige.  |
| GET     | `/health` | Sonde de santé (JSON `{"status": "ok"}`).     |
