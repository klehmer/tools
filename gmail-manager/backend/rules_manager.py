"""Persisted cleanup rules for the agent and direct actions."""
import json
from pathlib import Path
from typing import Any, Dict, List

_RULES_FILE = Path(__file__).parent / "rules.json"

DEFAULT_RULES: Dict[str, Any] = {
    "require_approval": True,
    "download_before_delete": False,
    "protected_senders": [],
    "protected_keywords": [],
    "custom_instructions": "",
}


def get_rules() -> Dict[str, Any]:
    if _RULES_FILE.exists():
        try:
            data = json.loads(_RULES_FILE.read_text())
            # Merge with defaults so newly added keys are present
            return {**DEFAULT_RULES, **data}
        except Exception:
            pass
    return dict(DEFAULT_RULES)


def save_rules(updates: Dict[str, Any]) -> Dict[str, Any]:
    current = get_rules()
    current.update(updates)
    _RULES_FILE.write_text(json.dumps(current, indent=2))
    return current


def is_sender_protected(sender_email: str) -> bool:
    rules = get_rules()
    protected: List[str] = rules.get("protected_senders", [])
    se = sender_email.lower().strip()
    for p in protected:
        p = p.lower().strip()
        if not p:
            continue
        if p.startswith("@"):
            if se.endswith(p):
                return True
        elif p == se:
            return True
    return False
