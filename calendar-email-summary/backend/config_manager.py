"""Read/write the .env file for runtime configuration."""
import os
from pathlib import Path

ENV_PATH = Path(__file__).parent / ".env"

FIELDS = [
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "AI_PROVIDER",
    "AI_MODEL",
    "DEFAULT_PERIOD",
    "DEFAULT_DIRECTION",
    "PLANNER_COLUMN_WIDTH",
    "BACKEND_URL",
    "FRONTEND_URL",
]

DEFAULTS = {
    "AI_PROVIDER": "claude-code",
    "AI_MODEL": "",
    "DEFAULT_PERIOD": "week",
    "DEFAULT_DIRECTION": "past",
    "PLANNER_COLUMN_WIDTH": "220",
    "BACKEND_URL": "http://localhost:8001",
    "FRONTEND_URL": "http://localhost:5174",
}


def _read_env() -> dict:
    if not ENV_PATH.exists():
        return {}
    out = {}
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip()
    return out


def get_config() -> dict:
    env = _read_env()
    result = {}
    for f in FIELDS:
        val = env.get(f) or os.getenv(f, "") or DEFAULTS.get(f, "")
        result[f] = {
            "value": val if not _is_secret(f) else ("***" if val else ""),
            "configured": bool(val) and val != f"your_{f.lower()}_here",
        }
    return result


def _is_secret(field: str) -> bool:
    return "SECRET" in field or "KEY" in field


def is_configured() -> bool:
    """True once initial setup has been completed.

    We just check whether the .env file has been written with an
    AI_PROVIDER value.  Google OAuth and API keys are optional at
    initial setup — the planner works without them.
    """
    env = _read_env()
    # AI_PROVIDER is written by save_config during setup.
    # If it's present in the .env, setup was completed.
    return bool(env.get("AI_PROVIDER"))


def is_ai_configured() -> bool:
    """True when the AI provider has the credentials it needs."""
    env = _read_env()
    provider = env.get("AI_PROVIDER") or os.getenv("AI_PROVIDER", "")
    if not provider:
        return False
    if provider == "anthropic":
        v = env.get("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY", "")
        if not v or v == "your_anthropic_api_key_here":
            return False
    elif provider == "openai":
        v = env.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY", "")
        if not v or v == "your_openai_api_key_here":
            return False
    return True


def is_google_configured() -> bool:
    """True when Google OAuth credentials have been provided."""
    env = _read_env()
    for f in ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"]:
        v = env.get(f) or os.getenv(f, "")
        if not v or v == f"your_{f.lower()}_here":
            return False
    return True


def save_config(updates: dict) -> None:
    env = _read_env()
    for k, v in updates.items():
        if k in FIELDS and v is not None and v != "***":
            env[k] = v
            os.environ[k] = v
    lines = [f"{k}={env.get(k, '')}" for k in FIELDS]
    ENV_PATH.write_text("\n".join(lines) + "\n")
