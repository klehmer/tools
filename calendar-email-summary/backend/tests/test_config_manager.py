"""Tests for config_manager module."""
import os
from pathlib import Path
from unittest.mock import patch

import pytest

import config_manager


@pytest.fixture(autouse=True)
def _temp_env(tmp_path, monkeypatch):
    """Point config_manager at a temporary .env file."""
    env_path = tmp_path / ".env"
    monkeypatch.setattr(config_manager, "ENV_PATH", env_path)
    yield env_path


class TestReadEnv:
    def test_missing_file_returns_empty(self):
        assert config_manager._read_env() == {}

    def test_parses_key_value_pairs(self, _temp_env):
        _temp_env.write_text("FOO=bar\nBAZ=qux\n")
        result = config_manager._read_env()
        assert result == {"FOO": "bar", "BAZ": "qux"}

    def test_skips_comments_and_blanks(self, _temp_env):
        _temp_env.write_text("# comment\n\nKEY=value\n")
        assert config_manager._read_env() == {"KEY": "value"}

    def test_handles_equals_in_value(self, _temp_env):
        _temp_env.write_text("URL=http://host:8000/path?a=1\n")
        assert config_manager._read_env() == {"URL": "http://host:8000/path?a=1"}


class TestGetConfig:
    def test_returns_all_fields(self, _temp_env):
        _temp_env.write_text("GOOGLE_CLIENT_ID=abc\nGOOGLE_CLIENT_SECRET=secret123\n")
        cfg = config_manager.get_config()
        assert set(cfg.keys()) == set(config_manager.FIELDS)
        assert cfg["GOOGLE_CLIENT_ID"]["value"] == "abc"
        assert cfg["GOOGLE_CLIENT_ID"]["configured"] is True

    def test_masks_secrets(self, _temp_env):
        _temp_env.write_text("GOOGLE_CLIENT_SECRET=s3cret\nANTHROPIC_API_KEY=ak123\n")
        cfg = config_manager.get_config()
        assert cfg["GOOGLE_CLIENT_SECRET"]["value"] == "***"
        assert cfg["GOOGLE_CLIENT_SECRET"]["configured"] is True
        assert cfg["ANTHROPIC_API_KEY"]["value"] == "***"

    def test_unconfigured_secret_shows_empty(self, _temp_env):
        _temp_env.write_text("")
        # Ensure env vars cleared for this field
        os.environ.pop("GOOGLE_CLIENT_SECRET", None)
        cfg = config_manager.get_config()
        assert cfg["GOOGLE_CLIENT_SECRET"]["value"] == ""
        assert cfg["GOOGLE_CLIENT_SECRET"]["configured"] is False

    def test_placeholder_counts_as_not_configured(self, _temp_env):
        _temp_env.write_text("GOOGLE_CLIENT_ID=your_google_client_id_here\n")
        os.environ.pop("GOOGLE_CLIENT_ID", None)
        cfg = config_manager.get_config()
        assert cfg["GOOGLE_CLIENT_ID"]["configured"] is False


class TestIsConfigured:
    def test_true_with_anthropic_provider_and_key(self, _temp_env):
        _temp_env.write_text("AI_PROVIDER=anthropic\nANTHROPIC_API_KEY=key\n")
        assert config_manager.is_configured() is True

    def test_true_with_claude_code_no_key(self, _temp_env):
        _temp_env.write_text("AI_PROVIDER=claude-code\n")
        assert config_manager.is_configured() is True

    def test_true_with_codex_no_key(self, _temp_env):
        _temp_env.write_text("AI_PROVIDER=codex\n")
        assert config_manager.is_configured() is True

    def test_true_with_openai_provider_and_key(self, _temp_env):
        _temp_env.write_text("AI_PROVIDER=openai\nOPENAI_API_KEY=key\n")
        assert config_manager.is_configured() is True

    def test_false_when_no_provider_set(self, _temp_env, monkeypatch):
        _temp_env.write_text("")
        monkeypatch.delenv("AI_PROVIDER", raising=False)
        assert config_manager.is_configured() is False

    def test_false_when_anthropic_missing_key(self, _temp_env, monkeypatch):
        _temp_env.write_text("AI_PROVIDER=anthropic\n")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        assert config_manager.is_configured() is False

    def test_false_when_anthropic_placeholder_key(self, _temp_env, monkeypatch):
        _temp_env.write_text("AI_PROVIDER=anthropic\nANTHROPIC_API_KEY=your_anthropic_api_key_here\n")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        assert config_manager.is_configured() is False

    def test_false_when_openai_missing_key(self, _temp_env, monkeypatch):
        _temp_env.write_text("AI_PROVIDER=openai\n")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        assert config_manager.is_configured() is False

    def test_false_when_openai_placeholder_key(self, _temp_env, monkeypatch):
        _temp_env.write_text("AI_PROVIDER=openai\nOPENAI_API_KEY=your_openai_api_key_here\n")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        assert config_manager.is_configured() is False

    def test_does_not_require_google_creds(self, _temp_env):
        _temp_env.write_text("AI_PROVIDER=claude-code\n")
        assert config_manager.is_configured() is True


class TestIsGoogleConfigured:
    def test_true_when_both_set(self, _temp_env):
        _temp_env.write_text("GOOGLE_CLIENT_ID=id\nGOOGLE_CLIENT_SECRET=secret\n")
        assert config_manager.is_google_configured() is True

    def test_false_when_id_missing(self, _temp_env, monkeypatch):
        _temp_env.write_text("GOOGLE_CLIENT_SECRET=secret\n")
        monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
        assert config_manager.is_google_configured() is False

    def test_false_when_secret_missing(self, _temp_env, monkeypatch):
        _temp_env.write_text("GOOGLE_CLIENT_ID=id\n")
        monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
        assert config_manager.is_google_configured() is False

    def test_false_when_placeholder(self, _temp_env, monkeypatch):
        _temp_env.write_text("GOOGLE_CLIENT_ID=your_google_client_id_here\nGOOGLE_CLIENT_SECRET=s\n")
        monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
        assert config_manager.is_google_configured() is False

    def test_false_when_empty(self, _temp_env, monkeypatch):
        _temp_env.write_text("")
        monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
        monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
        assert config_manager.is_google_configured() is False


class TestSaveConfig:
    def test_writes_env_file(self, _temp_env, monkeypatch):
        config_manager.save_config({"GOOGLE_CLIENT_ID": "new-id", "BACKEND_URL": "http://x"})
        content = _temp_env.read_text()
        assert "GOOGLE_CLIENT_ID=new-id" in content
        assert "BACKEND_URL=http://x" in content

    def test_ignores_unknown_fields(self, _temp_env):
        config_manager.save_config({"UNKNOWN_FIELD": "should-not-appear"})
        content = _temp_env.read_text()
        assert "UNKNOWN_FIELD" not in content

    def test_does_not_overwrite_with_mask(self, _temp_env):
        _temp_env.write_text("GOOGLE_CLIENT_SECRET=real-secret\n")
        config_manager.save_config({"GOOGLE_CLIENT_SECRET": "***"})
        content = _temp_env.read_text()
        assert "GOOGLE_CLIENT_SECRET=real-secret" in content

    def test_updates_os_environ(self, _temp_env, monkeypatch):
        config_manager.save_config({"GOOGLE_CLIENT_ID": "env-val"})
        assert os.environ["GOOGLE_CLIENT_ID"] == "env-val"
