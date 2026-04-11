"""JSON-file storage for linked items, cached account/transaction data, and goals.

Design notes
------------
- Everything is local-only: no cloud sync, no external DB. A personal finance
  tracker on one machine does not need Postgres.
- Access tokens are secret — they are stored in ``items.json`` with 0600 perms.
- Each linked Plaid ``Item`` (one institution login) owns many accounts and
  transactions. We key almost everything by ``item_id`` / ``account_id``.
"""
from __future__ import annotations

import json
import os
import stat
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

DATA_DIR = Path(__file__).parent / "data"
ITEMS_FILE = DATA_DIR / "items.json"
ACCOUNTS_FILE = DATA_DIR / "accounts.json"
TRANSACTIONS_FILE = DATA_DIR / "transactions.json"
INVESTMENTS_FILE = DATA_DIR / "investments.json"
LIABILITIES_FILE = DATA_DIR / "liabilities.json"
GOALS_FILE = DATA_DIR / "goals.json"
META_FILE = DATA_DIR / "meta.json"

_lock = threading.RLock()


def _ensure_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _secure(path: Path) -> None:
    """Tighten perms on secret-containing files."""
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def _read(path: Path, default: Any) -> Any:
    _ensure_dir()
    if not path.exists():
        return default
    try:
        with path.open() as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def _write(path: Path, data: Any, secure: bool = False) -> None:
    _ensure_dir()
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w") as f:
        json.dump(data, f, indent=2, default=str)
    tmp.replace(path)
    if secure:
        _secure(path)


# --- Items (linked institutions / access tokens) ----------------------------

def list_items() -> List[Dict[str, Any]]:
    with _lock:
        return _read(ITEMS_FILE, [])


def get_item(item_id: str) -> Optional[Dict[str, Any]]:
    for it in list_items():
        if it["item_id"] == item_id:
            return it
    return None


def save_item(
    item_id: str,
    access_token: str,
    institution_name: Optional[str],
    institution_id: Optional[str],
) -> Dict[str, Any]:
    with _lock:
        items = list_items()
        now = datetime.utcnow().isoformat()
        existing = next((i for i in items if i["item_id"] == item_id), None)
        if existing:
            existing["access_token"] = access_token
            existing["institution_name"] = institution_name or existing.get("institution_name")
            existing["institution_id"] = institution_id or existing.get("institution_id")
            record = existing
        else:
            record = {
                "item_id": item_id,
                "access_token": access_token,
                "institution_name": institution_name,
                "institution_id": institution_id,
                "linked_at": now,
                "last_synced_at": None,
                "transactions_cursor": None,
                "error": None,
            }
            items.append(record)
        _write(ITEMS_FILE, items, secure=True)
        return record


def update_item(item_id: str, **fields: Any) -> None:
    with _lock:
        items = list_items()
        for i in items:
            if i["item_id"] == item_id:
                i.update(fields)
                break
        _write(ITEMS_FILE, items, secure=True)


def delete_item(item_id: str) -> None:
    with _lock:
        items = [i for i in list_items() if i["item_id"] != item_id]
        _write(ITEMS_FILE, items, secure=True)

        accounts = [a for a in list_accounts() if a.get("item_id") != item_id]
        _write(ACCOUNTS_FILE, accounts)

        txns = [t for t in list_transactions() if t.get("item_id") != item_id]
        _write(TRANSACTIONS_FILE, txns)

        holdings = _read(INVESTMENTS_FILE, {})
        holdings.pop(item_id, None)
        _write(INVESTMENTS_FILE, holdings)

        liab = _read(LIABILITIES_FILE, {})
        liab.pop(item_id, None)
        _write(LIABILITIES_FILE, liab)


# --- Accounts ---------------------------------------------------------------

def list_accounts() -> List[Dict[str, Any]]:
    with _lock:
        return _read(ACCOUNTS_FILE, [])


def replace_accounts_for_item(item_id: str, accounts: List[Dict[str, Any]]) -> None:
    with _lock:
        existing = [a for a in list_accounts() if a.get("item_id") != item_id]
        existing.extend(accounts)
        _write(ACCOUNTS_FILE, existing)


# --- Transactions -----------------------------------------------------------

def list_transactions() -> List[Dict[str, Any]]:
    with _lock:
        return _read(TRANSACTIONS_FILE, [])


def upsert_transactions(item_id: str, added: List[Dict[str, Any]], modified: List[Dict[str, Any]], removed_ids: List[str]) -> None:
    with _lock:
        txns = list_transactions()
        by_id = {t["transaction_id"]: t for t in txns}
        for t in added + modified:
            t["item_id"] = item_id
            by_id[t["transaction_id"]] = t
        for tid in removed_ids:
            by_id.pop(tid, None)
        _write(TRANSACTIONS_FILE, list(by_id.values()))


# --- Investments / liabilities ---------------------------------------------

def save_investments(item_id: str, payload: Dict[str, Any]) -> None:
    with _lock:
        all_holdings = _read(INVESTMENTS_FILE, {})
        all_holdings[item_id] = payload
        _write(INVESTMENTS_FILE, all_holdings)


def list_investments() -> Dict[str, Any]:
    with _lock:
        return _read(INVESTMENTS_FILE, {})


def save_liabilities(item_id: str, payload: Dict[str, Any]) -> None:
    with _lock:
        all_liab = _read(LIABILITIES_FILE, {})
        all_liab[item_id] = payload
        _write(LIABILITIES_FILE, all_liab)


def list_liabilities() -> Dict[str, Any]:
    with _lock:
        return _read(LIABILITIES_FILE, {})


# --- Goals ------------------------------------------------------------------

def list_goals() -> List[Dict[str, Any]]:
    with _lock:
        return _read(GOALS_FILE, [])


def save_goal(goal: Dict[str, Any]) -> Dict[str, Any]:
    with _lock:
        goals = list_goals()
        if not goal.get("id"):
            goal["id"] = f"goal_{int(datetime.utcnow().timestamp() * 1000)}"
            goal["created_at"] = datetime.utcnow().isoformat()
            goals.append(goal)
        else:
            for i, g in enumerate(goals):
                if g["id"] == goal["id"]:
                    goals[i] = {**g, **goal}
                    break
            else:
                goals.append(goal)
        _write(GOALS_FILE, goals)
        return goal


def delete_goal(goal_id: str) -> None:
    with _lock:
        goals = [g for g in list_goals() if g.get("id") != goal_id]
        _write(GOALS_FILE, goals)


# --- Meta -------------------------------------------------------------------

def get_meta() -> Dict[str, Any]:
    with _lock:
        return _read(META_FILE, {})


def set_meta(**fields: Any) -> Dict[str, Any]:
    with _lock:
        meta = get_meta()
        meta.update(fields)
        _write(META_FILE, meta)
        return meta
