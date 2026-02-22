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
