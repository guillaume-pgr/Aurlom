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
from datetime import datetime, timedelta

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool
from starlette.middleware.sessions import SessionMiddleware

import auth
import config
import db
from datasource import get_dashboard_data
from sync import run_sync

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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=config.APP_PORT)
