"""Tests for the agents module."""
import os
import time

import pytest

import agents


@pytest.fixture(autouse=True)
def _temp_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(agents, "_FILE", tmp_path / "agents.json")
    monkeypatch.setattr(agents, "_runs", {})
    monkeypatch.setattr(agents, "_launch_counts", {})
    yield
    agents.kill_all()


def _wait(predicate, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


class TestConfigs:
    def test_create_list_update_delete(self):
        a = agents.create_agent("QA", runtime="claude", model="claude-opus-5-5", prompt="Test it")
        assert agents.list_agents() == [a]
        updated = agents.update_agent(a["id"], {"name": "QA 2", "model": None})
        assert updated["name"] == "QA 2"
        assert updated["model"] == "claude-opus-5-5"
        assert agents.delete_agent(a["id"]) is True
        assert agents.list_agents() == []

    def test_reorder(self):
        a = agents.create_agent("A")
        b = agents.create_agent("B")
        c = agents.create_agent("C")
        assert [x["name"] for x in agents.reorder_agents([c["id"], a["id"], b["id"]])] == ["C", "A", "B"]
        # New agents land after the manually ordered ones
        agents.create_agent("D")
        assert [x["name"] for x in agents.list_agents()] == ["C", "A", "B", "D"]

    def test_update_and_delete_missing(self):
        assert agents.update_agent("nope", {"name": "x"}) is None
        assert agents.delete_agent("nope") is False


class TestBuildCommand:
    def test_runtime_default_template(self):
        agent = {"runtime": "claude", "model": "claude-opus-5-5", "prompt": "You are a QA engineer", "command": ""}
        assert agents.build_command(agent) == ["claude", "--model", "claude-opus-5-5", "You are a QA engineer"]

    def test_empty_values_drop_their_flag(self):
        agent = {"runtime": "opencode", "model": "", "prompt": "", "command": ""}
        assert agents.build_command(agent) == ["opencode", "mini"]

    def test_custom_command_overrides_runtime(self):
        agent = {"runtime": "claude", "model": "m", "prompt": "it's a 'prompt'", "command": "tool run --m={model} {prompt}"}
        assert agents.build_command(agent) == ["tool", "run", "--m=m", "it's a 'prompt'"]


class TestRuns:
    def _agent(self, command, **kw):
        return agents.create_agent("Echo", runtime="custom", command=command, **kw)

    def test_launch_captures_output_and_exit_code(self, tmp_path):
        a = self._agent("sh -c 'echo hello-agent; exit 3'", working_dir=str(tmp_path))
        run = agents.launch(a["id"])
        assert run.name == "Echo #1"
        assert _wait(lambda: not run.running)
        assert run.exit_code == 3
        assert b"hello-agent" in run.attach(lambda d: None)

    def test_multiple_instances_are_numbered(self, tmp_path):
        a = self._agent("sleep 30", working_dir=str(tmp_path))
        first, second = agents.launch(a["id"]), agents.launch(a["id"])
        assert [r["name"] for r in agents.list_runs()] == ["Echo #1", "Echo #2"]
        assert first.running and second.running

    def test_input_reaches_process_and_listener_gets_output(self, tmp_path):
        a = self._agent("cat", working_dir=str(tmp_path))
        run = agents.launch(a["id"])
        chunks = []
        run.attach(chunks.append)
        run.write(b"ping\n")
        assert _wait(lambda: b"ping" in b"".join(c for c in chunks if c))

    def test_kill_stops_process_group(self, tmp_path):
        a = self._agent("sh -c 'sleep 30 & wait'", working_dir=str(tmp_path))
        run = agents.launch(a["id"])
        assert agents.kill_run(run.id)["id"] == run.id
        assert _wait(lambda: not run.running)
        assert agents.remove_run(run.id) is True
        assert agents.list_runs() == []

    def test_agent_does_not_inherit_app_secrets(self, tmp_path, monkeypatch):
        monkeypatch.setattr(agents, "dotenv_values", lambda path: {"ANTHROPIC_API_KEY": "x"})
        a = self._agent("sh -c 'echo key=[$ANTHROPIC_API_KEY] term=$TERM'", working_dir=str(tmp_path))
        run = agents.launch(a["id"])
        assert _wait(lambda: not run.running)
        out = run.attach(lambda d: None)
        assert b"key=[]" in out and b"term=xterm-256color" in out

    def test_launch_errors(self, tmp_path):
        with pytest.raises(LookupError):
            agents.launch("missing")
        a = self._agent("true", working_dir=str(tmp_path / "nope"))
        with pytest.raises(ValueError):
            agents.launch(a["id"])


class TestListModels:
    def test_claude_models_are_static(self):
        assert "claude-opus-5-5" in agents.list_models("claude")

    def test_opencode_models_come_from_cli(self, monkeypatch):
        from unittest.mock import MagicMock
        monkeypatch.setattr(agents, "_models_cache", {})
        out = "fireworks-ai/accounts/fireworks/models/kimi-k3p1-pro\nanthropic/claude-opus-5-5\n\nsome warning line\n"
        monkeypatch.setattr(agents.subprocess, "run", lambda *a, **k: MagicMock(returncode=0, stdout=out))
        assert agents.list_models("opencode") == [
            "fireworks-ai/accounts/fireworks/models/kimi-k3p1-pro", "anthropic/claude-opus-5-5"]

    def test_unknown_or_failing_runtime_returns_empty(self, monkeypatch):
        monkeypatch.setattr(agents, "_models_cache", {})
        def boom(*a, **k):
            raise OSError("not installed")
        monkeypatch.setattr(agents.subprocess, "run", boom)
        assert agents.list_models("opencode") == []
        assert agents.list_models("codex") == []
        assert agents.list_models("custom") == []

    def test_codex_models_come_from_cli_catalog(self, monkeypatch):
        import json
        from unittest.mock import MagicMock
        monkeypatch.setattr(agents, "_models_cache", {})
        out = json.dumps({"models": [
            {"slug": "b", "visibility": "list", "priority": 2},
            {"slug": "hidden", "visibility": "hide", "priority": 0},
            {"slug": "a", "visibility": "list", "priority": 1},
        ]})
        monkeypatch.setattr(agents.subprocess, "run", lambda *a, **k: MagicMock(returncode=0, stdout=out))
        assert agents.list_models("codex") == ["a", "b"]

    def test_unparseable_output_returns_empty(self, monkeypatch):
        from unittest.mock import MagicMock
        monkeypatch.setattr(agents, "_models_cache", {})
        monkeypatch.setattr(agents.subprocess, "run", lambda *a, **k: MagicMock(returncode=0, stdout="not json"))
        assert agents.list_models("codex") == []
