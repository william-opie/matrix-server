# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A Docker Compose-based self-hosted Matrix stack for private Tailscale environments. Primary components:

- **Synapse** — Matrix homeserver (PostgreSQL backend)
- **Element Web** — web client served via nginx
- **Element Call** — self-hosted group calls via LiveKit
- **coturn** — TURN server for 1:1 VoIP
- **admin-api/** — FastAPI service that wraps Synapse admin APIs behind JWT auth
- **admin-ui/** — static HTML/JS/CSS admin frontend served by nginx
- **scripts/** — config rendering and bootstrap automation
- **config/** — template files rendered into `runtime/` at startup
- **runtime/** — generated output; do not hand-edit

## Commands

### Docker Compose (primary workflow)

```bash
cp .env.example .env          # first-time setup; fill required values
docker compose up -d          # start full stack (triggers config-renderer → postgres → synapse → bootstrap)
docker compose up -d --force-recreate  # apply config changes
docker compose down
docker compose logs -f synapse
docker compose logs -f admin-api
docker compose run --rm config-renderer   # render runtime/ configs only
docker compose run --rm matrix-bootstrap  # run bootstrap only
```

### Local development (Admin API)

```bash
python -m pip install -r admin-api/requirements.txt
# Run from repo root:
uvicorn admin-api.app.main:app --host 127.0.0.1 --port 9000
# Or from admin-api/:
uvicorn app.main:app --host 127.0.0.1 --port 9000
```

### Scripts

```bash
python scripts/render_configs.py    # render config templates to runtime/
python scripts/bootstrap_matrix.py  # idempotent bootstrap (needs Synapse running)
```

### Syntax checks (no linter/formatter is configured)

```bash
python -m py_compile scripts/render_configs.py scripts/bootstrap_matrix.py admin-api/app/main.py
python -m compileall scripts admin-api/app
```

### Smoke checks

```bash
curl http://127.0.0.1:9000/api/health
docker compose ps
docker compose logs --tail=100 admin-api
```

### No test suite is present

If tests are added, use pytest conventions:
```bash
pytest                                        # all tests
pytest tests/test_file.py                     # one file
pytest tests/test_file.py::test_case_name     # one test
```

## Architecture

### Startup sequence

Docker Compose service dependencies enforce this order:
1. `config-renderer` renders all `config/**/*.template` files into `runtime/` using Python `string.Template.safe_substitute`. Also writes `runtime/bootstrap/meta.json`.
2. `postgres` starts (health-checked).
3. `synapse` starts (health-checked on `/_matrix/client/v3/health`).
4. `matrix-bootstrap` registers the admin user (via Synapse shared-secret API), creates the default Space + rooms, sets up a default invite token, and writes state to `data/bootstrap/bootstrap-state.json`. It is idempotent.
5. `admin-api` starts and installs its own dependencies at container start time.

### Config templating

- Templates live in `config/` and use `${VAR}` substitution syntax (`string.Template`).
- `scripts/render_configs.py` reads `.env` then merges OS environment overrides.
- All rendered output goes to `runtime/` and is mounted read-only into containers.
- Special computed values: `AUTO_JOIN_ROOMS_YAML`, `RETENTION_BLOCK`, auto-derived `MATRIX_RTC_LIVEKIT_SERVICE_URL` and `LIVEKIT_SFU_URL` if not set.

### Admin API (`admin-api/app/main.py`)

Single-file FastAPI application. Key design points:

- **Auth**: JWT HS256 signed with `ADMIN_AUTH_SECRET` (must be ≥32 chars or startup fails). Admin users stored in SQLite at `/data/admin.db` (separate from Matrix users). The bootstrap admin email/password seeds the SQLite DB on first startup.
- **Synapse proxy**: All Synapse admin calls go through `synapse_admin()`, which authenticates per-request using `BOOTSTRAP_ADMIN_PASSWORD` to get a Matrix access token. No token is cached.
- **Audit log**: Every admin action is written to the `audit_logs` SQLite table.
- **Self-hosting health check** (`GET /api/self-hosting/health`): reads runtime config files and checks internal service reachability to verify correct configuration.
- Dependencies: `fastapi`, `uvicorn`, `bcrypt`, `PyJWT` (see `admin-api/requirements.txt`).

### Network topology

- All services except `livekit` are on the `matrix` Docker bridge network.
- `livekit` uses `network_mode: host` so ICE/media binds to host interfaces. `LIVEKIT_NODE_IP` must be the Tailscale IPv6 address.
- `element-call-web` (nginx) proxies `/livekit/jwt/*` → `matrix-livekit-jwt:8080` and `/livekit/sfu/*` → `host.docker.internal:7880`.
- Redis is bound to `127.0.0.1:6379` so host-networked LiveKit can connect.
- Web-facing ports are bound to `127.0.0.1` and exposed via Tailscale Serve (not public internet).

### Admin UI

Static `admin-ui/index.html` + `admin-ui/app.js` + `admin-ui/styles.css`. Talks to the Admin API via `/api/` (proxied through the admin-ui nginx). No build step; served directly by nginx from the mounted directory.

## Key conventions

- `runtime/` is gitignored generated output — never commit hand-edits.
- `data/` holds persistent volumes (postgres, redis, bootstrap state, admin SQLite). Do not delete while the stack is running.
- All `CHANGE_ME_*` values in `.env.example` are placeholders — never use them in production.
- `ADMIN_AUTH_SECRET` must be ≥32 characters; the API refuses to start otherwise.
- Bootstrap is idempotent: re-running it is safe. State is tracked in `data/bootstrap/bootstrap-state.json`.
- The `video` room gets special power-level configuration to allow Element Call MSC events at level 0.

## More detailed guidance

See `AGENTS.md` for code style guidelines (Python, JS/CSS/HTML), security rules, and agent workflow expectations.
