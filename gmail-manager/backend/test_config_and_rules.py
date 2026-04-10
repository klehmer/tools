"""Tests for config_manager, rules_manager, and their API endpoints."""

import json
import pytest
from conftest import FAKE_TOKEN


# ===================================================================
# config_manager unit tests
# ===================================================================

class TestConfigManager:
    def test_is_configured_false_when_no_env(self, tmp_path, monkeypatch):
        import config_manager
        monkeypatch.setattr(config_manager, "ENV_PATH", tmp_path / ".env")
        assert config_manager.is_configured() is False

    def test_is_configured_false_with_placeholders(self, tmp_path, monkeypatch):
        import config_manager
        env = tmp_path / ".env"
        env.write_text(
            "GOOGLE_CLIENT_ID=your_client_id\n"
            "GOOGLE_CLIENT_SECRET=your_secret\n"
            "ANTHROPIC_API_KEY=your_key\n"
        )
        monkeypatch.setattr(config_manager, "ENV_PATH", env)
        assert config_manager.is_configured() is False

    def test_is_configured_true_when_all_set(self, tmp_path, monkeypatch):
        import config_manager
        env = tmp_path / ".env"
        env.write_text(
            "GOOGLE_CLIENT_ID=real_id\n"
            "GOOGLE_CLIENT_SECRET=real_secret\n"
            "ANTHROPIC_API_KEY=sk-real-key\n"
        )
        monkeypatch.setattr(config_manager, "ENV_PATH", env)
        assert config_manager.is_configured() is True

    def test_get_config_masks_secrets(self, tmp_path, monkeypatch):
        import config_manager
        env = tmp_path / ".env"
        env.write_text(
            "GOOGLE_CLIENT_ID=visible_id\n"
            "GOOGLE_CLIENT_SECRET=super_secret\n"
            "ANTHROPIC_API_KEY=sk-key\n"
        )
        monkeypatch.setattr(config_manager, "ENV_PATH", env)
        cfg = config_manager.get_config()
        assert cfg["GOOGLE_CLIENT_ID"]["value"] == "visible_id"
        assert cfg["GOOGLE_CLIENT_ID"]["is_set"] is True
        # Secrets: value hidden but is_set reported
        assert cfg["GOOGLE_CLIENT_SECRET"]["value"] == ""
        assert cfg["GOOGLE_CLIENT_SECRET"]["is_set"] is True

    def test_save_config_creates_and_updates(self, tmp_path, monkeypatch):
        import config_manager
        env = tmp_path / ".env"
        monkeypatch.setattr(config_manager, "ENV_PATH", env)
        config_manager.save_config({"GOOGLE_CLIENT_ID": "new_id"})
        assert "GOOGLE_CLIENT_ID=new_id" in env.read_text()
        # Update existing
        config_manager.save_config({"GOOGLE_CLIENT_ID": "updated_id"})
        content = env.read_text()
        assert "updated_id" in content
        assert content.count("GOOGLE_CLIENT_ID") == 1

    def test_save_config_preserves_comments(self, tmp_path, monkeypatch):
        import config_manager
        env = tmp_path / ".env"
        env.write_text("# A comment\nFOO=bar\n")
        monkeypatch.setattr(config_manager, "ENV_PATH", env)
        config_manager.save_config({"GOOGLE_CLIENT_ID": "id"})
        content = env.read_text()
        assert "# A comment" in content


# ===================================================================
# config API endpoints
# ===================================================================

class TestConfigEndpoints:
    def test_config_status(self, client):
        r = client.get("/config/status")
        assert r.status_code == 200
        # With isolated tmp, .env doesn't exist → not configured
        assert r.json()["configured"] is False

    def test_config_roundtrip(self, client):
        r = client.post("/config", json={
            "GOOGLE_CLIENT_ID": "cid",
            "GOOGLE_CLIENT_SECRET": "csec",
            "ANTHROPIC_API_KEY": "akey",
        })
        assert r.status_code == 200
        assert r.json()["configured"] is True

        r = client.get("/config")
        assert r.json()["GOOGLE_CLIENT_ID"]["is_set"] is True


# ===================================================================
# rules_manager unit tests
# ===================================================================

class TestRulesManager:
    def test_defaults_returned_when_no_file(self):
        import rules_manager
        rules = rules_manager.get_rules()
        assert rules["require_approval"] is True
        assert rules["protected_senders"] == []

    def test_save_and_load(self):
        import rules_manager
        rules_manager.save_rules({"protected_senders": ["admin@corp.com"]})
        r = rules_manager.get_rules()
        assert "admin@corp.com" in r["protected_senders"]

    def test_is_sender_protected_exact(self):
        import rules_manager
        rules_manager.save_rules({"protected_senders": ["boss@corp.com"]})
        assert rules_manager.is_sender_protected("boss@corp.com") is True
        assert rules_manager.is_sender_protected("Boss@Corp.com") is True
        assert rules_manager.is_sender_protected("other@corp.com") is False

    def test_is_sender_protected_domain_wildcard(self):
        import rules_manager
        rules_manager.save_rules({"protected_senders": ["@important.com"]})
        assert rules_manager.is_sender_protected("anyone@important.com") is True
        assert rules_manager.is_sender_protected("anyone@other.com") is False

    def test_merge_with_defaults(self):
        import rules_manager
        rules_manager.save_rules({"custom_instructions": "keep receipts"})
        r = rules_manager.get_rules()
        assert r["custom_instructions"] == "keep receipts"
        # Default fields still present
        assert "require_approval" in r


# ===================================================================
# rules API endpoints
# ===================================================================

class TestRulesEndpoints:
    def test_get_default_rules(self, client):
        r = client.get("/rules")
        assert r.status_code == 200
        assert "require_approval" in r.json()

    def test_update_rules(self, client):
        r = client.post("/rules", json={
            "protected_senders": ["vip@corp.com"],
        })
        assert r.status_code == 200
        assert "vip@corp.com" in r.json()["protected_senders"]
