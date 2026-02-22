# Operator Setup

## 1) Prepare environment

Copy `.env.example` to `.env` and set values.

Required before first startup:

- Tailnet identity:
  - `MATRIX_SERVER_NAME`
  - `PUBLIC_BASEURL`
  - `TURN_REALM`
- Admin bootstrap:
  - `BOOTSTRAP_ADMIN_EMAIL`
  - `BOOTSTRAP_ADMIN_PASSWORD`
  - `BOOTSTRAP_ADMIN_LOCALPART`
- Secrets (`CHANGE_ME_*` values)
- SMTP settings (`SMTP_*`) for self-service password reset

### Choosing `MATRIX_SERVER_NAME`, `PUBLIC_BASEURL`, and `TURN_REALM`

- Use your Tailscale node MagicDNS hostname as `MATRIX_SERVER_NAME` (example: `host.tailxxxx.ts.net`).
- Set `PUBLIC_BASEURL` to `https://` plus that same hostname.
- Set `TURN_REALM` to that same hostname as well.
- You can find the hostname in the Tailscale admin UI (Machines list) or on the host with:

```bash
tailscale status --self
```

- Keep all three aligned to avoid call/sign-in edge cases caused by host/realm mismatches.

## 2) Start stack

```bash
docker compose up -d
```

This launches:

- `config-renderer` to generate runtime config files.
- `synapse`, `postgres`, `coturn`, `element`, `web`.
- `matrix-bootstrap` to create baseline space/rooms.
- `admin-api` + `admin-ui`.
- `livekit` + `element-call`.

## 3) Configure Tailscale Serve

Expose local services to tailnet users:

- Matrix/Element (`ELEMENT_HTTP_PORT`)
- Element Call (`ELEMENT_CALL_HTTP_PORT`)
- Admin UI (`ADMIN_UI_HTTP_PORT`) only for trusted admins

## 4) Registration model

- Open registration is disabled by token requirement.
- Create invite tokens via Admin UI.
- Default token is also created during bootstrap (`data/bootstrap/bootstrap-state.json`).

## 5) Retention policy

Defaults to indefinite retention.

- `RETENTION_MODE=indefinite` keeps retention disabled.
- `RETENTION_MODE=limited` enables retention with:
  - `RETENTION_MESSAGE_MAX_DAYS`
  - `RETENTION_PURGE_INTERVAL_HOURS`

## 6) Backups

Backup these paths regularly:

- `data/postgres/`
- `runtime/synapse/` (contains signing key and server state)
- `data/bootstrap/`
- `data/admin-api/`

## 7) Upgrades

```bash
docker compose pull
docker compose up -d
```

If Synapse schema migrations are needed, Synapse will handle them on startup.
