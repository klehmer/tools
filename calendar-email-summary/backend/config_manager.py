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
    "AI_PROVIDER": "anthropic",
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
    """True when the minimum config has been saved (AI provider set up).

    Google OAuth credentials are optional at initial setup — they're
    only needed for email/calendar features, not the planner.
    """
    env = _read_env()
    provider = env.get("AI_PROVIDER") or os.getenv("AI_PROVIDER", "")

    # If no provider has been explicitly chosen, the user hasn't gone
    # through setup yet (the .env file won't have AI_PROVIDER at all).
    if not provider:
        return False

    # AI key required for anthropic/openai, not for CLI providers
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
