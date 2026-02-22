import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


SYNAPSE_URL = os.environ.get("SYNAPSE_URL", "http://matrix-synapse:8008")
STATE_PATH = Path("/state/bootstrap-state.json")


def request_json(method: str, url: str, data: dict | None = None, headers: dict | None = None) -> dict:
    body = None
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    if data is not None:
        body = json.dumps(data).encode("utf-8")

    req = urllib.request.Request(url, data=body, method=method, headers=req_headers)
    with urllib.request.urlopen(req, timeout=20) as response:
        payload = response.read().decode("utf-8")
        return json.loads(payload) if payload else {}


def wait_for_synapse() -> None:
    for _ in range(60):
        try:
            request_json("GET", f"{SYNAPSE_URL}/_matrix/client/versions")
            return
        except Exception:
            time.sleep(2)
    raise RuntimeError("Synapse did not become ready in time")


def shared_secret_register(localpart: str, password: str, admin: bool, shared_secret: str) -> None:
    nonce_payload = request_json("GET", f"{SYNAPSE_URL}/_synapse/admin/v1/register")
    nonce = nonce_payload["nonce"]
    mac_builder = hmac.new(shared_secret.encode("utf-8"), digestmod=hashlib.sha1)
    mac_builder.update(nonce.encode("utf-8"))
    mac_builder.update(b"\x00")
    mac_builder.update(localpart.encode("utf-8"))
    mac_builder.update(b"\x00")
    mac_builder.update(password.encode("utf-8"))
    mac_builder.update(b"\x00")
    mac_builder.update(b"admin" if admin else b"notadmin")
    mac = mac_builder.hexdigest()

    payload = {
        "nonce": nonce,
        "username": localpart,
        "password": password,
        "admin": admin,
        "mac": mac,
    }

    try:
        request_json("POST", f"{SYNAPSE_URL}/_synapse/admin/v1/register", payload)
    except urllib.error.HTTPError as exc:
        if exc.code == 400:
            error_payload = json.loads(exc.read().decode("utf-8"))
            if "User ID already taken" in error_payload.get("error", ""):
                return
        raise


def login(localpart: str, password: str, server_name: str) -> str:
    payload = {
        "type": "m.login.password",
        "identifier": {"type": "m.id.user", "user": f"@{localpart}:{server_name}"},
        "password": password,
    }
    response = request_json("POST", f"{SYNAPSE_URL}/_matrix/client/v3/login", payload)
    return response["access_token"]


def authed(method: str, path: str, token: str, data: dict | None = None) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    return request_json(method, f"{SYNAPSE_URL}{path}", data=data, headers=headers)


def room_state_path(room_id: str, event_type: str, state_key: str = "") -> str:
    encoded_room = urllib.parse.quote(room_id, safe="")
    encoded_type = urllib.parse.quote(event_type, safe="")
    encoded_key = urllib.parse.quote(state_key, safe="")
    return f"/_matrix/client/v3/rooms/{encoded_room}/state/{encoded_type}/{encoded_key}"


def get_room_state(token: str, room_id: str, event_type: str, state_key: str = "") -> dict | None:
    try:
        return authed("GET", room_state_path(room_id, event_type, state_key), token)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def put_room_state(token: str, room_id: str, event_type: str, content: dict, state_key: str = "") -> None:
    authed("PUT", room_state_path(room_id, event_type, state_key), token, content)


def ensure_room_name(token: str, room_id: str, display_name: str) -> None:
    existing = get_room_state(token, room_id, "m.room.name") or {}
    if existing.get("name") == display_name:
        return
    put_room_state(token, room_id, "m.room.name", {"name": display_name})


def ensure_room_topic(token: str, room_id: str, topic: str) -> None:
    existing = get_room_state(token, room_id, "m.room.topic") or {}
    if existing.get("topic") == topic:
        return
    put_room_state(token, room_id, "m.room.topic", {"topic": topic})


def ensure_video_room_call_permissions(token: str, room_id: str) -> None:
    required_event_levels = {
        "im.vector.modular.widgets": 0,
        "io.element.widgets.layout": 0,
        "org.matrix.msc3401.call": 0,
        "org.matrix.msc3401.call.member": 0,
        "org.matrix.msc3401.call.member.encrypted": 0,
        "org.matrix.msc3417.call": 0,
    }
    power_levels = get_room_state(token, room_id, "m.room.power_levels") or {}
    events = power_levels.get("events")
    if not isinstance(events, dict):
        events = {}

    changed = False
    for event_type, level in required_event_levels.items():
        if events.get(event_type) != level:
            events[event_type] = level
            changed = True

    if not changed:
        return

    power_levels["events"] = events
    put_room_state(token, room_id, "m.room.power_levels", power_levels)


def ensure_room_alias(alias: str, token: str, room_id: str) -> None:
    encoded = urllib.parse.quote(alias, safe="")
    try:
        authed("PUT", f"/_matrix/client/v3/directory/room/{encoded}", token, {"room_id": room_id})
    except urllib.error.HTTPError as exc:
        if exc.code != 409:
            raise


def room_id_from_alias(alias: str, token: str) -> str | None:
    encoded = urllib.parse.quote(alias, safe="")
    try:
        response = authed("GET", f"/_matrix/client/v3/directory/room/{encoded}", token)
        return response.get("room_id")
    except urllib.error.HTTPError:
        return None


def create_space(
    token: str,
    name: str,
    topic: str,
    alias_name: str,
    server_name: str,
    existing_space_id: str | None = None,
) -> str:
    alias = f"#{alias_name}:{server_name}"
    existing = room_id_from_alias(alias, token)
    if existing:
        ensure_room_name(token, existing, name)
        ensure_room_topic(token, existing, topic)
        return existing

    if existing_space_id:
        ensure_room_alias(alias, token, existing_space_id)
        ensure_room_name(token, existing_space_id, name)
        ensure_room_topic(token, existing_space_id, topic)
        return existing_space_id

    payload = {
        "creation_content": {"type": "m.space"},
        "name": name,
        "topic": topic,
        "preset": "private_chat",
        "room_alias_name": alias_name,
        "visibility": "private",
    }
    room = authed("POST", "/_matrix/client/v3/createRoom", token, payload)
    room_id = room["room_id"]
    ensure_room_alias(alias, token, room_id)
    ensure_room_name(token, room_id, name)
    ensure_room_topic(token, room_id, topic)
    return room_id


def create_room(token: str, alias_name: str, display_name: str, server_name: str) -> str:
    alias = f"#{alias_name}:{server_name}"
    existing = room_id_from_alias(alias, token)
    if existing:
        return existing

    payload = {
        "name": display_name,
        "topic": f"Default {alias_name} room",
        "preset": "private_chat",
        "room_alias_name": alias_name,
        "visibility": "private",
    }
    room = authed("POST", "/_matrix/client/v3/createRoom", token, payload)
    room_id = room["room_id"]
    ensure_room_alias(alias, token, room_id)
    return room_id


def link_room_to_space(token: str, space_id: str, room_id: str) -> None:
    authed(
        "PUT",
        f"/_matrix/client/v3/rooms/{urllib.parse.quote(space_id, safe='')}/state/m.space.child/{urllib.parse.quote(room_id, safe='')}",
        token,
        {"via": [os.environ["MATRIX_SERVER_NAME"]]},
    )


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def ensure_registration_token(token: str, registration_token: str, uses_allowed: int) -> None:
    existing = authed("GET", "/_synapse/admin/v1/registration_tokens", token)
    for entry in existing.get("registration_tokens", []):
        if entry.get("token") == registration_token:
            return
    authed(
        "POST",
        "/_synapse/admin/v1/registration_tokens/new",
        token,
        {
            "token": registration_token,
            "uses_allowed": uses_allowed,
            "expiry_time": None,
        },
    )


def main() -> None:
    wait_for_synapse()
    state = load_state()

    server_name = os.environ["MATRIX_SERVER_NAME"]
    admin_localpart = os.environ["BOOTSTRAP_ADMIN_LOCALPART"]
    admin_password = os.environ["BOOTSTRAP_ADMIN_PASSWORD"]
    shared_secret = os.environ["REGISTRATION_SHARED_SECRET"]
    default_rooms = [r.strip() for r in os.environ.get("BOOTSTRAP_DEFAULT_ROOMS", "announcements,chat,video,support").split(",") if r.strip()]

    shared_secret_register(admin_localpart, admin_password, admin=True, shared_secret=shared_secret)
    admin_token = login(admin_localpart, admin_password, server_name)

    space_name = os.environ.get("BOOTSTRAP_SPACE_NAME", "Community HQ")
    space_topic = os.environ.get("BOOTSTRAP_SPACE_TOPIC", "Main community space")
    space_alias = os.environ.get("BOOTSTRAP_SPACE_ALIAS", "community").strip()
    if not space_alias:
        raise RuntimeError("BOOTSTRAP_SPACE_ALIAS must not be empty")

    state["space_id"] = create_space(
        admin_token,
        space_name,
        space_topic,
        space_alias,
        server_name,
        state.get("space_id"),
    )

    rooms = state.get("rooms", {})
    for room in default_rooms:
        display_name = room.capitalize()
        if room not in rooms:
            rooms[room] = create_room(admin_token, room, display_name, server_name)
        link_room_to_space(admin_token, state["space_id"], rooms[room])
        ensure_room_name(admin_token, rooms[room], display_name)
        if room == "video":
            ensure_video_room_call_permissions(admin_token, rooms[room])

    state["rooms"] = rooms

    default_token = f"invite-{server_name.split('.')[0]}"
    uses_allowed = int(os.environ.get("REGISTRATION_TOKEN_DEFAULT_USES_ALLOWED", "1"))
    ensure_registration_token(admin_token, default_token, uses_allowed)
    state["default_registration_token"] = default_token

    save_state(state)
    print("Bootstrap complete")


if __name__ == "__main__":
    main()
