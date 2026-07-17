"""Application FastAPI — Dashboard direction Aurlom.

Routes principales :
- GET  /          : dashboard (mode courant demo/real, gardé en session).
- POST /sync      : synchro fulll -> base, déclenchée par le bouton de l'UI.
- GET  /health    : sonde de santé (publique).
- GET  /login     : formulaire de connexion (mot de passe partagé).
- POST /login     : vérifie le mot de passe, pose le cookie de session.
- GET  /logout    : supprime le cookie.
- GET/POST /api/sync : synchro déclenchée par le cron Vercel (protégée Bearer).

Un middleware global protège toutes les routes par cookie de session, sauf
``/login``, ``/health`` et ``/api/sync`` (qui a sa propre protection Bearer).
"""
from __future__ import annotations

import hmac
import secrets
from datetime import datetime, timedelta

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool
from starlette.middleware.sessions import SessionMiddleware

import auth
import config
import db
import excel_source
import excel_store
from datasource import get_dashboard_data
from sync import run_sync

# Taille maximale acceptée pour un upload Excel (garde-fou mémoire).
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 Mo

app = FastAPI(title="Dashboard direction Aurlom")

# Clé de signature de session stable (indispensable en serverless : sinon les
# cookies seraient invalidés à chaque démarrage à froid d'une nouvelle instance).
app.add_middleware(SessionMiddleware, secret_key=config.SESSION_SECRET)

templates = Jinja2Templates(directory=str(config.BASE_DIR / "templates"))

# Routes accessibles sans cookie de session.
# - /login : sinon impossible de se connecter.
# - /health : sonde publique.
# - /api/sync : protégée séparément par un secret Bearer (cron Vercel).
_EXEMPT_PATHS = {"/login", "/health", "/api/sync"}


def fmt(value, dec: int = 0) -> str:
    """Formatage nombres unifié (mêmes règles que le fmt() JS des graphiques).

    - None ou 0 -> '-'
    - séparateur de milliers = espace ; décimale = virgule
    - négatifs entre parenthèses : -1234 -> '(1 234)'
    """
    if value is None or value == "":
        return "-"
    try:
        x = float(value)
    except (TypeError, ValueError):
        return str(value)
    if x == 0:
        return "-"
    neg = x < 0
    a = abs(x)
    if dec:
        s = f"{a:,.{dec}f}".replace(",", " ").replace(".", ",")
    else:
        s = f"{int(round(a)):,}".replace(",", " ")
    return f"({s})" if neg else s


templates.env.filters["fmt"] = fmt


# --- Authentification : middleware global ------------------------------
@app.middleware("http")
async def require_login(request: Request, call_next):
    """Redirige vers /login si le cookie de session est absent/invalide/expiré."""
    # Auth désactivée (dev local sans hash configuré) : on laisse passer.
    if not auth.auth_required():
        return await call_next(request)
    if request.url.path in _EXEMPT_PATHS:
        return await call_next(request)
    if auth.valid_session(request.cookies.get(auth.COOKIE_NAME)):
        return await call_next(request)
    return RedirectResponse(url="/login", status_code=303)


# --- Helpers ------------------------------------------------------------
def _client_ip(request: Request) -> str:
    """IP réelle du client (derrière le proxy Vercel : X-Forwarded-For)."""
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _secure_cookie(request: Request) -> bool:
    """Cookie Secure uniquement en HTTPS (permet le dev en http://localhost)."""
    return request.url.scheme == "https"


def _current_mode(request: Request) -> str:
    """Mode effectif : ?mode= (prioritaire, persisté) sinon session sinon défaut."""
    q = request.query_params.get("mode")
    if q in ("demo", "real"):
        request.session["mode"] = q
        return q
    return request.session.get("mode", config.APP_MODE)


# --- Dashboard ----------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    mode = _current_mode(request)
    data = get_dashboard_data(mode)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {"d": data, "mode": mode},
    )


@app.post("/sync")
def sync(request: Request):
    """Lance une synchronisation (bouton UI) puis revient au dashboard en real."""
    result = run_sync()
    request.session["mode"] = "real"
    request.session["last_sync_msg"] = result.get("message", "")
    return RedirectResponse(url="/?mode=real", status_code=303)


@app.get("/health")
def health():
    return JSONResponse({"status": "ok", "mode_default": config.APP_MODE})


# --- Authentification : routes -----------------------------------------
@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    # Déjà connecté : inutile de réafficher le formulaire.
    if auth.auth_required() and auth.valid_session(request.cookies.get(auth.COOKIE_NAME)):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(request, "login.html", {"error": None})


@app.post("/login", response_class=HTMLResponse)
def login_submit(request: Request, password: str = Form("")):
    ip = _client_ip(request)
    now = datetime.now()
    window_start = (now - timedelta(minutes=10)).isoformat(timespec="seconds")

    # Rate limiting : au-delà de 5 tentatives / 10 min pour une IP -> blocage.
    attempts = db.count_recent_attempts(ip, window_start)
    if attempts >= 5:
        oldest = db.oldest_attempt_since(ip, window_start)
        wait_min = 10
        if oldest:
            try:
                elapsed = (now - datetime.fromisoformat(oldest)).total_seconds()
                wait_min = max(1, int(round((600 - elapsed) / 60)))
            except ValueError:
                wait_min = 10
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": f"Trop de tentatives. Réessayez dans {wait_min} minute(s)."},
            status_code=429,
        )

    if auth.check_password(password):
        # Succès : on purge le compteur et on pose le cookie signé.
        db.clear_login_attempts(ip)
        resp = RedirectResponse(url="/", status_code=303)
        resp.set_cookie(
            key=auth.COOKIE_NAME,
            value=auth.make_session_token(),
            max_age=auth.MAX_AGE_SECONDS,
            httponly=True,
            secure=_secure_cookie(request),
            samesite="lax",
        )
        return resp

    # Échec : on journalise la tentative et on réaffiche le formulaire.
    db.record_login_attempt(ip, now.isoformat(timespec="seconds"))
    return templates.TemplateResponse(
        request,
        "login.html",
        {"error": "Mot de passe incorrect."},
        status_code=401,
    )


@app.get("/logout")
def logout():
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie(auth.COOKIE_NAME)
    return resp


# --- Cron : synchro planifiée (protégée par secret Bearer) -------------
@app.api_route("/api/sync", methods=["GET", "POST"])
async def api_sync(request: Request):
    """Endpoint appelé par le cron Vercel (GET) — protégé par CRON_SECRET.

    Vercel envoie l'en-tête ``Authorization: Bearer <CRON_SECRET>`` dès lors que
    la variable ``CRON_SECRET`` est définie. Si elle ne l'est pas (dev), la
    route n'est pas protégée.
    """
    if config.CRON_SECRET:
        expected = f"Bearer {config.CRON_SECRET}"
        received = request.headers.get("authorization", "")
        if not hmac.compare_digest(received, expected):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
    # run_sync est bloquant (HTTP + base) : on l'exécute hors de la boucle asyncio.
    result = await run_in_threadpool(run_sync)
    status = 200 if result.get("status") == "ok" else 500
    return JSONResponse(result, status_code=status)


# --- Administration : import du fichier Excel (source du mode réel) ----
@app.get("/admin/upload", response_class=HTMLResponse)
def admin_upload_form(request: Request):
    """Page d'import : drag & drop du classeur + historique des imports."""
    info = _safe(excel_store.active_info)
    hist = _safe(excel_store.history, default=[]) or []
    return templates.TemplateResponse(
        request, "admin_upload.html",
        {"active": info, "history": hist, "staged": None, "error": None, "message": None},
    )


@app.post("/admin/upload", response_class=HTMLResponse)
async def admin_upload(request: Request, fichier: UploadFile = File(...)):
    """Étape 1 : upload -> validation -> diff -> écran de confirmation.

    On ne touche PAS aux données en place : le fichier validé est mis en attente
    (table import_staging) et l'utilisateur doit confirmer pour l'activer.
    """
    content = await fichier.read()
    if not content:
        return _admin_error(request, "Fichier vide.")
    if len(content) > _MAX_UPLOAD_BYTES:
        return _admin_error(request, "Fichier trop volumineux (max 10 Mo).")

    # Parsing + validation stricte (hors boucle asyncio : openpyxl est bloquant).
    try:
        dashboard, tables = await run_in_threadpool(
            excel_source.parse_and_validate, content)
    except excel_source.ExcelValidationError as exc:
        return _admin_error(request, "Le fichier comporte des erreurs :",
                            details=exc.errors)
    except Exception as exc:  # noqa: BLE001
        return _admin_error(request, f"Erreur inattendue : {type(exc).__name__} — {exc}")

    # Mise en attente + calcul du diff vs version active.
    token = secrets.token_urlsafe(24)
    diff = _safe(excel_store.compute_diff, dashboard, default={}) or {}
    volum = excel_source.volumetrie(tables)
    try:
        excel_store.stage_import(
            dashboard, token=token, filename=fichier.filename or "import.xlsx",
            file_hash=excel_source.file_hash(content), volumetrie=volum, diff=diff)
    except Exception as exc:  # noqa: BLE001
        return _admin_error(request, f"Base indisponible : {type(exc).__name__} — {exc}")

    return templates.TemplateResponse(
        request, "admin_upload.html",
        {"active": _safe(excel_store.active_info),
         "history": _safe(excel_store.history, default=[]) or [],
         "staged": {"token": token, "filename": fichier.filename,
                    "diff": diff, "volumetrie": volum},
         "error": None, "message": None},
    )


@app.post("/admin/confirm", response_class=HTMLResponse)
def admin_confirm(request: Request, token: str = Form(...)):
    """Étape 2 : l'utilisateur confirme -> activation (transactionnelle)."""
    staged = _safe(excel_store.get_staged, token)
    if not staged:
        return _admin_error(request, "Import expiré ou introuvable. Recommencez.")
    try:
        excel_store.save_import(
            staged["dashboard"], filename=staged["filename"],
            file_hash=staged["file_hash"], volumetrie=staged["volumetrie"],
            author=_client_ip(request))
        excel_store.clear_staged(token)
    except Exception as exc:  # noqa: BLE001
        return _admin_error(request, f"Échec de l'écriture : {type(exc).__name__} — {exc}")
    return _admin_message(
        request, f"Import confirmé : le mode réel affiche désormais les données "
        f"au {staged['date_maj']}.")


@app.post("/admin/cancel", response_class=HTMLResponse)
def admin_cancel(request: Request, token: str = Form(...)):
    """Abandon d'un import en attente (aucune donnée en place n'a bougé)."""
    _safe(excel_store.clear_staged, token)
    return _admin_message(request, "Import annulé. Aucune donnée n'a été modifiée.")


@app.post("/admin/rollback", response_class=HTMLResponse)
def admin_rollback(request: Request):
    """Réactive l'import précédent (annulation du dernier import confirmé)."""
    restored = _safe(excel_store.rollback)
    if not restored:
        return _admin_error(request, "Rien à annuler (un seul import ou aucun).")
    return _admin_message(
        request, f"Retour à l'import précédent : {restored.get('filename', '')} "
        f"(données au {restored.get('date_maj', '?')}).")


# --- Helpers admin ------------------------------------------------------
def _safe(fn, *args, default=None):
    """Appelle une fonction du store en absorbant une base indisponible."""
    try:
        return fn(*args)
    except Exception:  # noqa: BLE001
        return default


def _admin_error(request: Request, message: str, details: list | None = None):
    return templates.TemplateResponse(
        request, "admin_upload.html",
        {"active": _safe(excel_store.active_info),
         "history": _safe(excel_store.history, default=[]) or [],
         "staged": None, "error": message, "error_details": details, "message": None},
        status_code=400,
    )


def _admin_message(request: Request, message: str):
    return templates.TemplateResponse(
        request, "admin_upload.html",
        {"active": _safe(excel_store.active_info),
         "history": _safe(excel_store.history, default=[]) or [],
         "staged": None, "error": None, "message": message},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=config.APP_PORT)
