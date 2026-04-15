"""Checklist / action-items planner backed by a JSON file."""
import json
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Optional

_DATA_DIR = Path(__file__).parent / "data"
_DATA_DIR.mkdir(exist_ok=True)
_FILE = _DATA_DIR / "checklist.json"


def _read() -> list[dict]:
    if not _FILE.exists():
        return []
    return json.loads(_FILE.read_text())


def _write(items: list[dict]) -> None:
    _FILE.write_text(json.dumps(items, indent=2))


def list_items(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    done: Optional[bool] = None,
) -> list[dict]:
    items = _read()
    if date_from:
        items = [i for i in items if i["date"] >= date_from]
    if date_to:
        items = [i for i in items if i["date"] <= date_to]
    if done is not None:
        items = [i for i in items if i["done"] == done]
    items.sort(key=lambda i: (i["date"], i["sort_order"]))
    return items


def create_item(text: str, item_date: str, sort_order: int = 0, priority: bool = False) -> dict:
    items = _read()
    item = {
        "id": uuid.uuid4().hex[:12],
        "text": text,
        "date": item_date,
        "done": False,
        "priority": priority,
        "sort_order": sort_order,
        "created_at": datetime.utcnow().isoformat(),
    }
    items.append(item)
    _write(items)
    return item


def update_item(item_id: str, updates: dict) -> Optional[dict]:
    items = _read()
    for item in items:
        if item["id"] == item_id:
            for k in ("text", "date", "done", "sort_order", "priority"):
                if k in updates and updates[k] is not None:
                    item[k] = updates[k]
            _write(items)
            return item
    return None


def reorder_items(item_ids: list[str]) -> list[dict]:
    """Bulk reorder: accepts a list of item IDs in the desired order."""
    items = _read()
    id_to_order = {iid: idx for idx, iid in enumerate(item_ids)}
    updated = []
    for item in items:
        if item["id"] in id_to_order:
            item["sort_order"] = id_to_order[item["id"]]
            updated.append(item)
    _write(items)
    return updated


def delete_item(item_id: str) -> bool:
    items = _read()
    new = [i for i in items if i["id"] != item_id]
    if len(new) == len(items):
        return False
    _write(new)
    return True
