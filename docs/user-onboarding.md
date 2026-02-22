# User Onboarding Guide

## Join the server

1. Install Tailscale and sign in.
2. Get access to the operator's tailnet.
3. Open the provided Element URL.

## Create account

1. Select "Create account".
2. Enter:
   - homeserver URL,
   - username,
   - password,
   - invite token from admin.

After signup, you are auto-joined into the default space and rooms.

## Secure Backup setup (strongly recommended before any logout)

Before you log out of your first signed-in session, set up Secure Backup in
Element and save the recovery key/passphrase.

- This greatly reduces the risk of losing access to old encrypted messages.
- If you lose all trusted sessions and your recovery key/passphrase, encrypted
  message history may be unrecoverable.
- Non-encrypted room history is not affected by missing recovery keys.

Typical path in Element:

1. Open Settings.
2. Go to Security and Privacy.
3. Enable Secure Backup.
4. Save the recovery key/passphrase in a password manager and an offline copy.

## Log in on another device

Use the same username/password and homeserver URL.

When you sign back in after logging out, Element may show a
"Confirm your identity" prompt before old encrypted messages are readable.

## Confirm your identity after signing back in (important)

If you see "Confirm your identity", use one of these methods:

1. Verify from a trusted device (recommended):
   - Keep another signed-in Element device open.
   - On the new login, choose "Verify with another device".
   - Approve the request on the trusted device (QR or emoji/SAS check).
2. Restore Secure Backup:
   - Choose recovery with your security key or passphrase.
   - Enter your recovery key/passphrase and finish restore.

If you have neither a trusted device nor your recovery key/passphrase, you can
still sign in, but old encrypted history may remain unreadable.

## Before you log out of your last device

1. Confirm Secure Backup is enabled in Element security settings.
2. Save your recovery key/passphrase in a password manager and an offline copy.
3. Keep at least one other trusted signed-in device whenever possible.

## Password reset

Use "Forgot password" in the login screen.

- A reset email is sent to your configured email address.
- If email reset fails, contact admin for manual reset.

## Encrypted history on new devices (important)

To read older encrypted messages on a new device, do one of these:

1. Verify your new device from an already trusted device.
2. Restore Secure Backup with your recovery key/passphrase.

If you lose all trusted devices and your recovery key/passphrase, old encrypted history may be unrecoverable.
