"""Shared fixtures for all tests."""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Ensure backend package is importable
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(autouse=True)
def _isolate_env(tmp_path, monkeypatch):
    """Ensure tests never read real .env or persist to real /tmp files."""
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    monkeypatch.setenv("BACKEND_URL", "http://localhost:8000")
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:5173")


@pytest.fixture()
def mock_credentials():
    creds = MagicMock()
    creds.expired = False
    creds.refresh_token = "fake-refresh"
    creds.token = "fake-token"
    creds.to_json.return_value = '{"token": "fake-token"}'
    return creds


@pytest.fixture()
def mock_google_service():
    svc = MagicMock()
    svc.get_user_profile.return_value = {
        "email": "test@gmail.com",
        "name": "Test User",
        "picture": None,
    }
    svc.fetch_emails.return_value = [
        {
            "id": "msg1",
            "from": "alice@example.com",
            "to": "test@gmail.com",
            "subject": "Urgent: Q1 numbers",
            "date": "Mon, 07 Apr 2026 09:00:00 -0700",
            "snippet": "Please review the Q1 report attached.",
            "labels": ["INBOX"],
        },
        {
            "id": "msg2",
            "from": "newsletter@shop.com",
            "to": "test@gmail.com",
            "subject": "50% off everything!",
            "date": "Mon, 07 Apr 2026 08:00:00 -0700",
            "snippet": "Limited time offer ...",
            "labels": ["INBOX", "CATEGORY_PROMOTIONS"],
        },
    ]
    svc.fetch_events.return_value = [
        {
            "id": "evt1",
            "summary": "Team standup",
            "description": "Daily sync",
            "location": None,
            "start": "2026-04-09T09:00:00-07:00",
            "end": "2026-04-09T09:30:00-07:00",
            "attendees": ["bob@example.com", "carol@example.com"],
            "organizer": "test@gmail.com",
            "hangoutLink": "https://meet.google.com/abc",
            "status": "confirmed",
        },
    ]
    return svc


@pytest.fixture()
def client(mock_google_service):
    """TestClient with GoogleService dependency overridden."""
    from main import app, get_google

    app.dependency_overrides[get_google] = lambda: mock_google_service
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def raw_client():
    """TestClient with NO dependency overrides (real auth enforced)."""
    from main import app

    app.dependency_overrides.clear()
    with TestClient(app) as c:
        yield c
