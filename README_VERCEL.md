# Déploiement Vercel — Dashboard direction Aurlom

Guide complet pour publier le dashboard sur une **URL publique gratuite**,
protégée par un **mot de passe partagé**, avec base de données **Turso**
(serverless) et **synchronisation quotidienne** via cron Vercel.

> L'application conserve son **mode dev local** (uvicorn + `.env`, base SQLite
> fichier) : aucune régression. Le backend Turso ne s'active que si
> `TURSO_DATABASE_URL` est défini.

---

## Vue d'ensemble de l'architecture

| Élément                | Rôle                                                                     |
|------------------------|--------------------------------------------------------------------------|
| `api/index.py`         | Point d'entrée Vercel : expose l'app FastAPI (ASGI natif, sans Mangum).  |
| `vercel.json`          | Build Python + routing global + cron quotidien (6h UTC).                 |
| `db.py`                | Double backend : **SQLite** (dev) / **Turso libsql** (prod) — même API.  |
| `migrate_to_turso.py`  | Script one-shot : crée le schéma des tables sur Turso.                   |
| `auth.py`              | Auth mot de passe partagé (bcrypt + cookie signé itsdangerous, 30 j).    |
| `main.py`              | Middleware d'auth + routes `/login`, `/logout`, `/api/sync` (cron).      |

En développement (aucune variable Turso), tout continue de tourner sur SQLite
local, exactement comme avant.

---

## Prérequis

- Un compte **[Vercel](https://vercel.com)** (gratuit).
- Un compte **[Turso](https://turso.tech)** (gratuit).
- **Node.js** (pour le CLI Vercel) et **Python 3.11+**.
- Le CLI Vercel : `npm i -g vercel`.
- Le CLI Turso : voir <https://docs.turso.tech/cli/installation>.

---

## 1. Créer la base Turso

```bash
# Connexion
turso auth login

# Création de la base (choisissez un nom, ex : dashboard-aurlom)
turso db create dashboard-aurlom

# Récupérer l'URL de connexion (libsql://…)
turso db show dashboard-aurlom --url

# Générer un token d'accès
turso db tokens create dashboard-aurlom
```

Notez les deux valeurs obtenues :

- `TURSO_DATABASE_URL` = l'URL `libsql://dashboard-aurlom-<org>.turso.io`
- `TURSO_AUTH_TOKEN`   = le token généré

### Créer le schéma des tables

En local, dans un `.env` temporaire (ou en variables d'environnement),
renseignez au minimum `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN` **et** les
variables `FULLL_*` existantes (le module `config` les exige à l'import), puis :

```powershell
pip install -r requirements.txt
python migrate_to_turso.py
```

Sortie attendue :

```
Connexion à Turso : libsql://dashboard-aurlom-....turso.io
Tables présentes : accounts, entries, login_attempts, sync_log
[OK] Schéma Turso prêt.
```

---

## 2. Générer le hash bcrypt du mot de passe

Le mot de passe n'est **jamais** stocké en clair : seul son hash bcrypt est mis
en variable d'environnement.

```powershell
python -c "import bcrypt; print(bcrypt.hashpw(b'VotreMotDePasse', bcrypt.gensalt()).decode())"
```

Copiez la chaîne obtenue (commence par `$2b$…`) : ce sera
`DASHBOARD_PASSWORD_HASH`.

> ⚠️ Sous PowerShell, si le mot de passe contient des caractères spéciaux,
> préférez générer le hash dans un shell où l'échappement est maîtrisé.

### Générer les secrets de session et de cron

```powershell
# Clé de signature des cookies (SESSION_SECRET)
python -c "import secrets; print(secrets.token_urlsafe(48))"

# Secret du cron (CRON_SECRET)
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## 3. Lier le projet et configurer les variables d'environnement

Depuis la racine `C:\DEV\Dashboard_compta` :

```bash
vercel link      # crée/associe le projet Vercel (répondez aux questions)
```

Ajoutez ensuite **chaque** variable en environnement `production` (le CLI
demande la valeur puis les environnements ciblés) :

```bash
# API fulll (mêmes valeurs que votre .env local)
vercel env add FULLL_CLIENT_ID production
vercel env add FULLL_CLIENT_SECRET production
vercel env add FULLL_ACCESS_TOKEN production
vercel env add FULLL_REFRESH_TOKEN production
vercel env add FULLL_BASE_URL production
vercel env add APP_MODE production          # 'demo' ou 'real'

# Base Turso
vercel env add TURSO_DATABASE_URL production
vercel env add TURSO_AUTH_TOKEN production

# Authentification & session
vercel env add DASHBOARD_PASSWORD_HASH production
vercel env add SESSION_SECRET production

# Sécurité du cron
vercel env add CRON_SECRET production
```

> `CRON_SECRET` : Vercel réinjecte automatiquement cette variable dans
> l'en-tête `Authorization: Bearer <CRON_SECRET>` lors du déclenchement du
> cron. Aucune configuration supplémentaire côté cron n'est nécessaire.

Liste récapitulative des variables (à **ne jamais commiter**) :

| Variable                  | Description                                             |
|---------------------------|--------------------------------------------------------|
| `FULLL_CLIENT_ID`         | Identifiant client API fulll.                          |
| `FULLL_CLIENT_SECRET`     | Secret client API fulll.                               |
| `FULLL_ACCESS_TOKEN`      | Access token initial.                                  |
| `FULLL_REFRESH_TOKEN`     | Refresh token initial.                                 |
| `FULLL_BASE_URL`          | Ex. `https://api.fulll.io/accounting/v1`.              |
| `APP_MODE`                | `demo` ou `real`.                                      |
| `TURSO_DATABASE_URL`      | URL libsql de la base Turso.                           |
| `TURSO_AUTH_TOKEN`        | Token d'accès Turso.                                   |
| `DASHBOARD_PASSWORD_HASH` | Hash bcrypt du mot de passe partagé.                   |
| `SESSION_SECRET`          | Clé de signature des cookies de session.               |
| `CRON_SECRET`             | Secret protégeant `POST /api/sync` (Bearer).           |

> `APP_PORT` et `DB_PATH` ne servent qu'en local ; inutile sur Vercel.

---

## 4. Déployer

```bash
vercel --prod
```

Vercel renvoie l'URL publique (ex. `https://dashboard-aurlom.vercel.app`).

---

## 5. Tests

### Login

1. Ouvrez l'URL : vous êtes redirigé vers `/login`.
2. Un mauvais mot de passe → message « Mot de passe incorrect ».
3. Après **5 échecs en 10 min** depuis la même IP → « Trop de tentatives… ».
4. Le bon mot de passe → accès au dashboard ; le cookie reste valable 30 jours.
5. `/logout` supprime le cookie et renvoie vers `/login`.

### Sonde de santé (publique)

```bash
curl https://<votre-app>.vercel.app/health
# {"status":"ok","mode_default":"..."}
```

### Cron / synchro manuelle

Le cron s'exécute chaque jour à **6h00 UTC** (`0 6 * * *`). Pour tester
manuellement l'endpoint protégé :

```bash
# Sans le bon secret -> 401
curl -X POST https://<votre-app>.vercel.app/api/sync

# Avec le secret -> lance la synchro et renvoie le récap JSON
curl -X POST https://<votre-app>.vercel.app/api/sync \
  -H "Authorization: Bearer <CRON_SECRET>"
```

Vous pouvez aussi déclencher le cron depuis le dashboard Vercel
(*Project → Cron Jobs → Run*), ou utiliser le bouton **Synchroniser** de l'UI
(route `/sync`, protégée par le cookie de session).

---

## Développement local (inchangé)

Sans variables Turso, l'app utilise SQLite fichier comme avant :

```powershell
cd C:\DEV\Dashboard_compta
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8501
```

- Sans `DASHBOARD_PASSWORD_HASH` dans le `.env` local, **l'authentification est
  désactivée** (accès direct au dashboard) — pratique pour développer.
- Pour tester l'auth en local, ajoutez `DASHBOARD_PASSWORD_HASH` et
  `SESSION_SECRET` à votre `.env`. Le cookie fonctionne en `http://localhost`
  (drapeau `Secure` posé uniquement en HTTPS).

---

## Notes techniques

- **Base serverless** : le backend Turso utilise `libsql-client` en mode
  synchrone via transport HTTP (`libsql://` → `https://`), sans état, adapté à
  l'exécution éphémère des fonctions Vercel. Le client est réutilisé entre
  invocations « chaudes ».
- **Tokens fulll** : sur Vercel, le système de fichiers est en lecture seule
  sauf `/tmp`. Le cache de tokens rafraîchis (`.tokens.json`) est
  automatiquement déporté dans `/tmp` (détection via la variable `VERCEL`).
  Attention : `/tmp` n'est pas garanti persistant entre invocations — le
  refresh fonctionne mais le cache peut être régénéré.
- **Cookies de session** : `HttpOnly`, `SameSite=Lax`, `Secure` en HTTPS, jeton
  signé (itsdangerous) horodaté, expiration 30 jours. La clé `SESSION_SECRET`
  doit rester stable pour ne pas invalider les sessions.
- **Rate limiting** : table `login_attempts` (5 tentatives / 10 min par IP).
