"""Notes module backed by a JSON file."""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

_DATA_DIR = Path(__file__).parent / "data"
_DATA_DIR.mkdir(exist_ok=True)
_FILE = _DATA_DIR / "notes.json"


def _read() -> list[dict]:
    if not _FILE.exists():
        return []
    return json.loads(_FILE.read_text())


def _write(items: list[dict]) -> None:
    _FILE.write_text(json.dumps(items, indent=2))


def list_notes(archived: Optional[bool] = None) -> list[dict]:
    items = _read()
    if archived is not None:
        items = [i for i in items if i["archived"] == archived]
    items.sort(key=lambda i: i["updated_at"], reverse=True)
    return items


def create_note(title: str, content: str = "") -> dict:
    items = _read()
    now = datetime.utcnow().isoformat()
    note = {
        "id": uuid.uuid4().hex[:12],
        "title": title,
        "content": content,
        "archived": False,
        "created_at": now,
        "updated_at": now,
    }
    items.append(note)
    _write(items)
    return note


def update_note(note_id: str, updates: dict) -> Optional[dict]:
    items = _read()
    for note in items:
        if note["id"] == note_id:
            for k in ("title", "content", "archived"):
                if k in updates and updates[k] is not None:
                    note[k] = updates[k]
            note["updated_at"] = datetime.utcnow().isoformat()
            _write(items)
            return note
    return None


def get_note(note_id: str) -> Optional[dict]:
    items = _read()
    for note in items:
        if note["id"] == note_id:
            return note
    return None


def delete_note(note_id: str) -> bool:
    items = _read()
    new = [i for i in items if i["id"] != note_id]
    if len(new) == len(items):
        return False
    _write(new)
    return True
