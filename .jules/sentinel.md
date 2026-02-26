# Sentinel's Journal

## 2025-02-14 - Enforcing Secure Defaults for Auth Secrets
**Vulnerability:** `ADMIN_AUTH_SECRET` defaulted to "change-me", allowing the Admin API to run with a known weak secret if the environment variable was missing.
**Learning:** Default values for security-critical configuration (like secrets) should be avoided. The application should fail to start if a secure value is not provided, rather than silently falling back to an insecure default. This is a classic "Fail Open" vs "Fail Secure" issue.
**Prevention:** Use `os.environ[...]` for mandatory secrets (which raises KeyError) or explicit checks that raise `RuntimeError` if the value is missing or weak. Avoid `os.environ.get(..., "default_secret")`.
