"""
Human-in-the-loop approval queue for autonomous agents.

Flow:
  1. Agent POSTs /approvals/request with proposed delete batch.
  2. Backend stores it as "pending" and returns an approval_id.
  3. User sees it in the dashboard, clicks Approve / Download&Approve / Deny.
  4. Agent polls /approvals/{id} until status != "pending" then acts accordingly.
"""
import json
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

_FILE = Path(tempfile.gettempdir()) / "gmail_manager_approvals.json"


def _load() -> Dict[str, Dict[str, Any]]:
    if _FILE.exists():
        try:
            return json.loads(_FILE.read_text())
        except Exception:
            pass
    return {}


def _save(data: Dict[str, Dict[str, Any]]) -> None:
    try:
        _FILE.write_text(json.dumps(data))
    except Exception:
        pass


def request_approval(
    email_ids: List[str],
    sender: str,
    reason: str,
    suggested_action: str = "delete",
) -> Dict[str, Any]:
    data = _load()
    aid = str(uuid.uuid4())
    record = {
        "id": aid,
        "email_ids": email_ids,
        "sender": sender,
        "reason": reason,
        "suggested_action": suggested_action,
        "status": "pending",  # pending | approved | denied
        "created_at": time.time(),
        "decided_at": None,
    }
    data[aid] = record
    _save(data)
    return record


def list_approvals(status: Optional[str] = None) -> List[Dict[str, Any]]:
    data = _load()
    items = list(data.values())
    if status:
        items = [i for i in items if i["status"] == status]
    return sorted(items, key=lambda x: x["created_at"])


def get_approval(aid: str) -> Optional[Dict[str, Any]]:
    return _load().get(aid)


def decide(aid: str, status: str) -> Optional[Dict[str, Any]]:
    if status not in ("approved", "denied"):
        raise ValueError("status must be 'approved' or 'denied'")
    data = _load()
    if aid not in data:
        return None
    data[aid]["status"] = status
    data[aid]["decided_at"] = time.time()
    _save(data)
    return data[aid]


def cleanup_old(max_age_seconds: float = 86400) -> None:
    """Drop decided approvals older than max_age (default 1 day)."""
    data = _load()
    now = time.time()
    keep = {
        aid: rec
        for aid, rec in data.items()
        if rec["status"] == "pending" or (now - (rec.get("decided_at") or now)) < max_age_seconds
    }
    if len(keep) != len(data):
        _save(keep)
