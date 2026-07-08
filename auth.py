"""Authentification par mot de passe partagé (sans comptes utilisateur).

Principe :
- Un seul mot de passe partagé, dont le **hash bcrypt** est stocké dans la
  variable d'environnement ``DASHBOARD_PASSWORD_HASH`` (jamais le clair).
- En cas de succès, on pose un cookie contenant un jeton signé
  (itsdangerous, clé ``SESSION_SECRET``), valable 30 jours.
- Aucune base d'utilisateurs : la validité du cookie = « connecté ».
"""
from __future__ import annotations

from datetime import datetime, timezone

import bcrypt
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

import config

# Nom du cookie de session et durée de vie (30 jours).
COOKIE_NAME = "dash_session"
MAX_AGE_SECONDS = 30 * 24 * 3600

# Sérialiseur signé (HMAC) : le contenu est lisible mais infalsifiable.
_serializer = URLSafeTimedSerializer(config.SESSION_SECRET, salt="dashboard-auth")


def auth_required() -> bool:
    """L'authentification est active dès qu'un hash de mot de passe est fourni.

    En dev local sans ``DASHBOARD_PASSWORD_HASH``, l'accès reste ouvert.
    """
    return bool(config.DASHBOARD_PASSWORD_HASH)


def check_password(plain: str) -> bool:
    """Compare le mot de passe soumis au hash bcrypt configuré."""
    if not config.DASHBOARD_PASSWORD_HASH or not plain:
        return False
    try:
        return bcrypt.checkpw(
            plain.encode("utf-8"),
            config.DASHBOARD_PASSWORD_HASH.encode("utf-8"),
        )
    except ValueError:
        # Hash mal formé -> refus plutôt qu'erreur 500.
        return False


def make_session_token() -> str:
    """Crée un jeton de session signé et horodaté."""
    return _serializer.dumps({"iat": datetime.now(timezone.utc).isoformat()})


def valid_session(token: str | None) -> bool:
    """Vérifie la signature et l'expiration (30 jours) du jeton de cookie."""
    if not token:
        return False
    try:
        _serializer.loads(token, max_age=MAX_AGE_SECONDS)
        return True
    except (BadSignature, SignatureExpired):
        return False
