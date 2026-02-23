# Matrix Server

Self-hosted Matrix stack designed for private Tailscale environments, with invite-token onboarding, SMTP self-service password resets, default Space/room bootstrap, Element Call, and an internal admin panel.
This is intended to be used as a self-hosted Discord alternative.

## What this repository provides

- Synapse + PostgreSQL + coturn + Element Web in Docker Compose.
- Tailnet-only deployment model (no public federation).
- Invite-token registration flow and automatic room onboarding.
- SMTP password reset support.
- Element Call self-hosted stack (LiveKit-based).
- Admin API + frontend for common Synapse admin actions.
- Config templating from `.env` so this repo is easy to share.

## Prerequisites

- **Docker** and **Docker Compose** (v2) installed on the host.
- **Tailscale** installed, authenticated, and connected to your tailnet.
- Host ports available for LiveKit media: `7881/tcp` and `50000-50100/udp`. LiveKit runs with host networking, so these must not be in use by other services.

## Quick start

1. Copy `.env.example` to `.env`.
2. **Before first startup**, set your Tailnet hostname details and admin credentials in `.env`:
   - `MATRIX_SERVER_NAME` — your Tailscale MagicDNS hostname (e.g. `host.tailnet.ts.net`).
   - `PUBLIC_BASEURL` — `https://` + the same hostname.
   - `ELEMENT_CALL_URL` — your Element Call URL (e.g. `https://host.tailnet.ts.net:8443`).
   - `LIVEKIT_NODE_IP` — your host's Tailscale IPv6 address (run `tailscale ip -6`).
   - `TURN_REALM` — same hostname as `MATRIX_SERVER_NAME`.
   - `BOOTSTRAP_ADMIN_EMAIL` and `BOOTSTRAP_ADMIN_PASSWORD`.
   - *(Optional)* Set `SMTP_HOST`, `SMTP_USER`, `SMTP_PASS`, and related SMTP variables if you want self-service password resets.
3. Replace all `CHANGE_ME_*` values with strong secrets.
4. Start the stack:

```bash
docker compose up -d
```

Config rendering, database setup, and bootstrap (admin user, default Space, rooms) all run automatically on first startup via Docker Compose service dependencies.

5. **Configure Tailscale Serve** to expose local services over HTTPS on your tailnet. These routes are required for clients to reach the stack:

```bash
tailscale serve --bg --https=443  http://127.0.0.1:8088   # Matrix + Element Web
tailscale serve --bg --https=8443 http://127.0.0.1:8089   # Element Call
tailscale serve --bg --https=8444 http://127.0.0.1:8090   # Admin UI
```

6. Verify everything is running:

```bash
docker compose ps
tailscale serve status
```

See `docs/operator-setup.md` for the full deployment walkthrough, including ACL recommendations for restricting Admin UI access.

Quick links:

- User onboarding (including encrypted-message identity confirmation): `docs/user-onboarding.md`
- Common issues and recovery steps: `docs/troubleshooting.md`
- Operator setup and deployment flow: `docs/operator-setup.md`

Onboarding policy recommendation: strongly encourage every new user to enable
Secure Backup and store recovery material before logging out, or they may lose
access to old encrypted message history.

## Configuration reference (`.env`)

Use `.env.example` as the source of truth. The values below are the main settings most operators need to set first.

| Variable | What it controls | How to choose it |
| --- | --- | --- |
| **Matrix identity / networking** | | |
| `MATRIX_SERVER_NAME` | Synapse server name and room/user domain | Use your Tailscale node MagicDNS name (for example `host.tailnet.ts.net`). |
| `PUBLIC_BASEURL` | Base URL clients use to reach Synapse | `https://` + the same host as `MATRIX_SERVER_NAME` in tailnet deployments. |
| `ELEMENT_HTTP_PORT` | Host port for Element Web | Default `8088`. Change if the port conflicts on your host. |
| `ELEMENT_CALL_HTTP_PORT` | Host port for Element Call | Default `8089`. Change if the port conflicts on your host. |
| `ADMIN_UI_HTTP_PORT` | Host port for the Admin UI | Default `8090`. Change if the port conflicts on your host. |
| `LIVEKIT_HTTP_PORT` | Host port for LiveKit signaling | Default `7880`. Change if the port conflicts on your host. |
| `ELEMENT_CALL_URL` | Element Call URL used by Element Web call buttons | Point this to your self-hosted Element Call URL (for example `https://host.tailnet.ts.net:8443`). |
| `LIVEKIT_NODE_IP` | LiveKit media candidate IP | Set to the server's Tailscale IPv6 from `tailscale ip -6` for tailnet-only media. |
| `MATRIX_RTC_LIVEKIT_SERVICE_URL` | Synapse MatrixRTC focus URL for group calls | Usually leave blank to auto-use `${ELEMENT_CALL_URL}/livekit/jwt`, or set explicitly if your path differs. |
| `LIVEKIT_SFU_URL` | LiveKit WebSocket URL returned by MatrixRTC auth service | Usually leave blank to auto-use `wss://.../livekit/sfu` from `ELEMENT_CALL_URL`. |
| `MAX_EVENT_DELAY_DURATION` | Maximum allowed delay for delayed events in Synapse | Default `24h`. Adjust if your workflows need longer or shorter delays. |
| `RC_MESSAGE_PER_SECOND` | Synapse rate limit: messages per second | Default `0.5`. Increase for higher-traffic rooms. |
| `RC_MESSAGE_BURST_COUNT` | Synapse rate limit: message burst allowance | Default `30`. Increase if users hit rate limits during bursts. |
| `RC_DELAYED_EVENT_MGMT_PER_SECOND` | Synapse rate limit: delayed-event management per second | Default `1`. |
| `RC_DELAYED_EVENT_MGMT_BURST_COUNT` | Synapse rate limit: delayed-event management burst | Default `20`. |
| `TURN_REALM` | coturn auth realm used for Matrix VoIP | Set this to the same host as `MATRIX_SERVER_NAME`/`PUBLIC_BASEURL`. Mismatches can break calls. |
| `LIVEKIT_API_KEY` | API key for Element Call <-> LiveKit auth | Default `devkey`. Change for production deployments. |
| `LIVEKIT_API_SECRET` | Secret for Element Call <-> LiveKit auth | Use at least 32 characters. |
| **Database** | | |
| `POSTGRES_USER` | PostgreSQL username for Synapse | Default `synapse`. |
| `POSTGRES_PASSWORD` | Synapse database password | Generate a long random password. |
| `POSTGRES_DB` | PostgreSQL database name for Synapse | Default `synapse`. |
| **Synapse secrets** | | |
| `REGISTRATION_SHARED_SECRET` | Secret for privileged Synapse registration APIs | Generate a long random secret. |
| `MACAROON_SECRET_KEY` | Synapse token-signing secret | Generate a long random secret. |
| `FORM_SECRET` | Synapse form/CSRF-related secret material | Generate a long random secret. |
| `TURN_SECRET` | Shared secret used for TURN credentials | Generate a long random secret and keep it private. |
| **Registration / onboarding** | | |
| `ENABLE_REGISTRATION` | Whether open registration is enabled | Default `true`. Set `false` to disable new sign-ups entirely. |
| `REGISTRATION_REQUIRES_TOKEN` | Require an invite token to register | Default `true`. Set `false` to allow open registration without tokens. |
| `REGISTRATION_TOKEN_DEFAULT_USES_ALLOWED` | Default number of uses per generated invite token | Default `1` (single-use tokens). |
| `AUTO_JOIN_ROOMS` | Comma-separated list of rooms new users auto-join | Defaults to announcements, chat, video, and support rooms on your server. |
| **SMTP (password reset)** | | |
| `SMTP_HOST` | SMTP server hostname | Use your SMTP provider's hostname. |
| `SMTP_PORT` | SMTP server port | Default `587` (STARTTLS). Use `465` for implicit TLS if required. |
| `SMTP_USER` | SMTP authentication username | Use your SMTP provider credentials. |
| `SMTP_PASS` | SMTP authentication password | Use your SMTP provider credentials. |
| `SMTP_FROM` | Sender address for password-reset emails | For example `Matrix Admin <matrix@example.com>`. |
| `SMTP_ENABLE_TLS` | Enable TLS for SMTP connections | Default `true`. |
| **Retention** | | |
| `RETENTION_MODE` | Retention policy mode | `indefinite` (keep everything) or `limited` (purge after max days). |
| `RETENTION_MESSAGE_MAX_DAYS` | Max age in days for messages when mode is `limited` | Default `180`. Only applies when `RETENTION_MODE=limited`. |
| `RETENTION_MEDIA_MAX_DAYS` | Max age in days for media when mode is `limited` | Default `180`. Only applies when `RETENTION_MODE=limited`. |
| `RETENTION_PURGE_INTERVAL_HOURS` | How often the retention purge job runs (hours) | Default `24`. |
| **Bootstrap admin + defaults** | | |
| `BOOTSTRAP_ADMIN_LOCALPART` | Local part of the initial admin Matrix ID | Default `admin` (creates `@admin:<server>`). |
| `BOOTSTRAP_ADMIN_DISPLAY_NAME` | Display name for the bootstrap admin user | Default `Server Admin`. |
| `BOOTSTRAP_ADMIN_EMAIL` | Initial admin login email | Set to the operator/admin email you will use. |
| `BOOTSTRAP_ADMIN_PASSWORD` | Initial admin login password | Set a strong unique password, then rotate per your policy. |
| `BOOTSTRAP_SPACE_NAME` | Display name of the root Matrix Space shown in Element | Set your community label (for example `Acme Community`). |
| `BOOTSTRAP_SPACE_ALIAS` | Alias slug for the root Matrix Space (`#<alias>:<server>`) | Use a short stable slug (for example `community` or `acme`). |
| `BOOTSTRAP_SPACE_TOPIC` | Topic description for the root Space | Set a short description for your community Space. |
| `BOOTSTRAP_DEFAULT_ROOMS` | Comma-separated room slugs created at bootstrap | Default `announcements,chat,video,support`. |
| **Admin API auth** | | |
| `ADMIN_AUTH_SECRET` | JWT signing secret for the Admin API | Generate a long random secret. |
| `ADMIN_TOKEN_TTL_MINUTES` | Admin API JWT token lifetime in minutes | Default `480` (8 hours). |

### How to obtain `TURN_REALM`

- Use the exact hostname clients use for your homeserver.
- In this tailnet-only setup, that is typically your Tailscale MagicDNS name.
- You can get that hostname from the Tailscale admin UI (Machines list) or locally with:

```bash
tailscale status --self
```

- Ensure these stay aligned: `MATRIX_SERVER_NAME` host, `PUBLIC_BASEURL` host, and `TURN_REALM`.

### Tailnet-only media path

- This stack configures LiveKit to advertise only the Tailscale IP in `LIVEKIT_NODE_IP`.
- Group-call media stays on the tailnet and does not rely on public WAN ICE candidates.
- Clients must be connected to Tailscale for voice/video to work.

### LiveKit host-network architecture

- `livekit` runs with host networking so ICE/media binds to host interfaces directly (instead of Docker bridge addresses).
- `element-call-web` proxies `/livekit/sfu/*` to `host.docker.internal:7880` so signaling reaches host-networked LiveKit.
- Redis is bound on `127.0.0.1:6379` so host-networked LiveKit can still connect.
- Media ports used by LiveKit are `7881/tcp` and `50000-50100/udp` on the host.

## Service endpoints (local host bindings)

- Matrix Web (Element): `http://127.0.0.1:${ELEMENT_HTTP_PORT}`
- Element Call: `http://127.0.0.1:${ELEMENT_CALL_HTTP_PORT}`
- Admin UI: `http://127.0.0.1:${ADMIN_UI_HTTP_PORT}`

## Notes

- `runtime/` is generated from templates by `scripts/render_configs.py` via the `config-renderer` service.
- `matrix-bootstrap` is idempotent and creates the initial admin user, default Space, and default rooms.
- New users auto-join `AUTO_JOIN_ROOMS`, and the root Space alias `#${BOOTSTRAP_SPACE_ALIAS}:${MATRIX_SERVER_NAME}` is always appended during config rendering.
- Element Web is configured to use your self-hosted Element Call URL exclusively for room conference calls.
- Admin UI is protected by Tailnet access plus local admin login.
- Admin UI includes a "Self-Hosting Health" panel that checks local call-stack routing/config and highlights drift.
