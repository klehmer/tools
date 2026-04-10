"""
Read and write app configuration to the .env file.
Changes are applied to os.environ immediately so the running process
picks them up without a restart.
"""

import os
from pathlib import Path
from typing import Optional

ENV_PATH = Path(__file__).parent / ".env"

# Fields exposed through the config API
ALL_FIELDS = [
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "ANTHROPIC_API_KEY",
    "BACKEND_URL",
    "FRONTEND_URL",
]

# These are never returned in plain text
SECRET_FIELDS = {"GOOGLE_CLIENT_SECRET", "ANTHROPIC_API_KEY"}

# Required for the app to function
REQUIRED_FIELDS = {"GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "ANTHROPIC_API_KEY"}


# ------------------------------------------------------------------ #
# Read                                                                 #
# ------------------------------------------------------------------ #

def _read_env_file() -> dict[str, str]:
    """Parse the .env file into a dict (no os.environ fallback)."""
    values: dict[str, str] = {}
    if not ENV_PATH.exists():
        return values
    with open(ENV_PATH) as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, _, value = stripped.partition("=")
            values[key.strip()] = value.strip()
    return values


def _is_placeholder(value: str) -> bool:
    return not value or value.startswith("your_")


def get_config() -> dict:
    """
    Return config values for the UI.
    Non-secrets: return the actual value (or "" if not set).
    Secrets: return "" — the UI only needs to know whether they are set.
    """
    raw = _read_env_file()
    result = {}
    for field in ALL_FIELDS:
        value = raw.get(field, "")
        is_set = bool(value) and not _is_placeholder(value)
        if field in SECRET_FIELDS:
            result[field] = {"value": "", "is_set": is_set}
        else:
            result[field] = {"value": value if is_set else "", "is_set": is_set}
    return result


def is_configured() -> bool:
    """True when all required fields have real (non-placeholder) values."""
    raw = _read_env_file()
    return all(
        not _is_placeholder(raw.get(f, "")) for f in REQUIRED_FIELDS
    )


# ------------------------------------------------------------------ #
# Write                                                                #
# ------------------------------------------------------------------ #

def save_config(updates: dict[str, Optional[str]]) -> None:
    """
    Write non-None values to the .env file and update os.environ.
    Passing None for a field leaves it unchanged.
    Passing "" for a field clears it.
    """
    # Load existing lines to preserve comments and ordering
    lines: list[str] = []
    key_to_line: dict[str, int] = {}

    if ENV_PATH.exists():
        with open(ENV_PATH) as f:
            for line in f:
                stripped = line.rstrip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    key = stripped.partition("=")[0].strip()
                    key_to_line[key] = len(lines)
                lines.append(stripped)

    for key, value in updates.items():
        if value is None:
            continue  # Leave unchanged
        if key in key_to_line:
            lines[key_to_line[key]] = f"{key}={value}"
        else:
            lines.append(f"{key}={value}")

        # Apply immediately to the running process
        if value:
            os.environ[key] = value
        else:
            os.environ.pop(key, None)

    with open(ENV_PATH, "w") as f:
        f.write("\n".join(lines) + "\n")
