"""Bookmarked links module backed by a JSON file."""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

_DATA_DIR = Path(__file__).parent / "data"
_DATA_DIR.mkdir(exist_ok=True)
_FILE = _DATA_DIR / "links.json"


def _read() -> list[dict]:
    if not _FILE.exists():
        return []
    return json.loads(_FILE.read_text())


def _write(items: list[dict]) -> None:
    _FILE.write_text(json.dumps(items, indent=2))


def list_links() -> list[dict]:
    items = _read()
    items.sort(key=lambda i: i["created_at"], reverse=True)
    return items


def create_link(url: str, title: str = "") -> dict:
    items = _read()
    link = {
        "id": uuid.uuid4().hex[:12],
        "url": url,
        "title": title,
        "created_at": datetime.utcnow().isoformat(),
    }
    items.append(link)
    _write(items)
    return link


def update_link(link_id: str, updates: dict) -> Optional[dict]:
    items = _read()
    for link in items:
        if link["id"] == link_id:
            for k in ("url", "title"):
                if k in updates and updates[k] is not None:
                    link[k] = updates[k]
            _write(items)
            return link
    return None


def delete_link(link_id: str) -> bool:
    items = _read()
    new = [i for i in items if i["id"] != link_id]
    if len(new) == len(items):
        return False
    _write(new)
    return True
