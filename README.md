# Matrix Server (Tailnet-Only)

Self-hosted Matrix stack designed for private Tailscale environments, with invite-token onboarding, SMTP self-service password resets, default Space/room bootstrap, Element Call, and an internal admin panel.

## What this repository provides

- Synapse + PostgreSQL + coturn + Element Web in Docker Compose.
- Tailnet-only deployment model (no public federation).
- Invite-token registration flow and automatic room onboarding.
- SMTP password reset support.
- Element Call self-hosted stack (LiveKit-based).
- Admin API + frontend for common Synapse admin actions.
- Config templating from `.env` so this repo is easy to share.

## Quick start

1. Copy `.env.example` to `.env`.
2. **Before first startup**, set your Tailnet hostname details and admin credentials in `.env`:
   - `MATRIX_SERVER_NAME`
   - `PUBLIC_BASEURL`
   - `TURN_REALM`
   - `BOOTSTRAP_ADMIN_EMAIL`
   - `BOOTSTRAP_ADMIN_PASSWORD`
   - For Tailscale deployments, set `TURN_REALM` to the same host as your Matrix server (usually your node MagicDNS name, like `host.tailnet.ts.net`).
3. Replace all `CHANGE_ME_*` values with strong secrets.
4. Start the stack:

```bash
docker compose up -d
```

5. Publish internal ports using Tailscale Serve/Funnel rules as desired.

See detailed docs in `docs/`.

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
| `MATRIX_SERVER_NAME` | Synapse server name and room/user domain | Use your Tailscale node MagicDNS name (for example `host.tailnet.ts.net`). |
| `PUBLIC_BASEURL` | Base URL clients use to reach Synapse | `https://` + the same host as `MATRIX_SERVER_NAME` in tailnet deployments. |
| `ELEMENT_CALL_URL` | Element Call URL used by Element Web call buttons | Point this to your self-hosted Element Call URL (for example `https://host.tailnet.ts.net:8443`). |
| `MATRIX_RTC_LIVEKIT_SERVICE_URL` | Synapse MatrixRTC focus URL for group calls | Usually leave blank to auto-use `${ELEMENT_CALL_URL}/livekit/jwt`, or set explicitly if your path differs. |
| `LIVEKIT_SFU_URL` | LiveKit WebSocket URL returned by MatrixRTC auth service | Usually leave blank to auto-use `wss://.../livekit/sfu` from `ELEMENT_CALL_URL`. |
| `LIVEKIT_NODE_IP` | LiveKit media candidate IP | Set to the server's Tailscale IPv4 from `tailscale ip -4` for tailnet-only media. |
| `TURN_REALM` | coturn auth realm used for Matrix VoIP | Set this to the same host as `MATRIX_SERVER_NAME`/`PUBLIC_BASEURL`. Mismatches can break calls. |
| `TURN_SECRET` | Shared secret used for TURN credentials | Generate a long random secret and keep it private. |
| `LIVEKIT_API_SECRET` | Secret for Element Call <-> LiveKit auth | Use at least 32 characters. |
| `POSTGRES_PASSWORD` | Synapse database password | Generate a long random password. |
| `REGISTRATION_SHARED_SECRET` | Secret for privileged Synapse registration APIs | Generate a long random secret. |
| `MACAROON_SECRET_KEY` | Synapse token-signing secret | Generate a long random secret. |
| `FORM_SECRET` | Synapse form/CSRF-related secret material | Generate a long random secret. |
| `BOOTSTRAP_ADMIN_EMAIL` | Initial admin login email | Set to the operator/admin email you will use. |
| `BOOTSTRAP_ADMIN_PASSWORD` | Initial admin login password | Set a strong unique password, then rotate per your policy. |
| `BOOTSTRAP_SPACE_NAME` | Display name of the root Matrix Space shown in Element | Set your community label (for example `Acme Community`). |
| `BOOTSTRAP_SPACE_ALIAS` | Alias slug for the root Matrix Space (`#<alias>:<server>`) | Use a short stable slug (for example `community` or `acme`). |
| `SMTP_HOST` / `SMTP_USER` / `SMTP_PASS` | Password reset email delivery settings | Use your SMTP provider credentials and TLS requirements. |

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
