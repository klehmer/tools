"""Tests for auth.py — all Google OAuth calls are mocked."""

import json
from unittest.mock import MagicMock, patch
import pytest


# ===================================================================
# Session persistence
# ===================================================================

class TestSessionPersistence:
    def test_load_sessions_empty(self, tmp_path, monkeypatch):
        import auth
        monkeypatch.setattr(auth, "_SESSIONS_FILE", tmp_path / "sessions.json")
        result = auth._load_sessions()
        assert result == {}

    def test_load_sessions_corrupt_file(self, tmp_path, monkeypatch):
        import auth
        sf = tmp_path / "sessions.json"
        sf.write_text("not json{{{")
        monkeypatch.setattr(auth, "_SESSIONS_FILE", sf)
        assert auth._load_sessions() == {}

    def test_save_and_load_roundtrip(self, tmp_path, monkeypatch):
        import auth
        sf = tmp_path / "sessions.json"
        monkeypatch.setattr(auth, "_SESSIONS_FILE", sf)

        # Create a fake credential
        creds = MagicMock()
        creds.to_json.return_value = json.dumps({
            "token": "access_tok",
            "refresh_token": "refresh_tok",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "cid",
            "client_secret": "csec",
            "scopes": ["https://mail.google.com/"],
        })
        auth._sessions["tok1"] = creds
        auth._save_sessions()

        assert sf.exists()
        data = json.loads(sf.read_text())
        assert "tok1" in data


# ===================================================================
# Verifier persistence (PKCE)
# ===================================================================

class TestVerifierPersistence:
    def test_save_and_pop_verifier(self, tmp_path, monkeypatch):
        import auth
        monkeypatch.setattr(auth, "_FLOWS_FILE", tmp_path / "flows.json")
        auth._save_verifier("state123", "verifier_abc")
        v = auth._pop_verifier("state123")
        assert v == "verifier_abc"
        # Second pop returns None
        assert auth._pop_verifier("state123") is None

    def test_load_verifiers_empty(self, tmp_path, monkeypatch):
        import auth
        monkeypatch.setattr(auth, "_FLOWS_FILE", tmp_path / "flows.json")
        assert auth._load_verifiers() == {}

    def test_load_verifiers_corrupt(self, tmp_path, monkeypatch):
        import auth
        f = tmp_path / "flows.json"
        f.write_text("not json")
        monkeypatch.setattr(auth, "_FLOWS_FILE", f)
        assert auth._load_verifiers() == {}


# ===================================================================
# get_auth_url
# ===================================================================

class TestGetAuthUrl:
    @patch("auth._build_flow")
    def test_returns_url_and_saves_verifier(self, mock_flow_builder, tmp_path, monkeypatch):
        import auth
        monkeypatch.setattr(auth, "_FLOWS_FILE", tmp_path / "flows.json")

        flow = MagicMock()
        flow.authorization_url.return_value = ("https://accounts.google.com/auth?state=s1", "s1")
        flow.code_verifier = "cv_test"
        mock_flow_builder.return_value = flow

        url = auth.get_auth_url()
        assert url == "https://accounts.google.com/auth?state=s1"
        # Verifier was persisted
        assert auth._pop_verifier("s1") == "cv_test"


# ===================================================================
# exchange_code
# ===================================================================

class TestExchangeCode:
    @patch("auth._build_flow")
    def test_success(self, mock_flow_builder, tmp_path, monkeypatch):
        import auth
        monkeypatch.setattr(auth, "_SESSIONS_FILE", tmp_path / "sessions.json")
        monkeypatch.setattr(auth, "_FLOWS_FILE", tmp_path / "flows.json")

        # Pre-save a verifier
        auth._save_verifier("state1", "verifier1")

        flow = MagicMock()
        creds = MagicMock()
        creds.to_json.return_value = json.dumps({
            "token": "at", "refresh_token": "rt",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "cid", "client_secret": "csec",
        })
        flow.credentials = creds
        mock_flow_builder.return_value = flow

        token = auth.exchange_code("auth_code_123", "state1")
        assert isinstance(token, str)
        assert len(token) == 36  # UUID
        flow.fetch_token.assert_called_once_with(code="auth_code_123", code_verifier="verifier1")
        # Session saved
        assert token in auth._sessions

    @patch("auth._build_flow")
    def test_without_verifier(self, mock_flow_builder, tmp_path, monkeypatch):
        import auth
        monkeypatch.setattr(auth, "_SESSIONS_FILE", tmp_path / "sessions.json")
        monkeypatch.setattr(auth, "_FLOWS_FILE", tmp_path / "flows.json")

        flow = MagicMock()
        creds = MagicMock()
        creds.to_json.return_value = json.dumps({
            "token": "at", "refresh_token": "rt",
            "token_uri": "u", "client_id": "c", "client_secret": "s",
        })
        flow.credentials = creds
        mock_flow_builder.return_value = flow

        token = auth.exchange_code("code", "unknown_state")
        flow.fetch_token.assert_called_once_with(code="code")
        assert token in auth._sessions

    @patch("auth._build_flow")
    def test_fetch_token_failure_raises(self, mock_flow_builder, tmp_path, monkeypatch):
        import auth
        monkeypatch.setattr(auth, "_SESSIONS_FILE", tmp_path / "sessions.json")
        monkeypatch.setattr(auth, "_FLOWS_FILE", tmp_path / "flows.json")

        flow = MagicMock()
        flow.fetch_token.side_effect = Exception("token exchange failed")
        mock_flow_builder.return_value = flow

        with pytest.raises(Exception, match="token exchange failed"):
            auth.exchange_code("bad_code", "state")


# ===================================================================
# get_credentials
# ===================================================================

class TestGetCredentials:
    def test_returns_none_for_unknown_token(self, tmp_path, monkeypatch):
        import auth
        assert auth.get_credentials("nonexistent") is None

    def test_returns_valid_creds(self, tmp_path, monkeypatch):
        import auth
        creds = MagicMock()
        creds.expired = False
        auth._sessions["valid_tok"] = creds
        result = auth.get_credentials("valid_tok")
        assert result is creds

    def test_refreshes_expired_creds(self, tmp_path, monkeypatch):
        import auth
        monkeypatch.setattr(auth, "_SESSIONS_FILE", tmp_path / "sessions.json")

        creds = MagicMock()
        creds.expired = True
        creds.refresh_token = "rt"
        creds.to_json.return_value = json.dumps({
            "token": "new_at", "refresh_token": "rt",
            "token_uri": "u", "client_id": "c", "client_secret": "s",
        })
        auth._sessions["tok"] = creds

        with patch("auth.Request"):
            result = auth.get_credentials("tok")
        assert result is creds
        creds.refresh.assert_called_once()

    def test_removes_session_on_refresh_failure(self, tmp_path, monkeypatch):
        import auth
        monkeypatch.setattr(auth, "_SESSIONS_FILE", tmp_path / "sessions.json")

        creds = MagicMock()
        creds.expired = True
        creds.refresh_token = "rt"
        creds.refresh.side_effect = Exception("refresh failed")
        creds.to_json.return_value = "{}"
        auth._sessions["bad_tok"] = creds

        with patch("auth.Request"):
            result = auth.get_credentials("bad_tok")
        assert result is None
        assert "bad_tok" not in auth._sessions


# ===================================================================
# delete_session
# ===================================================================

class TestDeleteSession:
    def test_removes_session(self, tmp_path, monkeypatch):
        import auth
        monkeypatch.setattr(auth, "_SESSIONS_FILE", tmp_path / "sessions.json")
        auth._sessions["del_tok"] = MagicMock()
        auth.delete_session("del_tok")
        assert "del_tok" not in auth._sessions

    def test_noop_for_unknown(self, tmp_path, monkeypatch):
        import auth
        monkeypatch.setattr(auth, "_SESSIONS_FILE", tmp_path / "sessions.json")
        auth.delete_session("nonexistent")  # Should not raise


# ===================================================================
# _get_redirect_uri / _build_flow
# ===================================================================

class TestHelpers:
    def test_redirect_uri_default(self, monkeypatch):
        import auth
        monkeypatch.delenv("BACKEND_URL", raising=False)
        assert auth._get_redirect_uri() == "http://localhost:8000/auth/callback"

    def test_redirect_uri_custom(self, monkeypatch):
        import auth
        monkeypatch.setenv("BACKEND_URL", "https://api.example.com")
        assert auth._get_redirect_uri() == "https://api.example.com/auth/callback"

    def test_build_flow(self, monkeypatch):
        import auth
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test_id")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test_secret")
        flow = auth._build_flow()
        assert flow is not None
