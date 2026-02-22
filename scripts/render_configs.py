import json
import os
from pathlib import Path
from string import Template


ROOT = Path(__file__).resolve().parent.parent


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def to_bool(value: str) -> str:
    return "true" if value.lower() in {"1", "true", "yes", "on"} else "false"


def render_template(src: Path, dst: Path, context: dict[str, str]) -> None:
    content = src.read_text(encoding="utf-8")
    rendered = Template(content).safe_substitute(context)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(rendered, encoding="utf-8")


def build_retention_block(env: dict[str, str]) -> str:
    mode = env.get("RETENTION_MODE", "indefinite").strip().lower()
    if mode == "limited":
        max_days = env.get("RETENTION_MESSAGE_MAX_DAYS", "180")
        purge_hours = env.get("RETENTION_PURGE_INTERVAL_HOURS", "24")
        return (
            "retention:\n"
            "  enabled: true\n"
            f"  default_policy:\n"
            f"    max_lifetime: {int(max_days) * 24 * 60 * 60 * 1000}\n"
            f"  allowed_lifetime_min: 86400000\n"
            f"  purge_jobs:\n"
            f"    - interval: {int(purge_hours) * 60 * 60 * 1000}\n"
            f"      shortest_max_lifetime: 86400000\n"
        )
    return "retention:\n  enabled: false\n"


def main() -> None:
    env = {}
    env.update(load_env(ROOT / ".env"))
    env.update({k: v for k, v in os.environ.items() if k in env or k.startswith(("MATRIX_", "POSTGRES_", "SMTP_", "BOOTSTRAP_", "RETENTION_", "TURN_", "LIVEKIT_", "ADMIN_", "REGISTRATION_", "PUBLIC_BASEURL", "ENABLE_", "AUTO_JOIN_", "MACAROON_", "FORM_"))})

    required = [
        "MATRIX_SERVER_NAME",
        "PUBLIC_BASEURL",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
        "REGISTRATION_SHARED_SECRET",
        "MACAROON_SECRET_KEY",
        "FORM_SECRET",
        "TURN_SECRET",
        "SMTP_HOST",
        "SMTP_PORT",
        "SMTP_USER",
        "SMTP_PASS",
        "SMTP_FROM",
        "LIVEKIT_API_KEY",
        "LIVEKIT_API_SECRET",
    ]
    missing = [k for k in required if not env.get(k)]
    if missing:
        raise SystemExit(f"Missing required env vars: {', '.join(missing)}")

    auto_join_rooms = [room.strip() for room in env.get("AUTO_JOIN_ROOMS", "").split(",") if room.strip()]
    env["AUTO_JOIN_ROOMS_YAML"] = "\n".join(f"  - \"{room}\"" for room in auto_join_rooms)
    env["ENABLE_REGISTRATION"] = to_bool(env.get("ENABLE_REGISTRATION", "true"))
    env["REGISTRATION_REQUIRES_TOKEN"] = to_bool(env.get("REGISTRATION_REQUIRES_TOKEN", "true"))
    env["SMTP_ENABLE_TLS"] = to_bool(env.get("SMTP_ENABLE_TLS", "true"))
    env["RETENTION_BLOCK"] = build_retention_block(env)

    render_template(
        ROOT / "config" / "synapse" / "homeserver.yaml.template",
        ROOT / "runtime" / "synapse" / "homeserver.yaml",
        env,
    )
    render_template(
        ROOT / "config" / "element" / "config.json.template",
        ROOT / "runtime" / "element" / "config.json",
        env,
    )
    render_template(
        ROOT / "config" / "nginx" / "matrix.conf.template",
        ROOT / "runtime" / "nginx" / "matrix.conf",
        env,
    )
    render_template(
        ROOT / "config" / "nginx" / "admin-ui.conf.template",
        ROOT / "runtime" / "nginx" / "admin-ui.conf",
        env,
    )
    render_template(
        ROOT / "config" / "livekit" / "livekit.yaml.template",
        ROOT / "runtime" / "livekit" / "livekit.yaml",
        env,
    )
    render_template(
        ROOT / "config" / "element-call" / "config.json.template",
        ROOT / "runtime" / "element-call" / "config.json",
        env,
    )

    bootstrap_meta = {
        "server_name": env["MATRIX_SERVER_NAME"],
        "space_name": env.get("BOOTSTRAP_SPACE_NAME", "Community HQ"),
        "rooms": [r.strip() for r in env.get("BOOTSTRAP_DEFAULT_ROOMS", "announcements,chat,video,support").split(",") if r.strip()],
    }
    out_path = ROOT / "runtime" / "bootstrap" / "meta.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(bootstrap_meta, indent=2), encoding="utf-8")

    print("Rendered runtime configs under ./runtime")


if __name__ == "__main__":
    main()
