import datetime as dt
import json
import os
import sqlite3
import urllib.error
import urllib.parse
import urllib.request

import bcrypt
import jwt
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


app = FastAPI(title="Matrix Admin API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = os.environ.get("ADMIN_DB_PATH", "/data/admin.db")
AUTH_SECRET = os.environ.get("ADMIN_AUTH_SECRET", "change-me")
TOKEN_TTL_MINUTES = int(os.environ.get("ADMIN_TOKEN_TTL_MINUTES", "480"))

MATRIX_SERVER_NAME = os.environ["MATRIX_SERVER_NAME"]
SYNAPSE_URL = os.environ.get("SYNAPSE_URL", "http://matrix-synapse:8008")
SYNAPSE_ADMIN_LOCALPART = os.environ["BOOTSTRAP_ADMIN_LOCALPART"]
SYNAPSE_ADMIN_PASSWORD = os.environ["BOOTSTRAP_ADMIN_PASSWORD"]


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
            (bootstrap_email, password_hash, "admin", dt.datetime.utcnow().isoformat()),
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


def matrix_admin_token() -> str:
    login_payload = {
        "type": "m.login.password",
        "identifier": {
            "type": "m.id.user",
            "user": f"@{SYNAPSE_ADMIN_LOCALPART}:{MATRIX_SERVER_NAME}",
        },
        "password": SYNAPSE_ADMIN_PASSWORD,
    }
    response = request_json("POST", f"{SYNAPSE_URL}/_matrix/client/v3/login", login_payload)
    return response["access_token"]


def synapse_admin(method: str, path: str, body: dict | None = None) -> dict:
    token = matrix_admin_token()
    headers = {"Authorization": f"Bearer {token}"}
    return request_json(method, f"{SYNAPSE_URL}{path}", body, headers)


def write_audit(actor_email: str, action: str, target: str = "") -> None:
    conn = db()
    conn.execute(
        "INSERT INTO audit_logs(actor_email, action, target, created_at) VALUES (?, ?, ?, ?)",
        (actor_email, action, target, dt.datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def create_jwt(email: str, role: str) -> str:
    now = dt.datetime.utcnow()
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


@app.on_event("startup")
def on_startup() -> None:
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
    write_audit(user["sub"], "list_registration_tokens")
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
    write_audit(user["sub"], "view_audit_logs")
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


@app.exception_handler(urllib.error.HTTPError)
def handle_synapse_http_error(_, exc: urllib.error.HTTPError):
    detail = exc.reason
    try:
        payload = json.loads(exc.read().decode("utf-8"))
        detail = payload.get("error", detail)
    except Exception:
        pass
    return JSONResponse(status_code=exc.code, content={"detail": detail})
