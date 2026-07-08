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


# --- Identifiants API (société cible : G2A) ---
# IMPORTANT : ces variables sont OPTIONNELLES au chargement. En mode 'demo',
# l'application ne touche jamais à l'API fulll : elle ne doit donc jamais
# planter au démarrage (ni à chaque requête) si elles sont absentes.
# La présence des identifiants n'est vérifiée que de façon *lazy*, au moment où
# le client fulll est réellement instancié (cf. ensure_fulll_credentials()).
CLIENT_ID = os.getenv("FULLL_CLIENT_ID") or None
CLIENT_SECRET = os.getenv("FULLL_CLIENT_SECRET") or None
ACCESS_TOKEN = os.getenv("FULLL_ACCESS_TOKEN") or None
REFRESH_TOKEN = os.getenv("FULLL_REFRESH_TOKEN") or None

# --- URLs ---
_base_url = os.getenv("FULLL_BASE_URL")
BASE_URL = _base_url.rstrip("/") if _base_url else None  # ex: https://api.fulll.io/accounting/v1
# Endpoint OAuth2 de refresh (base racine de l'API, chemin /cred/oauth2/token).
TOKEN_URL = os.getenv("FULLL_TOKEN_URL", "https://api.fulll.io/cred/oauth2/token")

# Variables requises pour tout appel réel à l'API fulll (mode 'real' / synchro).
_FULLL_REQUIRED = (
    "FULLL_CLIENT_ID",
    "FULLL_CLIENT_SECRET",
    "FULLL_ACCESS_TOKEN",
    "FULLL_REFRESH_TOKEN",
    "FULLL_BASE_URL",
)


def ensure_fulll_credentials() -> None:
    """Valide la présence des identifiants fulll — appel *lazy*.

    N'est invoquée qu'au moment où l'on va réellement contacter l'API (mode
    'real' / synchro), typiquement à l'instanciation de ``FulllClient``. En mode
    'demo', elle n'est jamais appelée : l'app démarre et sert toutes les routes
    sans exiger ces variables.
    """
    missing = [name for name in _FULLL_REQUIRED if not os.getenv(name)]
    if missing:
        raise RuntimeError(
            "Variables d'environnement fulll manquantes : "
            f"{', '.join(missing)}. Requises uniquement en mode 'real' "
            f"(synchro). Vérifiez le fichier d'environnement "
            f"({ENV_FILE or 'introuvable'})."
        )

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
