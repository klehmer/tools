"""Tests for auth module."""
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import auth


@pytest.fixture(autouse=True)
def _isolate_auth_state(tmp_path, monkeypatch):
    """Use temp files and clean session state for each test."""
    monkeypatch.setattr(auth, "_FLOWS_FILE", tmp_path / "flows.json")
    monkeypatch.setattr(auth, "_SESSIONS_FILE", tmp_path / "sessions.json")
    auth._sessions.clear()


class TestVerifiers:
    def test_save_and_pop_verifier(self):
        auth._save_verifier("state1", "verifier1")
        assert auth._pop_verifier("state1") == "verifier1"
        # Second pop returns None (consumed)
        assert auth._pop_verifier("state1") is None

    def test_multiple_verifiers(self):
        auth._save_verifier("s1", "v1")
        auth._save_verifier("s2", "v2")
        assert auth._pop_verifier("s2") == "v2"
        assert auth._pop_verifier("s1") == "v1"

    def test_missing_verifier_returns_none(self):
        assert auth._pop_verifier("nonexistent") is None


class TestSessions:
    def test_get_credentials_missing_returns_none(self):
        assert auth.get_credentials("no-such-token") is None

    def test_delete_session_removes_token(self, mock_credentials):
        auth._sessions["tok1"] = mock_credentials
        auth.delete_session("tok1")
        assert auth.get_credentials("tok1") is None

    def test_delete_nonexistent_session_is_safe(self):
        auth.delete_session("no-such-token")  # Should not raise

    def test_get_credentials_returns_valid_creds(self, mock_credentials):
        mock_credentials.expired = False
        auth._sessions["tok1"] = mock_credentials
        result = auth.get_credentials("tok1")
        assert result is mock_credentials

    def test_refreshes_expired_creds(self, mock_credentials):
        mock_credentials.expired = True
        mock_credentials.refresh_token = "refresh-tok"
        auth._sessions["tok1"] = mock_credentials
        result = auth.get_credentials("tok1")
        mock_credentials.refresh.assert_called_once()
        assert result is mock_credentials

    def test_removes_session_on_refresh_failure(self, mock_credentials):
        mock_credentials.expired = True
        mock_credentials.refresh_token = "refresh-tok"
        mock_credentials.refresh.side_effect = Exception("refresh failed")
        auth._sessions["tok1"] = mock_credentials
        result = auth.get_credentials("tok1")
        assert result is None
        assert "tok1" not in auth._sessions


class TestGetAuthUrl:
    @patch("auth._build_flow")
    def test_returns_url_string(self, mock_build):
        flow = MagicMock()
        flow.authorization_url.return_value = ("https://accounts.google.com/auth?state=abc", "abc")
        flow.code_verifier = "test-verifier"
        mock_build.return_value = flow

        url = auth.get_auth_url()
        assert url == "https://accounts.google.com/auth?state=abc"
        flow.authorization_url.assert_called_once_with(access_type="offline", prompt="consent")

    @patch("auth._build_flow")
    def test_persists_code_verifier(self, mock_build):
        flow = MagicMock()
        flow.authorization_url.return_value = ("https://auth.url", "state123")
        flow.code_verifier = "my-verifier"
        mock_build.return_value = flow

        auth.get_auth_url()
        assert auth._pop_verifier("state123") == "my-verifier"


class TestExchangeCode:
    @patch("auth._build_flow")
    def test_returns_session_token(self, mock_build):
        flow = MagicMock()
        flow.credentials = MagicMock()
        flow.credentials.to_json.return_value = '{"token": "t"}'
        mock_build.return_value = flow

        # Pre-save a verifier
        auth._save_verifier("state1", "verifier1")

        token = auth.exchange_code("auth-code", "state1")
        assert isinstance(token, str)
        assert len(token) == 36  # UUID format
        flow.fetch_token.assert_called_once_with(code="auth-code", code_verifier="verifier1")

    @patch("auth._build_flow")
    def test_works_without_verifier(self, mock_build):
        flow = MagicMock()
        flow.credentials = MagicMock()
        flow.credentials.to_json.return_value = '{"token": "t"}'
        mock_build.return_value = flow

        token = auth.exchange_code("auth-code", "no-verifier-state")
        flow.fetch_token.assert_called_once_with(code="auth-code")
        assert token in auth._sessions

    @patch("auth._build_flow")
    def test_stores_credentials_in_sessions(self, mock_build):
        creds = MagicMock()
        creds.to_json.return_value = '{"token": "t"}'
        flow = MagicMock()
        flow.credentials = creds
        mock_build.return_value = flow

        token = auth.exchange_code("code", "state")
        assert auth._sessions[token] is creds
