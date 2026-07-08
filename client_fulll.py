"""Client HTTP pour l'API fulll.io (Accounting v1).

- Auth Bearer + refresh token depuis le fichier d'env.
- Refresh automatique et transparent sur réponse 401.
- Les tokens rafraîchis sont mis en cache dans un fichier local
  (``.tokens.json``) : le fichier d'environnement n'est jamais modifié.
"""
from __future__ import annotations

import json
import os
from typing import Any

import requests

import config


class FulllClient:
    def __init__(self) -> None:
        # Validation *lazy* : on ne vérifie la présence des identifiants qu'ici,
        # c.-à-d. au moment d'un usage réel de l'API (jamais en mode démo).
        config.ensure_fulll_credentials()
        self._access_token = config.ACCESS_TOKEN
        self._refresh_token = config.REFRESH_TOKEN
        self._load_cached_tokens()
        self._session = requests.Session()

    # --- Gestion des tokens ---------------------------------------------
    def _load_cached_tokens(self) -> None:
        """Recharge des tokens précédemment rafraîchis, s'ils existent."""
        try:
            with open(config.TOKEN_CACHE, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self._access_token = data.get("access_token") or self._access_token
            self._refresh_token = data.get("refresh_token") or self._refresh_token
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def _save_cached_tokens(self) -> None:
        tmp = config.TOKEN_CACHE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(
                {"access_token": self._access_token,
                 "refresh_token": self._refresh_token},
                fh,
            )
        os.replace(tmp, config.TOKEN_CACHE)

    def _refresh(self) -> None:
        """Échange le refresh token contre un nouvel access token."""
        resp = requests.post(
            config.TOKEN_URL,
            json={
                "grant_type": "refresh_token",
                "client_id": config.CLIENT_ID,
                "client_secret": config.CLIENT_SECRET,
                "refresh_token": self._refresh_token,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data["access_token"]
        # Certains fournisseurs font tourner le refresh token : on le garde.
        self._refresh_token = data.get("refresh_token", self._refresh_token)
        self._save_cached_tokens()

    # --- Requêtes -------------------------------------------------------
    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/json",
        }
        if config.COMPANY_ID:
            headers["X-Company"] = config.COMPANY_ID
        return headers

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        url = f"{config.BASE_URL}/{path.lstrip('/')}"
        resp = self._session.get(url, headers=self._headers(), params=params, timeout=60)
        if resp.status_code == 401:
            # Token expiré : on rafraîchit une fois puis on rejoue la requête.
            self._refresh()
            resp = self._session.get(url, headers=self._headers(), params=params, timeout=60)
        resp.raise_for_status()
        return resp.json()

    # --- Endpoints métier ----------------------------------------------
    def get_accounts(self, limit: int = 200) -> list[dict]:
        """Retourne tous les comptes (plan comptable), avec soldes.

        Pagine automatiquement via ``page``/``limit``.
        """
        accounts: list[dict] = []
        page = 1
        while True:
            data = self._get(
                "accounts",
                params={"complete_mode": 1, "page": page, "limit": limit},
            )
            batch = (data.get("_embedded") or {}).get("accounts", [])
            accounts.extend(batch)
            total = data.get("total")
            if not batch or (total is not None and len(accounts) >= total):
                break
            page += 1
        return accounts

    def get_entries(self, period_start: str, period_end: str) -> list[dict]:
        """Retourne les écritures pour une période.

        ``period_start`` / ``period_end`` au format ``mm/yyyy``.
        """
        data = self._get(
            "entries",
            params={"period_start": period_start, "period_end": period_end},
        )
        # La réponse expose les lignes sous la clé ``entries``.
        return data.get("entries", [])
