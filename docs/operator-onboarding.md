# Operator Onboarding Flow

## Create invite token

1. Open Admin UI.
2. Sign in with `BOOTSTRAP_ADMIN_EMAIL` and `BOOTSTRAP_ADMIN_PASSWORD`.
3. Create a registration token (single use recommended).
4. Send user:
   - Homeserver URL (`PUBLIC_BASEURL`)
   - Their token

## What happens after signup

- User registers with username/password + token.
- Synapse auto-joins the user to configured defaults in `AUTO_JOIN_ROOMS`.
- The root Space alias `#${BOOTSTRAP_SPACE_ALIAS}:${MATRIX_SERVER_NAME}` is appended to auto-join at render time, so users also get the root Space in the Element sidebar.
- Default Space and rooms are pre-created by bootstrap.

## Onboarding completion checklist (strong policy recommendation)

Before marking onboarding complete, ask the user to confirm:

1. They enabled Secure Backup in Element.
2. They saved their recovery key/passphrase in a password manager and offline copy.

Reason: without a trusted signed-in device or recovery key/passphrase, old
encrypted history may be unrecoverable after logout/device loss.

## Recommended invite policy

- Generate one token per user.
- Set `uses_allowed=1`.
- Expire/disable tokens when no longer needed.

## Basic moderation actions in Admin UI

- Deactivate/reactivate user.
- Admin password reset fallback.
- Shut down room/space by room ID.
- Review audit log.
