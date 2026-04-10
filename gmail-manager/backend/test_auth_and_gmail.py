"""Tests for auth endpoints, session enforcement, and Gmail passthrough endpoints."""

import pytest
from unittest.mock import MagicMock, patch
from conftest import FAKE_TOKEN


# ===================================================================
# Auth enforcement
# ===================================================================

class TestAuthEnforcement:
    def test_missing_token_returns_401(self, unauthed_client):
        r = unauthed_client.get("/auth/me")
        assert r.status_code == 401

    def test_missing_token_on_gmail_endpoint(self, unauthed_client):
        r = unauthed_client.get("/gmail/overview")
        assert r.status_code == 401

    def test_config_status_does_not_need_auth(self, unauthed_client):
        r = unauthed_client.get("/config/status")
        assert r.status_code == 200

    def test_rules_do_not_need_auth(self, unauthed_client):
        # Rules endpoints don't require session tokens
        r = unauthed_client.get("/rules")
        assert r.status_code == 200


# ===================================================================
# auth/me
# ===================================================================

class TestGetMe:
    def test_returns_profile(self, client, gmail_mock):
        r = client.get("/auth/me")
        assert r.status_code == 200
        data = r.json()
        assert data["email"] == "user@example.com"
        assert data["total_messages"] == 5000
        assert data["storage_used_bytes"] == 1_000_000_000

    def test_calls_gmail_service(self, client, gmail_mock):
        client.get("/auth/me")
        gmail_mock.get_user_profile.assert_called_once()
        gmail_mock.get_inbox_overview.assert_called_once()


# ===================================================================
# auth/logout
# ===================================================================

class TestLogout:
    def test_logout_returns_ok(self, client):
        with patch("auth.delete_session") as mock_del:
            r = client.post("/auth/logout")
            assert r.status_code == 200
            assert r.json() == {"ok": True}
            mock_del.assert_called_once_with(FAKE_TOKEN)


# ===================================================================
# Gmail passthrough endpoints
# ===================================================================

class TestGmailEndpoints:
    def test_overview(self, client, gmail_mock):
        r = client.get("/gmail/overview")
        assert r.status_code == 200
        assert r.json()["total_messages"] == 5000

    def test_top_senders(self, client, gmail_mock):
        r = client.get("/gmail/top-senders?limit=10")
        assert r.status_code == 200
        gmail_mock.get_top_senders.assert_called_once_with(10)

    def test_search(self, client, gmail_mock):
        r = client.get("/gmail/search?query=from:test@x.com&limit=100")
        assert r.status_code == 200
        gmail_mock.search_emails.assert_called_once_with("from:test@x.com", 100)

    def test_search_limit_capped_at_500(self, client, gmail_mock):
        client.get("/gmail/search?query=test&limit=9999")
        gmail_mock.search_emails.assert_called_once_with("test", 500)

    def test_messages_metadata(self, client, gmail_mock):
        gmail_mock.get_messages_metadata.return_value = [
            {"id": "m1", "sender": "a@x.com", "subject": "hi", "date": "2024-01-01", "size_bytes": 1000}
        ]
        r = client.post("/gmail/messages", json={"email_ids": ["m1"]})
        assert r.status_code == 200
        assert len(r.json()["messages"]) == 1


# ===================================================================
# Actions endpoints
# ===================================================================

class TestActionEndpoints:
    def test_delete(self, client, gmail_mock):
        r = client.post("/actions/delete",
                        json={"email_ids": ["a", "b"]},
                        headers={"X-Approved": "1"})
        assert r.status_code == 200
        gmail_mock.delete_emails.assert_called_once()

    def test_block(self, client, gmail_mock):
        gmail_mock.delete_emails.return_value = {"deleted": 3, "errors": []}
        gmail_mock.search_emails.return_value = {
            "emails": [{"id": "e1"}, {"id": "e2"}, {"id": "e3"}],
            "total_found": 3,
        }
        r = client.post("/actions/block",
                        json={"sender_email": "spam@x.com"},
                        headers={"X-Approved": "1"})
        assert r.status_code == 200
        gmail_mock.create_block_filter.assert_called_once_with("spam@x.com")
