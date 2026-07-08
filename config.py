"""Chargement de la configuration depuis le fichier d'environnement.

Le fichier fourni s'appelle ``env`` (sans point) mais on accepte aussi ``.env``.
Aucun secret n'est codé en dur : tout vient du fichier via python-dotenv.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# On charge le premier fichier d'env trouvé (`.env` prioritaire, sinon `env`).
for _candidate in (".env", "env"):
    _path = BASE_DIR / _candidate
    if _path.exists():
        load_dotenv(_path)
        ENV_FILE = _path
        break
else:  # pragma: no cover - garde-fou
    ENV_FILE = None


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Variable d'environnement manquante : {name}. "
            f"Vérifiez le fichier d'environnement ({ENV_FILE or 'introuvable'})."
        )
    return value


# --- Identifiants API (société cible : G2A) ---
CLIENT_ID = _require("FULLL_CLIENT_ID")
CLIENT_SECRET = _require("FULLL_CLIENT_SECRET")
ACCESS_TOKEN = _require("FULLL_ACCESS_TOKEN")
REFRESH_TOKEN = _require("FULLL_REFRESH_TOKEN")

# --- URLs ---
BASE_URL = _require("FULLL_BASE_URL").rstrip("/")  # ex: https://api.fulll.io/accounting/v1
# Endpoint OAuth2 de refresh (base racine de l'API, chemin /cred/oauth2/token).
TOKEN_URL = os.getenv("FULLL_TOKEN_URL", "https://api.fulll.io/cred/oauth2/token")

# Identifiant société (header X-Company). Optionnel : envoyé seulement s'il est défini.
COMPANY_ID = os.getenv("FULLL_COMPANY_ID", "").strip() or None

# --- App ---
APP_PORT = int(os.getenv("APP_PORT", "8501"))
# Mode d'affichage du dashboard : 'demo' (données du mockup) ou 'real' (SQLite).
# Défaut = demo. Peut être surchargé à chaud via l'UI (état en session).
APP_MODE = os.getenv("APP_MODE", "demo").strip().lower()
if APP_MODE not in ("demo", "real"):
    APP_MODE = "demo"
DB_PATH = os.getenv("DB_PATH", "data.db")
# Chemin absolu de la base pour éviter les surprises selon le cwd.
if not os.path.isabs(DB_PATH):
    DB_PATH = str(BASE_DIR / DB_PATH)

# Détection de l'exécution sur Vercel (variable posée automatiquement par la
# plateforme). Sur Vercel, le système de fichiers est en lecture seule sauf /tmp.
ON_VERCEL = bool(os.getenv("VERCEL"))

# Cache local des tokens rafraîchis (le fichier d'env n'est jamais modifié).
# Sur Vercel, seul /tmp est accessible en écriture -> on y déporte le cache.
if ON_VERCEL:
    TOKEN_CACHE = "/tmp/fulll_tokens.json"
else:
    TOKEN_CACHE = str(BASE_DIR / ".tokens.json")

# --- Base de données Turso (libsql, prod serverless) -------------------
# Si TURSO_DATABASE_URL est défini -> backend Turso ; sinon SQLite local (dev).
TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL", "").strip()
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "").strip() or None

# --- Authentification par mot de passe partagé -------------------------
# Hash bcrypt du mot de passe (jamais le mot de passe en clair). Si vide,
# l'authentification est désactivée (pratique en dev local uniquement).
DASHBOARD_PASSWORD_HASH = os.getenv("DASHBOARD_PASSWORD_HASH", "").strip()
# Clé de signature des cookies de session (itsdangerous) et de SessionMiddleware.
# En dev, une valeur par défaut permet de démarrer ; EN PROD, définissez-la.
SESSION_SECRET = os.getenv("SESSION_SECRET", "").strip() or "dev-insecure-change-me"

# --- Sécurité du cron (Vercel) -----------------------------------------
# Secret attendu dans l'en-tête Authorization: Bearer <CRON_SECRET> sur /api/sync.
# Si vide, la route n'est pas protégée (dev). En prod, définissez-la.
CRON_SECRET = os.getenv("CRON_SECRET", "").strip()
