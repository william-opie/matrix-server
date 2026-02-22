# Troubleshooting

## User cannot register

- Confirm the token is valid and has remaining uses.
- Confirm `REGISTRATION_REQUIRES_TOKEN=true`.
- Check Synapse logs:

```bash
docker compose logs -f synapse
```

## Password reset email not sent

- Verify `SMTP_*` values in `.env`.
- Confirm SMTP credentials and TLS requirements.
- Check logs:

```bash
docker compose logs -f synapse
```

## Cannot read old encrypted messages on phone

- See `docs/user-onboarding.md` for a full end-user walkthrough of
  "Confirm your identity" and key-backup prevention steps.
- If Element shows "Confirm your identity", recover keys with one of these:
  1. Verify this device from another trusted signed-in device.
  2. Restore Secure Backup with your recovery key/passphrase.
- If both options fail because all trusted devices are logged out and the
  recovery key/passphrase is lost, old encrypted history may be unrecoverable.
- After regaining access, confirm Secure Backup is enabled and store the
  recovery key/passphrase safely to prevent future lockout.

## Admin UI login fails

- Ensure you are using `BOOTSTRAP_ADMIN_EMAIL` and `BOOTSTRAP_ADMIN_PASSWORD`.
- Check Admin API logs:

```bash
docker compose logs -f admin-api
```

## Group call issues

- Verify `livekit` and `element-call` containers are healthy.
- Check TURN connectivity and UDP firewall settings.
- Ensure LiveKit media ports are reachable on the host (`50000-50100/udp` and `7881/tcp` in this stack).
- Confirm `TURN_REALM` matches the homeserver hostname (`MATRIX_SERVER_NAME` / `PUBLIC_BASEURL` host).
- Confirm Tailnet users can reach Element Call URL.
- If room calls open Jitsi, verify `ELEMENT_CALL_URL` is set, then re-render config and confirm `runtime/element/config.json` contains `"element_call": {"use_exclusively": true, ...}` and `"features": {"feature_group_calls": true, ...}`.
- If you see `MISSING_MATRIX_RTC_FOCUS`, verify Synapse has `matrix_rtc.transports` configured with a `livekit_service_url` (in this repo from `MATRIX_RTC_LIVEKIT_SERVICE_URL`, defaulting to `${ELEMENT_CALL_URL}/livekit/jwt`).
- Synapse 1.147+ may require `experimental_features.msc4143_enabled: true` so Element's `/_matrix/client/unstable/org.matrix.msc4143/rtc/transports` request succeeds.
- Ensure `/.well-known/matrix/client` is served by Synapse and includes `org.matrix.msc4143.rtc_foci` pointing to your LiveKit JWT endpoint.
- If `GET /livekit/jwt/sfu/get` returns `405`, ensure the Element Call endpoint is fronted by a reverse proxy routing `/livekit/jwt/*` to `lk-jwt-service` and `/livekit/sfu/*` to LiveKit.
- If LiveKit logs `secret is too short`, set `LIVEKIT_API_SECRET` to at least 32 characters and restart `livekit` + `livekit-jwt`.
- If `lk-jwt-service` logs `Failed to look up user info ... M_UNRECOGNIZED`, ensure Synapse listener resources include `federation` (not just `client`) so OpenID userinfo lookup is exposed.
