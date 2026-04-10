"""Shared fixtures for backend tests."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient


# ---------------------------------------------------------------------------
# Isolate all temp-file state into a per-test directory so tests never leak
# into one another or touch the real report/session/approval files.
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolate_tmp(tmp_path, monkeypatch):
    """Redirect every temp-file path in the app to a fresh tmp dir."""

    # main.py globals
    import main
    monkeypatch.setattr(main, "_REPORT_FILE", tmp_path / "report.json")
    monkeypatch.setattr(main, "_UNSUB_FILE", tmp_path / "unsub.json")
    monkeypatch.setattr(main, "_LOG_FILE", tmp_path / "agent.log")

    # approvals module
    import approvals
    monkeypatch.setattr(approvals, "_FILE", tmp_path / "approvals.json")

    # rules_manager — redirect rules file
    import rules_manager
    monkeypatch.setattr(rules_manager, "_RULES_FILE", tmp_path / "rules.json")

    # auth — redirect session store
    import auth
    monkeypatch.setattr(auth, "_SESSIONS_FILE", tmp_path / "sessions.json")
    monkeypatch.setattr(auth, "_FLOWS_FILE", tmp_path / "flows.json")

    # config_manager — redirect .env
    import config_manager
    monkeypatch.setattr(config_manager, "ENV_PATH", tmp_path / ".env")

    yield


# ---------------------------------------------------------------------------
# Fake session token & Gmail service
# ---------------------------------------------------------------------------

FAKE_TOKEN = "test-session-token-abc123"


def _fake_gmail():
    """Return a MagicMock GmailService with sane defaults."""
    g = MagicMock()
    g.get_user_profile.return_value = {
        "email": "user@example.com",
        "name": "Test User",
        "picture": None,
    }
    g.get_inbox_overview.return_value = {
        "email_address": "user@example.com",
        "total_messages": 5000,
        "total_threads": 3000,
        "storage_used_bytes": 1_000_000_000,
        "storage_limit_bytes": 15_000_000_000,
    }
    g.get_top_senders.return_value = {
        "senders": [
            {
                "sender": "noreply@example.com",
                "count": 200,
                "size_mb": 50.0,
                "email_ids": [f"id{i}" for i in range(200)],
                "oldest_date": "2020-01-01",
                "newest_date": "2024-06-01",
            }
        ],
        "total_sampled": 200,
    }
    g.search_emails.return_value = {"emails": [], "total_found": 0}
    g.delete_emails.return_value = {"deleted": 5, "errors": []}
    g.create_block_filter.return_value = {
        "success": True,
        "filter_id": "filter123",
    }
    return g


@pytest.fixture
def gmail_mock():
    return _fake_gmail()


@pytest.fixture
def client(gmail_mock):
    """TestClient with auth bypassed — every request that needs a session
    token just works and gets the mocked GmailService."""
    from main import app, get_gmail, get_session_token

    app.dependency_overrides[get_session_token] = lambda: FAKE_TOKEN
    app.dependency_overrides[get_gmail] = lambda: gmail_mock

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture
def unauthed_client():
    """TestClient with NO auth overrides — for testing auth-required paths."""
    from main import app
    app.dependency_overrides.clear()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
