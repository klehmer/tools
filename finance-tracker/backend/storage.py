"""JSON-file storage for sources, accounts, transactions, and goals.

A **source** is anything that can produce accounts + transactions. There are
three kinds:

- ``plaid``    — a linked Plaid Item, ``config`` holds ``{access_token,
                 institution_id, transactions_cursor}``
- ``simplefin``— a SimpleFIN bridge connection, ``config`` holds
                 ``{access_url}``
- ``manual``   — user-entered accounts + CSV imports. ``config`` is empty.

A user can mix and match: e.g. real-time Robinhood via Plaid + two checking
accounts via SimpleFIN + a cash envelope + a rollover IRA tracked manually.
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
PLAID_CONFIG_FILE = DATA_DIR / "plaid_config.json"
SOURCES_FILE = DATA_DIR / "sources.json"
ACCOUNTS_FILE = DATA_DIR / "accounts.json"
TRANSACTIONS_FILE = DATA_DIR / "transactions.json"
INVESTMENTS_FILE = DATA_DIR / "investments.json"
LIABILITIES_FILE = DATA_DIR / "liabilities.json"
GOALS_FILE = DATA_DIR / "goals.json"
META_FILE = DATA_DIR / "meta.json"
CATEGORY_RULES_FILE = DATA_DIR / "category_rules.json"
FREQUENCY_RULES_FILE = DATA_DIR / "frequency_rules.json"

# One-time migration from the old Plaid-only layout.
LEGACY_ITEMS_FILE = DATA_DIR / "items.json"

_lock = threading.RLock()


def _ensure_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _secure(path: Path) -> None:
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


def _migrate_legacy_items_if_present() -> None:
    """Convert old ``items.json`` (Plaid-only) to ``sources.json`` once."""
    if SOURCES_FILE.exists() or not LEGACY_ITEMS_FILE.exists():
        return
    try:
        with LEGACY_ITEMS_FILE.open() as f:
            legacy = json.load(f)
    except (json.JSONDecodeError, OSError):
        return
    sources = []
    for i in legacy:
        sources.append(
            {
                "source_id": i.get("item_id"),
                "kind": "plaid",
                "display_name": i.get("institution_name") or "Plaid",
                "linked_at": i.get("linked_at") or datetime.utcnow().isoformat(),
                "last_synced_at": i.get("last_synced_at"),
                "error": i.get("error"),
                "config": {
                    "access_token": i.get("access_token"),
                    "institution_id": i.get("institution_id"),
                    "transactions_cursor": i.get("transactions_cursor"),
                },
            }
        )
    _write(SOURCES_FILE, sources, secure=True)
    # Migrate item_id → source_id on cached accounts + transactions.
    if ACCOUNTS_FILE.exists():
        accs = _read(ACCOUNTS_FILE, [])
        for a in accs:
            if "source_id" not in a and "item_id" in a:
                a["source_id"] = a.pop("item_id")
                a["source_kind"] = "plaid"
        _write(ACCOUNTS_FILE, accs)
    if TRANSACTIONS_FILE.exists():
        txns = _read(TRANSACTIONS_FILE, [])
        for t in txns:
            if "source_id" not in t and "item_id" in t:
                t["source_id"] = t.pop("item_id")
        _write(TRANSACTIONS_FILE, txns)
    try:
        LEGACY_ITEMS_FILE.unlink()
    except OSError:
        pass


# --- Plaid configuration (client_id / secret / env) ------------------------

def get_plaid_config() -> Dict[str, Any]:
    with _lock:
        return _read(PLAID_CONFIG_FILE, {})


def save_plaid_config(
    client_id: Optional[str] = None,
    secret: Optional[str] = None,
    env: Optional[str] = None,
    products: Optional[List[str]] = None,
    country_codes: Optional[List[str]] = None,
    client_name: Optional[str] = None,
) -> Dict[str, Any]:
    with _lock:
        cfg = get_plaid_config()
        if client_id is not None:
            cfg["client_id"] = client_id.strip()
        if secret is not None:
            cfg["secret"] = secret.strip()
        if env is not None:
            cfg["env"] = env.strip().lower()
        if products is not None:
            cfg["products"] = products
        if country_codes is not None:
            cfg["country_codes"] = country_codes
        if client_name is not None:
            cfg["client_name"] = client_name
        _write(PLAID_CONFIG_FILE, cfg, secure=True)
        return cfg


def clear_plaid_config() -> None:
    with _lock:
        _write(PLAID_CONFIG_FILE, {}, secure=True)


# --- Sources (linked institutions of any kind) -----------------------------

def list_sources() -> List[Dict[str, Any]]:
    with _lock:
        _migrate_legacy_items_if_present()
        return _read(SOURCES_FILE, [])


def get_source(source_id: str) -> Optional[Dict[str, Any]]:
    for s in list_sources():
        if s["source_id"] == source_id:
            return s
    return None


def get_source_by_config(key: str, value: str) -> Optional[Dict[str, Any]]:
    """Find an existing source by a config field — used to avoid duplicate
    SimpleFIN connections, etc."""
    for s in list_sources():
        if (s.get("config") or {}).get(key) == value:
            return s
    return None


def save_source(
    source_id: str,
    kind: str,
    display_name: str,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    with _lock:
        sources = list_sources()
        now = datetime.utcnow().isoformat()
        existing = next((s for s in sources if s["source_id"] == source_id), None)
        if existing:
            existing["kind"] = kind
            existing["display_name"] = display_name or existing.get("display_name")
            existing["config"] = {**existing.get("config", {}), **config}
            record = existing
        else:
            record = {
                "source_id": source_id,
                "kind": kind,
                "display_name": display_name,
                "config": config,
                "linked_at": now,
                "last_synced_at": None,
                "error": None,
            }
            sources.append(record)
        _write(SOURCES_FILE, sources, secure=True)
        return record


def update_source(source_id: str, **fields: Any) -> None:
    with _lock:
        sources = list_sources()
        for s in sources:
            if s["source_id"] == source_id:
                # ``config`` updates merge rather than replace.
                if "config" in fields and isinstance(fields["config"], dict):
                    s["config"] = {**s.get("config", {}), **fields.pop("config")}
                s.update(fields)
                break
        _write(SOURCES_FILE, sources, secure=True)


def delete_source(source_id: str) -> None:
    with _lock:
        sources = [s for s in list_sources() if s["source_id"] != source_id]
        _write(SOURCES_FILE, sources, secure=True)

        accounts = [a for a in list_accounts() if a.get("source_id") != source_id]
        _write(ACCOUNTS_FILE, accounts)

        txns = [t for t in list_transactions() if t.get("source_id") != source_id]
        _write(TRANSACTIONS_FILE, txns)

        holdings = _read(INVESTMENTS_FILE, {})
        holdings.pop(source_id, None)
        _write(INVESTMENTS_FILE, holdings)

        liab = _read(LIABILITIES_FILE, {})
        liab.pop(source_id, None)
        _write(LIABILITIES_FILE, liab)


def get_or_create_default_manual_source() -> Dict[str, Any]:
    """Every user gets a single ``Manual accounts`` source on first use, so
    they don't have to think about source-vs-account hierarchy for hand-
    entered data."""
    for s in list_sources():
        if s["kind"] == "manual":
            return s
    return save_source(
        source_id=f"manual_{int(datetime.utcnow().timestamp() * 1000)}",
        kind="manual",
        display_name="Manual accounts",
        config={},
    )


# --- Accounts ---------------------------------------------------------------

def list_accounts() -> List[Dict[str, Any]]:
    with _lock:
        return _read(ACCOUNTS_FILE, [])


def get_account(account_id: str) -> Optional[Dict[str, Any]]:
    for a in list_accounts():
        if a["account_id"] == account_id:
            return a
    return None


def replace_accounts_for_source(source_id: str, accounts: List[Dict[str, Any]]) -> None:
    with _lock:
        existing = [a for a in list_accounts() if a.get("source_id") != source_id]
        existing.extend(accounts)
        _write(ACCOUNTS_FILE, existing)


def upsert_account(account: Dict[str, Any]) -> Dict[str, Any]:
    with _lock:
        accs = list_accounts()
        for i, a in enumerate(accs):
            if a["account_id"] == account["account_id"]:
                accs[i] = {**a, **account}
                _write(ACCOUNTS_FILE, accs)
                return accs[i]
        accs.append(account)
        _write(ACCOUNTS_FILE, accs)
        return account


def delete_account(account_id: str) -> None:
    with _lock:
        accs = [a for a in list_accounts() if a["account_id"] != account_id]
        _write(ACCOUNTS_FILE, accs)
        txns = [t for t in list_transactions() if t.get("account_id") != account_id]
        _write(TRANSACTIONS_FILE, txns)


# --- Transactions -----------------------------------------------------------

def list_transactions() -> List[Dict[str, Any]]:
    with _lock:
        return _read(TRANSACTIONS_FILE, [])


def upsert_transactions(
    source_id: str,
    added: List[Dict[str, Any]],
    modified: List[Dict[str, Any]] | None = None,
    removed_ids: List[str] | None = None,
) -> int:
    modified = modified or []
    removed_ids = removed_ids or []
    with _lock:
        txns = list_transactions()
        by_id = {t["transaction_id"]: t for t in txns}
        n_added = 0
        for t in added:
            t["source_id"] = source_id
            if t["transaction_id"] not in by_id:
                n_added += 1
            by_id[t["transaction_id"]] = t
        for t in modified:
            t["source_id"] = source_id
            by_id[t["transaction_id"]] = t
        for tid in removed_ids:
            by_id.pop(tid, None)
        _write(TRANSACTIONS_FILE, list(by_id.values()))
        return n_added


# --- Investments / liabilities ---------------------------------------------

def save_investments(source_id: str, payload: Dict[str, Any]) -> None:
    with _lock:
        all_holdings = _read(INVESTMENTS_FILE, {})
        all_holdings[source_id] = payload
        _write(INVESTMENTS_FILE, all_holdings)


def list_investments() -> Dict[str, Any]:
    with _lock:
        return _read(INVESTMENTS_FILE, {})


def save_liabilities(source_id: str, payload: Dict[str, Any]) -> None:
    with _lock:
        all_liab = _read(LIABILITIES_FILE, {})
        all_liab[source_id] = payload
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


# --- Category rules ----------------------------------------------------------

def get_category_rules() -> Dict[str, str]:
    with _lock:
        return _read(CATEGORY_RULES_FILE, {})


def save_category_rule(merchant: str, category: str) -> Dict[str, str]:
    with _lock:
        rules = get_category_rules()
        rules[merchant] = category
        _write(CATEGORY_RULES_FILE, rules)
        return rules


def delete_category_rule(merchant: str) -> None:
    with _lock:
        rules = get_category_rules()
        rules.pop(merchant, None)
        _write(CATEGORY_RULES_FILE, rules)


# --- Frequency rules ---------------------------------------------------------

def get_frequency_rules() -> Dict[str, str]:
    with _lock:
        return _read(FREQUENCY_RULES_FILE, {})


def save_frequency_rule(merchant: str, frequency: str) -> Dict[str, str]:
    with _lock:
        rules = get_frequency_rules()
        rules[merchant] = frequency
        _write(FREQUENCY_RULES_FILE, rules)
        return rules


def delete_frequency_rule(merchant: str) -> None:
    with _lock:
        rules = get_frequency_rules()
        rules.pop(merchant, None)
        _write(FREQUENCY_RULES_FILE, rules)
