import datetime as dt
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import bcrypt
import jwt
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


app = FastAPI(title="Matrix Admin API", version="0.1.0")

DB_PATH = os.environ.get("ADMIN_DB_PATH", "/data/admin.db")
AUTH_SECRET = os.environ.get("ADMIN_AUTH_SECRET", "")
TOKEN_TTL_MINUTES = int(os.environ.get("ADMIN_TOKEN_TTL_MINUTES", "480"))

MATRIX_SERVER_NAME = os.environ["MATRIX_SERVER_NAME"]
SYNAPSE_URL = os.environ.get("SYNAPSE_URL", "http://matrix-synapse:8008")
SYNAPSE_ADMIN_LOCALPART = os.environ["BOOTSTRAP_ADMIN_LOCALPART"]
SYNAPSE_ADMIN_PASSWORD = os.environ["BOOTSTRAP_ADMIN_PASSWORD"]
PUBLIC_BASEURL = os.environ.get("PUBLIC_BASEURL", "")
ELEMENT_CALL_URL = os.environ.get("ELEMENT_CALL_URL", "")
MATRIX_RTC_LIVEKIT_SERVICE_URL = os.environ.get("MATRIX_RTC_LIVEKIT_SERVICE_URL", "")
ELEMENT_CALL_INTERNAL_URL = os.environ.get("ELEMENT_CALL_INTERNAL_URL", "http://matrix-element-call-web")
RUNTIME_ROOT = Path(os.environ.get("RUNTIME_ROOT", "/workspace/runtime"))
REPO_ROOT = Path(os.environ.get("REPO_ROOT", "/workspace"))

ADMIN_UI_HTTP_PORT = os.environ.get("ADMIN_UI_HTTP_PORT", "8090")
_cors_origins = [
    f"http://127.0.0.1:{ADMIN_UI_HTTP_PORT}",
    f"https://{MATRIX_SERVER_NAME}:8444",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Synapse admin token cache
# ---------------------------------------------------------------------------
_cached_admin_token: str | None = None
_cached_admin_token_ts: float = 0.0
_TOKEN_CACHE_TTL: int = 30 * 60  # 30 minutes


def db() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    conn = db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_users (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          email TEXT UNIQUE NOT NULL,
          password_hash TEXT NOT NULL,
          role TEXT NOT NULL,
          created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          actor_email TEXT NOT NULL,
          action TEXT NOT NULL,
          target TEXT,
          created_at TEXT NOT NULL
        )
        """
    )

    bootstrap_email = os.environ["BOOTSTRAP_ADMIN_EMAIL"].strip().lower()
    bootstrap_password = os.environ["BOOTSTRAP_ADMIN_PASSWORD"]

    existing = conn.execute("SELECT id FROM admin_users WHERE email = ?", (bootstrap_email,)).fetchone()
    if not existing:
        password_hash = bcrypt.hashpw(bootstrap_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        conn.execute(
            "INSERT INTO admin_users(email, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
            (bootstrap_email, password_hash, "admin", dt.datetime.now(dt.timezone.utc).replace(tzinfo=None).isoformat()),
        )
    conn.commit()
    conn.close()


def request_json(method: str, url: str, data: dict | None = None, headers: dict | None = None) -> dict:
    payload = None
    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)
    if data is not None:
        payload = json.dumps(data).encode("utf-8")

    req = urllib.request.Request(url, method=method, data=payload, headers=request_headers)
    with urllib.request.urlopen(req, timeout=20) as response:
        raw = response.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def request_status(method: str, url: str) -> int:
    req = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(req, timeout=15) as response:
        return response.status


def _invalidate_token_cache() -> None:
    global _cached_admin_token, _cached_admin_token_ts
    _cached_admin_token = None
    _cached_admin_token_ts = 0.0


def matrix_admin_token() -> str:
    global _cached_admin_token, _cached_admin_token_ts
    now = time.monotonic()
    if _cached_admin_token and (now - _cached_admin_token_ts) < _TOKEN_CACHE_TTL:
        return _cached_admin_token

    login_payload = {
        "type": "m.login.password",
        "identifier": {
            "type": "m.id.user",
            "user": f"@{SYNAPSE_ADMIN_LOCALPART}:{MATRIX_SERVER_NAME}",
        },
        "password": SYNAPSE_ADMIN_PASSWORD,
    }
    response = request_json("POST", f"{SYNAPSE_URL}/_matrix/client/v3/login", login_payload)
    token: str = response["access_token"]
    _cached_admin_token = token
    _cached_admin_token_ts = now
    return token


def synapse_admin(method: str, path: str, body: dict | None = None) -> dict:
    token = matrix_admin_token()
    headers = {"Authorization": f"Bearer {token}"}
    try:
        return request_json(method, f"{SYNAPSE_URL}{path}", body, headers)
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            _invalidate_token_cache()
            token = matrix_admin_token()
            headers = {"Authorization": f"Bearer {token}"}
            return request_json(method, f"{SYNAPSE_URL}{path}", body, headers)
        raise


def write_audit(actor_email: str, action: str, target: str = "") -> None:
    conn = db()
    conn.execute(
        "INSERT INTO audit_logs(actor_email, action, target, created_at) VALUES (?, ?, ?, ?)",
        (actor_email, action, target, dt.datetime.now(dt.timezone.utc).replace(tzinfo=None).isoformat()),
    )
    conn.commit()
    conn.close()


def create_jwt(email: str, role: str) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    payload = {
        "sub": email,
        "role": role,
        "iat": now,
        "exp": now + dt.timedelta(minutes=TOKEN_TTL_MINUTES),
    }
    return jwt.encode(payload, AUTH_SECRET, algorithm="HS256")


def get_current_user(authorization: str = Header(default="")) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, AUTH_SECRET, algorithms=["HS256"])
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return payload


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)


class UserAction(BaseModel):
    user_id: str


class ResetPasswordRequest(BaseModel):
    user_id: str
    new_password: str = Field(min_length=8)


class RegistrationTokenRequest(BaseModel):
    token: str | None = None
    uses_allowed: int = Field(default=1, ge=1, le=1000)


class RoomShutdownRequest(BaseModel):
    room_id: str
    message: str = "This room has been closed by an administrator."


class SelfHostingCheck(BaseModel):
    id: str
    title: str
    status: str
    details: str


@app.on_event("startup")
def on_startup() -> None:
    if not AUTH_SECRET or AUTH_SECRET == "change-me":
        print(
            "FATAL: ADMIN_AUTH_SECRET is not set or is still the default value. "
            "Set a strong secret in .env"
        )
        sys.exit(1)
    init_db()


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.post("/api/auth/login")
def login(payload: LoginRequest) -> dict:
    conn = db()
    row = conn.execute(
        "SELECT email, password_hash, role FROM admin_users WHERE email = ?",
        (payload.email.lower(),),
    ).fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not bcrypt.checkpw(payload.password.encode("utf-8"), row["password_hash"].encode("utf-8")):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_jwt(row["email"], row["role"])
    return {"access_token": token, "token_type": "bearer"}


@app.get("/api/auth/me")
def me(user: dict = Depends(get_current_user)) -> dict:
    return {"email": user["sub"], "role": user["role"]}


@app.post("/api/users/deactivate")
def deactivate_user(payload: UserAction, user: dict = Depends(get_current_user)) -> dict:
    encoded = urllib.parse.quote(payload.user_id, safe="")
    synapse_admin("POST", f"/_synapse/admin/v1/deactivate/{encoded}", {"erase": False})
    write_audit(user["sub"], "deactivate_user", payload.user_id)
    return {"ok": True}


@app.post("/api/users/reactivate")
def reactivate_user(payload: UserAction, user: dict = Depends(get_current_user)) -> dict:
    encoded = urllib.parse.quote(payload.user_id, safe="")
    synapse_admin("PUT", f"/_synapse/admin/v2/users/{encoded}", {"deactivated": False})
    write_audit(user["sub"], "reactivate_user", payload.user_id)
    return {"ok": True}


@app.post("/api/users/reset-password")
def reset_password(payload: ResetPasswordRequest, user: dict = Depends(get_current_user)) -> dict:
    encoded = urllib.parse.quote(payload.user_id, safe="")
    synapse_admin("POST", f"/_synapse/admin/v1/reset_password/{encoded}", {"new_password": payload.new_password})
    write_audit(user["sub"], "reset_password", payload.user_id)
    return {"ok": True}


@app.post("/api/registration-tokens")
def create_registration_token(payload: RegistrationTokenRequest, user: dict = Depends(get_current_user)) -> dict:
    request_payload: dict[str, object] = {"uses_allowed": payload.uses_allowed}
    if payload.token:
        request_payload["token"] = payload.token
    response = synapse_admin("POST", "/_synapse/admin/v1/registration_tokens/new", request_payload)
    write_audit(user["sub"], "create_registration_token", response.get("token", ""))
    return response


@app.get("/api/registration-tokens")
def list_registration_tokens(user: dict = Depends(get_current_user)) -> dict:
    response = synapse_admin("GET", "/_synapse/admin/v1/registration_tokens")
    return response


@app.post("/api/rooms/shutdown")
def shutdown_room(payload: RoomShutdownRequest, user: dict = Depends(get_current_user)) -> dict:
    encoded = urllib.parse.quote(payload.room_id, safe="")
    response = synapse_admin(
        "DELETE",
        f"/_synapse/admin/v2/rooms/{encoded}",
        {
            "block": True,
            "purge": False,
            "message": payload.message,
        },
    )
    write_audit(user["sub"], "shutdown_room", payload.room_id)
    return response


@app.get("/api/audit-logs")
def audit_logs(user: dict = Depends(get_current_user)) -> dict:
    conn = db()
    rows = conn.execute(
        "SELECT actor_email, action, target, created_at FROM audit_logs ORDER BY id DESC LIMIT 200"
    ).fetchall()
    conn.close()
    return {
        "logs": [
            {
                "actor_email": row["actor_email"],
                "action": row["action"],
                "target": row["target"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]
    }


@app.get("/api/self-hosting/health")
def self_hosting_health(user: dict = Depends(get_current_user)) -> dict:
    checks: list[SelfHostingCheck] = []

    def add_check(check_id: str, title: str, ok: bool, details: str, warning: bool = False) -> None:
        status = "pass" if ok and not warning else "warn" if ok and warning else "fail"
        checks.append(SelfHostingCheck(id=check_id, title=title, status=status, details=details))

    element_path = RUNTIME_ROOT / "element" / "config.json"
    synapse_path = RUNTIME_ROOT / "synapse" / "homeserver.yaml"
    call_nginx_path = RUNTIME_ROOT / "nginx" / "element-call.conf"
    compose_path = REPO_ROOT / "docker-compose.yml"

    try:
        element_config = json.loads(element_path.read_text(encoding="utf-8"))
        element_call = element_config.get("element_call", {})
        use_exclusively = bool(element_call.get("use_exclusively"))
        call_url = element_call.get("url", "")
        no_jitsi = "jitsi" not in element_path.read_text(encoding="utf-8").lower()
        add_check(
            "element_call_exclusive",
            "Element configured for Element Call only",
            use_exclusively and no_jitsi,
            f"element_call.url={call_url}, use_exclusively={use_exclusively}, jitsi_refs={not no_jitsi}",
        )
    except Exception as exc:
        add_check("element_call_exclusive", "Element configured for Element Call only", False, f"Read failed: {exc}")

    try:
        synapse_yaml = synapse_path.read_text(encoding="utf-8")
        has_matrix_rtc = "matrix_rtc:" in synapse_yaml and "livekit_service_url:" in synapse_yaml
        has_federation_listener = "names: [client, federation]" in synapse_yaml
        add_check(
            "synapse_matrixrtc",
            "Synapse MatrixRTC + federation listener",
            has_matrix_rtc and has_federation_listener,
            f"matrix_rtc={has_matrix_rtc}, federation_listener={has_federation_listener}",
        )
    except Exception as exc:
        add_check("synapse_matrixrtc", "Synapse MatrixRTC + federation listener", False, f"Read failed: {exc}")

    try:
        nginx_conf = call_nginx_path.read_text(encoding="utf-8")
        has_jwt_route = "/livekit/jwt/" in nginx_conf and "matrix-livekit-jwt:8080" in nginx_conf
        has_sfu_route = "/livekit/sfu/" in nginx_conf and (
            "matrix-livekit:7880" in nginx_conf or "host.docker.internal:7880" in nginx_conf
        )
        add_check(
            "call_proxy_routes",
            "Element Call proxy routes to local services",
            has_jwt_route and has_sfu_route,
            f"jwt_route={has_jwt_route}, sfu_route={has_sfu_route}",
        )
    except Exception as exc:
        add_check("call_proxy_routes", "Element Call proxy routes to local services", False, f"Read failed: {exc}")

    try:
        versions = request_json("GET", f"{SYNAPSE_URL}/_matrix/client/versions")
        unstable = versions.get("unstable_features", {})
        has_msc4140 = bool(unstable.get("org.matrix.msc4140"))
        add_check(
            "synapse_versions",
            "Synapse client API reachable",
            True,
            f"versions={len(versions.get('versions', []))}, msc4140={has_msc4140}",
            warning=not has_msc4140,
        )
    except Exception as exc:
        add_check("synapse_versions", "Synapse client API reachable", False, f"Request failed: {exc}")

    try:
        jwt_status = request_status("GET", f"{ELEMENT_CALL_INTERNAL_URL.rstrip('/')}/livekit/jwt/healthz")
        add_check(
            "jwt_health",
            "LiveKit JWT service reachable",
            jwt_status == 200,
            f"status={jwt_status}, endpoint={ELEMENT_CALL_INTERNAL_URL.rstrip('/')}/livekit/jwt/healthz",
        )
    except Exception as exc:
        add_check("jwt_health", "LiveKit JWT service reachable", False, f"Request failed: {exc}")

    try:
        compose_text = compose_path.read_text(encoding="utf-8")
        web_local = '127.0.0.1:${ELEMENT_HTTP_PORT}:80' in compose_text
        call_local = '127.0.0.1:${ELEMENT_CALL_HTTP_PORT}:80' in compose_text
        admin_local = '127.0.0.1:${ADMIN_UI_HTTP_PORT}:80' in compose_text
        add_check(
            "port_binding_posture",
            "Public web UIs bound to localhost",
            web_local and call_local and admin_local,
            f"matrix_web_local={web_local}, element_call_local={call_local}, admin_ui_local={admin_local}",
        )
    except Exception as exc:
        add_check("port_binding_posture", "Public web UIs bound to localhost", False, f"Read failed: {exc}")

    if PUBLIC_BASEURL and ELEMENT_CALL_URL and MATRIX_RTC_LIVEKIT_SERVICE_URL:
        details = (
            f"public_baseurl={PUBLIC_BASEURL}, element_call_url={ELEMENT_CALL_URL}, "
            f"rtc_focus={MATRIX_RTC_LIVEKIT_SERVICE_URL}"
        )
        same_domain = MATRIX_SERVER_NAME in PUBLIC_BASEURL and MATRIX_SERVER_NAME in ELEMENT_CALL_URL
        add_check("tailnet_domain_alignment", "Tailnet domain alignment", same_domain, details)
    else:
        add_check(
            "tailnet_domain_alignment",
            "Tailnet domain alignment",
            False,
            "Missing one or more env values: PUBLIC_BASEURL/ELEMENT_CALL_URL/MATRIX_RTC_LIVEKIT_SERVICE_URL",
        )

    statuses = [check.status for check in checks]
    overall = "fail" if "fail" in statuses else "warn" if "warn" in statuses else "pass"
    return {
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(tzinfo=None).isoformat() + "Z",
        "overall": overall,
        "checks": [check.model_dump() for check in checks],
        "note": (
            "This report verifies self-hosted configuration and runtime paths. "
            "It cannot cryptographically prove that no packet ever leaves your tailnet."
        ),
    }


@app.exception_handler(urllib.error.HTTPError)
def handle_synapse_http_error(_, exc: urllib.error.HTTPError):
    detail = exc.reason
    try:
        payload = json.loads(exc.read().decode("utf-8"))
        detail = payload.get("error", detail)
    except Exception:
        pass
    return JSONResponse(status_code=exc.code, content={"detail": detail})
