# Operator Setup

## 1) Prepare environment

Copy `.env.example` to `.env` and set values.

Required before first startup:

- Tailnet identity:
  - `MATRIX_SERVER_NAME`
  - `PUBLIC_BASEURL`
  - `ELEMENT_CALL_URL`
  - `LIVEKIT_NODE_IP`
  - `TURN_REALM`
- Admin bootstrap:
  - `BOOTSTRAP_ADMIN_EMAIL`
  - `BOOTSTRAP_ADMIN_PASSWORD`
  - `BOOTSTRAP_ADMIN_LOCALPART`
  - `BOOTSTRAP_SPACE_NAME`
  - `BOOTSTRAP_SPACE_ALIAS`
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
- Set `ELEMENT_CALL_URL` to your Element Call Serve URL (for example `https://host.tailxxxx.ts.net:8443`).
- Set `LIVEKIT_NODE_IP` to the host's Tailscale IPv4 from `tailscale ip -4`.
- Optional: set `MATRIX_RTC_LIVEKIT_SERVICE_URL` if your LiveKit JWT endpoint is not `${ELEMENT_CALL_URL}/livekit/jwt`.
- LiveKit media is configured tailnet-only in this repo (advertises `LIVEKIT_NODE_IP` only), so participants must be connected to Tailscale for calls.

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

LiveKit runs with host networking in this stack so ICE/media binds directly on host ports (`7881/tcp`, `50000-50100/udp`). Ensure those ports are available on the host.

## 3) Configure Tailscale Serve

Tailscale Serve proxies localhost HTTP ports onto your tailnet with automatic
HTTPS certificate provisioning. Each command below maps a local service to an
HTTPS port on your node's MagicDNS hostname (`MATRIX_SERVER_NAME`).

Port values below match `.env.example` defaults; adjust if you changed them.

**Matrix + Element Web** (serves Synapse API and Element frontend):

```bash
tailscale serve --bg --https=443 http://127.0.0.1:8088
```

**Element Call** (video/voice calling UI):

```bash
tailscale serve --bg --https=8443 http://127.0.0.1:8089
```

**Admin UI** (restrict access to trusted operators):

```bash
tailscale serve --bg --https=8444 http://127.0.0.1:8090
```

Verify the routes are active:

```bash
tailscale serve status
```

> **Persistence:** Tailscale Serve rules created with `--bg` persist across
> reboots on Tailscale v1.56+. If you are running an older version, see the
> [Tailscale Serve docs](https://tailscale.com/kb/1312/serve) for alternative
> approaches.

> **Access control:** The Admin UI should only be reachable by trusted admins.
> Consider using [Tailscale ACLs](https://tailscale.com/kb/1018/acls) to
> restrict which tailnet users can reach the admin ports.

The Admin UI dashboard includes a **Self-Hosting Health** panel (admin-only)
that validates MatrixRTC/LiveKit routing and key self-hosting posture checks.

## 4) Registration model

- Open registration is disabled by token requirement.
- Create invite tokens via Admin UI.
- Default token is also created during bootstrap (`data/bootstrap/bootstrap-state.json`).
- New users auto-join room aliases in `AUTO_JOIN_ROOMS`.
- The root Space alias `#${BOOTSTRAP_SPACE_ALIAS}:${MATRIX_SERVER_NAME}` is automatically appended to `AUTO_JOIN_ROOMS` during config rendering, so new users also land in the Space sidebar.

### Space naming and aliasing

- `BOOTSTRAP_SPACE_NAME` controls the display name users see in Element.
- `BOOTSTRAP_SPACE_ALIAS` controls the root Space alias slug (`#<alias>:<server>`).
- Updating either value is safe on existing deployments; rerun `config-renderer` and `matrix-bootstrap` (or `docker compose up -d --force-recreate`) to apply changes.

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
