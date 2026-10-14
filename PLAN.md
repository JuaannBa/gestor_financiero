# PLAN.md — Gestor Financiero

Multi-user personal finance manager. Django backend + React SPA, developed to production quality but **hosted 100% free, locally, on the home network**. Doubles as a portfolio project for job hunting.

- **Timeline:** ~6 weeks part-time, phase-based with Definition of Done per phase
- **UI language:** English
- **Access:** `http://<lan-ip>` from any device on the home network (no cloud, no internet exposure)

---

## 1. Locked-in decisions

| Area | Choice |
|---|---|
| Backend | Django 6.0/6.1 + DRF 3.17+ (Python 3.14 compatible), django-filter, drf-spectacular |
| Auth | SimpleJWT (access + refresh with rotation + blacklist), email-based custom User |
| Frontend | React 19 + TypeScript + Vite, React Router, TanStack Query, Tailwind CSS, Recharts, react-hook-form + Zod |
| Database | PostgreSQL 17 (Docker container), Decimal money, DB-level constraints |
| Web server | nginx (single origin: static frontend + `/api/` proxy → Gunicorn), no CORS in prod |
| Scheduler | Cron sidecar container running `generate_recurring` management command |
| Deployment | Docker Compose "production" stack on own machine, LAN access, free forever |
| CI | GitHub Actions on a public repo (free for public repos) |
| Repo | Monorepo: `backend/` + `frontend/` |
| Audience | Multi-user SaaS-style: signup/login, strict per-user data isolation |

## 2. Repository layout

```
gestor_financiero/
├── PLAN.md
├── backend/
│   ├── manage.py
│   ├── pyproject.toml            # ruff, pytest-django, coverage config
│   ├── Dockerfile                # multi-stage, non-root
│   ├── config/                   # settings/base.py, dev.py, prod.py; urls.py; wsgi/asgi
│   └── apps/
│       ├── users/                # custom email User, JWT auth endpoints
│       ├── accounts/             # bank accounts
│       ├── ledger/               # categories, transactions, transfers, recurrences
│       ├── budgets/              # monthly budgets
│       ├── imports/              # CSV upload → preview → commit
│       └── reports/              # dashboard/aggregation endpoints
├── frontend/
│   ├── Dockerfile                # build stage → nginx
│   └── src/
│       ├── api/                  # typed client, TanStack Query hooks
│       ├── features/             # auth, accounts, transactions, budgets, dashboard, import
│       ├── components/           # shared UI (tables, dialogs, charts)
│       └── routes/               # router + protected routes
├── docker-compose.yml            # dev: db + backend + frontend (Vite)
├── docker-compose.prod.yml       # prod: nginx + backend + db + cron sidecar
├── .github/workflows/ci.yml
├── .env.example
└── README.md                     # portfolio-facing
```

## 3. Data model

- **User** — custom model, `email` as identifier (unique), password validation. Custom user model decided on day 1 (changing `AUTH_USER_MODEL` later is painful).
- **Account** — name, type (`checking|savings|credit|cash`), currency (EUR default), opening balance, `is_archived`. Running balance is **derived** (opening balance ± SUM of transactions), never stored — always correct after edits, no reconciliation bugs.
- **Category** — user-scoped, self-FK for nesting (`parent`), kind (`income|expense`), icon/color. `seed_defaults` management command creates a default tree per new user.
- **Transaction** — account FK, `type` (`income|expense|transfer`), `amount` (`Decimal`, `>= 0` via DB check constraint; sign lives in `type`), date, payee, category (nullable), notes. Transfers are **two linked rows** sharing a `transfer_group` UUID so every account statement stays uniform.
- **Recurrence** — template on a transaction (daily/weekly/monthly/yearly), materialized by `generate_recurring` management command on cron. No Celery/Redis in MVP (would add a broker + extra process + cost/complexity for one job).
- **Budget** — user + category + `year` + `month` + amount; unique together.
- **ImportBatch** — uploaded file, column mapping, status, SHA-256 dedup fingerprint (account+date+amount+payee) so re-imports are idempotent.

Multi-tenancy: querysets scoped with `filter(user=request.user)` at the view layer (no django-guardian needed — every object has exactly one owner), plus tests asserting 404 on other users' objects.

## 4. API surface (`/api/v1/`)

- `auth/`: `register`, `login`, `refresh`, `logout`, `me` — JWT with rotation/blacklist, throttling on auth endpoints
- `accounts/`, `categories/`, `budgets/` — DRF ViewSets + router (CRUD)
- `transactions/` — CRUD + filters: date range, account, category, type, payee search; pagination
- `reports/dashboard/` — net worth series, month income/expense, spend by category, budget vs actual — computed with DB aggregates/annotations, never Python loops
- `imports/csv/`: `upload` → `preview` (mapped rows + validation errors) → `commit` (dedup on fingerprint)
- `schema/` + `docs/` — drf-spectacular OpenAPI + Swagger UI (public portfolio artifact)

## 5. Phases

### Phase 0 — Environment & repo (½ day)
Install `nvm` → Node 22 LTS; install Docker Engine + Compose plugin. `git init`, public GitHub repo, `.gitignore`, `.env.example`, README skeleton.
**DoD:** `docker compose up db` healthy; empty repo pushed; CI badge visible.

### Phase 1 — Backend foundation (2–3 days)
Django project + app skeleton; settings split (base/dev/prod) via `django-environ`; DRF registered; drf-spectacular; ruff + pytest-django + factory_boy; dev `docker-compose.yml`; **GitHub Actions CI** (ruff + pytest on push).
**DoD:** `/api/v1/schema/` renders; `pytest` green in CI.

### Phase 2 — Auth & users (2 days)
Custom `User`; register/login/refresh/logout/me with SimpleJWT (rotation + blacklist); password rules; throttling; ownership-isolation tests.
**DoD:** full auth flow tested; JWT works from Swagger UI.

### Phase 3 — Core ledger API (4–5 days)
Accounts, categories (+ seed command), transactions incl. transfers, budgets, recurrence command, dashboard/report endpoints. Exhaustive API tests, coverage ≥ 80%.
**DoD:** seed script produces data; dashboard endpoint returns real aggregates.

### Phase 4 — CSV import (2–3 days)
Upload → parse (column mapping) → preview endpoint with row validation → commit with dedup. European formats supported (`1.234,56`, `DD/MM/YYYY`). Fixture CSVs in tests.
**DoD:** importing the same file twice creates no duplicates.

### Phase 5 — Frontend foundation (3–4 days)
Vite + React + TS (strict) + Tailwind; router with protected routes; auth feature (login/register, token-refresh interceptor, logout); TanStack Query; typed API client; layout shell; ESLint + Prettier + Vitest.
**DoD:** signup → login → authenticated empty dashboard against local API.

### Phase 6 — Frontend features (5–6 days)
Accounts CRUD; transactions table (date filters, search, category chips, add/edit drawer, transfer form); categories manager; budgets with progress bars; dashboard with Recharts (balance over time, income vs expense, category donut, budget vs actual); CSV import wizard (upload → map → preview → commit).
**DoD:** every backend feature usable through the UI; component tests for critical flows.

### Phase 7 — Local production hardening (3–4 days)
Multi-stage Dockerfiles (non-root, frontend builds → nginx serves static + proxies `/api/`); `docker-compose.prod.yml`; `prod.py` (`DEBUG=False`, security headers, trusted hosts/CSRF for LAN IP, stdout logging, connection reuse); `/healthz`; `collectstatic`; `migrate` before app start (compose healthcheck ordering).
**DoD:** full stack runs from images at `http://<lan-ip>` with `DEBUG=False`.

### Phase 8 — LAN access & ops (1–2 days)
Firewall rule (ufw, LAN subnet only, port 80); `restart: unless-stopped` + Docker enabled on boot (stack survives reboot); backup job (`pg_dump` → dated local folder on cron, keep last N); log rotation.
**DoD:** phone reaches the app over home Wi-Fi; backup restores cleanly into a fresh container.

### Phase 9 — Portfolio polish (2–3 days)
README: badges (CI, coverage), architecture diagram, screenshots/demo GIFs, 10-minute run guide for recruiters, tech rationale; public Swagger UI docs; `seed_demo` command; LICENSE; "future work" section.
**DoD:** a stranger clones the repo, runs 2 commands, sees a populated app.

## 6. Cross-cutting standards

- **Money:** always `Decimal`/`NUMERIC(12,2)`, never floats (backend and frontend).
- **Tests:** pytest API tests per endpoint incl. auth + isolation; Vitest for auth, transactions table, import wizard.
- **Quality gates enforced in CI:** `ruff check` + `ruff format --check`, `tsc --noEmit`, coverage ≥ 80%.
- **Security:** no secrets in repo (`.env.example` only); object-level scoping verified by tests; auth throttling; LAN-only firewall; no internet exposure.

## 7. Key decisions & trade-offs

**Why these choices**
- **Django 6.0 + DRF 3.17:** first versions officially supporting Python 3.14 (the installed interpreter).
- **JWT over sessions:** standard for SPA APIs, avoids cross-origin CSRF plumbing; rotation+blacklist keeps logout safe.
- **Postgres everywhere (dev and prod):** SQLite locally would cause "works locally, breaks in prod" divergence.
- **Derived balances + two-row transfers:** correctness by construction; mirrors how accounting software models ledgers.
- **No Celery:** one background job (recurrence) runs on a cron sidecar — no broker, no extra cost/ops.
- **Single-origin nginx:** static frontend + API behind one origin removes CORS entirely from production.
- **CI from day 1:** every phase lands behind a green check instead of writing tests retroactively.
- **Backend fully before frontend:** the API is the contract; Swagger UI stays usable for testing throughout.
- **Deploy at Phase 8, polish last:** if time runs short, the priority order is working deployed app > docs.

**Accepted trade-offs (local/free constraints)**
1. **HTTP only on LAN** — no encryption between home devices; acceptable on trusted Wi-Fi. The app is firewalled to the LAN subnet and never exposed to the internet (so no HSTS/domain/cert needed).
2. **Your PC is production** — down when it's off; no HA/autoscaling; irrelevant for one user.
3. **Local-only backups** — disaster recovery = local/external drive copy; nothing offsite.
4. **No live demo URL for recruiters** — mitigated by screenshots, demo GIFs, seedable demo data, and public Swagger docs they can run locally.
5. **No cloud monitoring** — Docker stdout logging + log rotation instead of Sentry.

**Free-forever audit:** Docker, all Python/JS dependencies, GitHub Actions (public repos), Postgres, nginx — nothing in this plan ever bills.

## 8. Risks

1. **Node & Docker not installed** on this machine — Phase 0 installs both (Docker needs sudo).
2. **Version drift** — pin Django 6.0.x/6.1 and DRF ≥ 3.17; lock dependencies.
3. **Cron sidecar quirks** — fallback: materialize recurrences lazily when a date range is queried.
4. **Scope creep** (goals, investments, FX, bank APIs) — deferred explicitly to "future work" so the project reaches its finished state.

## 9. Future work (post-v1)

Multi-currency with FX rates, savings goals, investment tracking, bank CSV/API integrations, notifications, HTTPS via `mkcert` on LAN, offsite backups, optional cloud deployment (Docker images are portable).
