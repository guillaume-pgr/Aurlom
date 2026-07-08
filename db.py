"""Accès base de données : abstraction SQLite (dev) / Turso libsql (prod).

Deux backends interchangeables, sélectionnés automatiquement :

- Si ``TURSO_DATABASE_URL`` est défini  -> Turso (libsql-client, transport HTTP,
  idéal en serverless : sans état, autocommit par requête).
- Sinon                                 -> SQLite local (fichier ``DB_PATH``),
  pour le développement (uvicorn + .env).

Les deux exposent la même API (``query`` / ``execute`` / ``executemany`` /
upserts / journal de synchro / tentatives de login), si bien que le reste de
l'application ignore totalement le backend utilisé. Le schéma est identique.
"""
from __future__ import annotations

import sqlite3
import threading
from typing import Any, Iterable, Sequence

import config

# --- Schéma -----------------------------------------------------------------
# Une instruction par entrée : rejouable aussi bien via sqlite3 que via le
# ``batch()`` de libsql (qui, contrairement à sqlite3, n'a pas d'executescript).
SCHEMA_STATEMENTS: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS accounts (
        id       TEXT PRIMARY KEY,
        number   TEXT,
        label    TEXT,
        type     TEXT,
        debit    REAL,
        credit   REAL,
        balance  REAL,
        status   TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS entries (
        lineid   TEXT PRIMARY KEY,
        header   TEXT,
        number   TEXT,
        book     TEXT,
        period   TEXT,
        day      TEXT,
        account  TEXT,
        label    TEXT,
        debit    REAL,
        credit   REAL,
        letter   TEXT,
        due_date TEXT,
        account_type TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sync_log (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        started_at    TEXT NOT NULL,
        finished_at   TEXT,
        status        TEXT NOT NULL,          -- 'running' | 'ok' | 'error'
        accounts_count INTEGER DEFAULT 0,
        entries_count  INTEGER DEFAULT 0,
        period_start  TEXT,
        period_end    TEXT,
        message       TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS login_attempts (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        ip           TEXT NOT NULL,
        attempted_at TEXT NOT NULL
    )
    """,
]


# --- Backend SQLite (développement local) -----------------------------------
class _SqliteBackend:
    """Backend fichier local, connexion ouverte/fermée à chaque appel."""

    def __init__(self) -> None:
        self._path = config.DB_PATH

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self) -> None:
        conn = self._conn()
        try:
            for stmt in SCHEMA_STATEMENTS:
                conn.execute(stmt)
            conn.commit()
        finally:
            conn.close()

    def query(self, sql: str, params: Any = None) -> list[dict]:
        conn = self._conn()
        try:
            cur = conn.execute(sql, params if params is not None else [])
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def execute(self, sql: str, params: Any = None) -> int:
        conn = self._conn()
        try:
            cur = conn.execute(sql, params if params is not None else [])
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def executemany(self, sql: str, rows: Sequence[Any]) -> int:
        conn = self._conn()
        try:
            conn.executemany(sql, rows)
            conn.commit()
            return len(rows)
        finally:
            conn.close()


# --- Backend Turso (production serverless) ----------------------------------
class _TursoBackend:
    """Backend libsql-client, client synchrone réutilisé sur tout le process.

    Le client est instancié une fois par conteneur (réutilisé entre invocations
    « chaudes ») : pas de coût de reconnexion à chaque requête.
    """

    def __init__(self) -> None:
        # Import local : la dépendance n'est requise qu'en mode Turso.
        import libsql_client

        url = config.TURSO_DATABASE_URL
        # On force le transport HTTP (sans état), le plus adapté au serverless :
        # libsql://  -> https://
        if url.startswith("libsql://"):
            url = "https://" + url[len("libsql://"):]
        self._client = libsql_client.create_client_sync(
            url=url, auth_token=config.TURSO_AUTH_TOKEN
        )

    def init_schema(self) -> None:
        # Un seul aller-retour réseau pour créer toutes les tables.
        self._client.batch([stmt for stmt in SCHEMA_STATEMENTS])

    def query(self, sql: str, params: Any = None) -> list[dict]:
        rs = self._client.execute(sql, params if params is not None else None)
        cols = rs.columns
        return [dict(zip(cols, row)) for row in rs.rows]

    def execute(self, sql: str, params: Any = None) -> int:
        rs = self._client.execute(sql, params if params is not None else None)
        # last_insert_rowid vaut None quand l'instruction n'insère rien.
        return rs.last_insert_rowid

    def executemany(self, sql: str, rows: Sequence[Any]) -> int:
        # batch() = une transaction, un seul aller-retour réseau.
        self._client.batch([(sql, r) for r in rows])
        return len(rows)


# --- Sélection paresseuse du backend (thread-safe) --------------------------
_backend: Any = None
_lock = threading.Lock()


def _get_backend():
    global _backend
    if _backend is None:
        with _lock:
            if _backend is None:
                backend = (
                    _TursoBackend() if config.TURSO_DATABASE_URL else _SqliteBackend()
                )
                # Schéma garanti présent dès la première utilisation.
                backend.init_schema()
                _backend = backend
    return _backend


# --- API générique ----------------------------------------------------------
def init_db() -> None:
    """Garantit l'existence du backend et du schéma (idempotent)."""
    _get_backend()


def query(sql: str, params: Any = None) -> list[dict]:
    """Exécute un SELECT et renvoie une liste de dicts."""
    return _get_backend().query(sql, params)


def execute(sql: str, params: Any = None) -> int:
    """Exécute une instruction d'écriture, renvoie le dernier rowid inséré."""
    return _get_backend().execute(sql, params)


# --- Upserts (comptes / écritures) ------------------------------------------
def upsert_accounts(rows: Iterable[dict]) -> int:
    rows = list(rows)
    if not rows:
        return 0
    return _get_backend().executemany(
        """
        INSERT INTO accounts (id, number, label, type, debit, credit, balance, status)
        VALUES (:id, :number, :label, :type, :debit, :credit, :balance, :status)
        ON CONFLICT(id) DO UPDATE SET
            number=excluded.number, label=excluded.label, type=excluded.type,
            debit=excluded.debit, credit=excluded.credit,
            balance=excluded.balance, status=excluded.status
        """,
        rows,
    )


def upsert_entries(rows: Iterable[dict]) -> int:
    rows = list(rows)
    if not rows:
        return 0
    return _get_backend().executemany(
        """
        INSERT INTO entries
            (lineid, header, number, book, period, day, account, label,
             debit, credit, letter, due_date, account_type)
        VALUES
            (:lineid, :header, :number, :book, :period, :day, :account, :label,
             :debit, :credit, :letter, :due_date, :account_type)
        ON CONFLICT(lineid) DO UPDATE SET
            header=excluded.header, number=excluded.number, book=excluded.book,
            period=excluded.period, day=excluded.day, account=excluded.account,
            label=excluded.label, debit=excluded.debit, credit=excluded.credit,
            letter=excluded.letter, due_date=excluded.due_date,
            account_type=excluded.account_type
        """,
        rows,
    )


# --- Journal de synchronisation ---------------------------------------------
def start_sync(started_at: str, period_start: str, period_end: str) -> int:
    return execute(
        """
        INSERT INTO sync_log (started_at, status, period_start, period_end)
        VALUES (?, 'running', ?, ?)
        """,
        [started_at, period_start, period_end],
    )


def finish_sync(sync_id: int, finished_at: str, status: str,
                accounts_count: int, entries_count: int, message: str = "") -> None:
    execute(
        """
        UPDATE sync_log
           SET finished_at=?, status=?, accounts_count=?, entries_count=?, message=?
         WHERE id=?
        """,
        [finished_at, status, accounts_count, entries_count, message, sync_id],
    )


def last_sync() -> dict | None:
    rows = query("SELECT * FROM sync_log ORDER BY id DESC LIMIT 1")
    return rows[0] if rows else None


# --- Rate limiting du login (par IP) ----------------------------------------
def record_login_attempt(ip: str, attempted_at: str) -> None:
    execute(
        "INSERT INTO login_attempts (ip, attempted_at) VALUES (?, ?)",
        [ip, attempted_at],
    )


def count_recent_attempts(ip: str, since_iso: str) -> int:
    rows = query(
        "SELECT COUNT(*) AS n FROM login_attempts WHERE ip=? AND attempted_at>=?",
        [ip, since_iso],
    )
    return int(rows[0]["n"]) if rows else 0


def oldest_attempt_since(ip: str, since_iso: str) -> str | None:
    rows = query(
        "SELECT MIN(attempted_at) AS t FROM login_attempts WHERE ip=? AND attempted_at>=?",
        [ip, since_iso],
    )
    return rows[0]["t"] if rows and rows[0]["t"] else None


def clear_login_attempts(ip: str) -> None:
    """Purge les tentatives d'une IP après une connexion réussie."""
    execute("DELETE FROM login_attempts WHERE ip=?", [ip])
