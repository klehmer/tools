"""Claude artifacts list, served from a saved copy.

The list can only be fetched from an interactive Claude Code session (its
Artifact tool is not available to headless runs), so that session writes
data/artifacts.json and this module just reads it.
"""
import json
from pathlib import Path

_DATA_DIR = Path(__file__).parent / "data"
_DATA_DIR.mkdir(exist_ok=True)
_FILE = _DATA_DIR / "artifacts.json"


def get_list() -> dict:
    if not _FILE.exists():
        return {"refreshed_at": None, "artifacts": []}
    return json.loads(_FILE.read_text())
