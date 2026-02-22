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

- Verify the device in Element from a trusted device.
- Restore Secure Backup with recovery key/passphrase.

## Admin UI login fails

- Ensure you are using `BOOTSTRAP_ADMIN_EMAIL` and `BOOTSTRAP_ADMIN_PASSWORD`.
- Check Admin API logs:

```bash
docker compose logs -f admin-api
```

## Group call issues

- Verify `livekit` and `element-call` containers are healthy.
- Check TURN connectivity and UDP firewall settings.
- Confirm `TURN_REALM` matches the homeserver hostname (`MATRIX_SERVER_NAME` / `PUBLIC_BASEURL` host).
- Confirm Tailnet users can reach Element Call URL.
- If room calls open Jitsi, verify `ELEMENT_CALL_URL` is set, then re-render config and confirm `runtime/element/config.json` contains `"element_call": {"use_exclusively": true, ...}` and `"features": {"feature_group_calls": true, ...}`.
- If you see `MISSING_MATRIX_RTC_FOCUS`, verify Synapse has `matrix_rtc.transports` configured with a `livekit_service_url` (in this repo from `MATRIX_RTC_LIVEKIT_SERVICE_URL`, defaulting to `${ELEMENT_CALL_URL}/livekit/jwt`).
- Synapse 1.147+ may require `experimental_features.msc4143_enabled: true` so Element's `/_matrix/client/unstable/org.matrix.msc4143/rtc/transports` request succeeds.
- Ensure `/.well-known/matrix/client` is served by Synapse and includes `org.matrix.msc4143.rtc_foci` pointing to your LiveKit JWT endpoint.
