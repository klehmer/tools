"""Tests for agent runtime control endpoints: logs, processes, kill-all, install, start."""

import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from conftest import FAKE_TOKEN


# ===================================================================
# Agent logs
# ===================================================================

class TestAgentLogs:
    def test_get_empty_log(self, client):
        r = client.get("/agent/logs")
        assert r.status_code == 200
        assert r.json()["lines"] == []

    def test_get_log_with_content(self, client, tmp_path, monkeypatch):
        import main
        log_file = main._LOG_FILE
        log_file.write_text("line1\nline2\nline3\n")
        r = client.get("/agent/logs?lines=2")
        assert r.status_code == 200
        assert r.json()["lines"] == ["line2", "line3"]

    def test_clear_log(self, client, tmp_path, monkeypatch):
        import main
        main._LOG_FILE.write_text("stuff\n")
        r = client.delete("/agent/logs")
        assert r.status_code == 200
        assert main._LOG_FILE.read_text() == ""


# ===================================================================
# Agent processes
# ===================================================================

class TestAgentProcesses:
    def test_returns_empty_when_none_running(self, client):
        r = client.get("/agent/processes")
        assert r.status_code == 200
        # May or may not be empty depending on what's running on the machine,
        # but structure is correct
        assert "processes" in r.json()

    @patch("subprocess.run")
    def test_filters_matching_processes(self, mock_run, client):
        mock_run.return_value = MagicMock(
            stdout=(
                "  PID     ELAPSED COMMAND\n"
                "12345      01:30 /bin/bash run-cleanup-codex.sh\n"
                "12346      00:45 codex exec --dangerously thing\n"
                "12347      10:00 vim something.py\n"
            )
        )
        r = client.get("/agent/processes")
        procs = r.json()["processes"]
        assert len(procs) == 2
        assert procs[0]["pid"] == "12345"
        assert "run-cleanup" in procs[0]["command"]
        assert procs[1]["pid"] == "12346"


# ===================================================================
# Kill all agents
# ===================================================================

class TestKillAllAgents:
    @patch("subprocess.run")
    def test_kill_all(self, mock_run, client):
        mock_run.return_value = MagicMock(returncode=0)
        r = client.post("/agent/kill-all")
        assert r.status_code == 200
        assert r.json()["ok"] is True
        # Should have called pkill 3 times
        assert mock_run.call_count == 3


# ===================================================================
# Install files
# ===================================================================

class TestInstallFiles:
    def test_install_writes_files(self, client, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        # Patch expanduser to use tmp
        monkeypatch.setattr(os.path, "expanduser", lambda p: str(tmp_path) if p == "~" else p)

        r = client.post("/agent/install-files", json={
            "prompt": "You are an inbox cleanup agent...",
            "runner": "codex",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True

        prompt_path = Path(data["prompt_path"])
        script_path = Path(data["script_path"])
        assert prompt_path.exists()
        assert "cleanup agent" in prompt_path.read_text()
        assert script_path.exists()
        assert os.access(str(script_path), os.X_OK)


# ===================================================================
# Start agent
# ===================================================================

class TestStartAgent:
    def test_start_missing_script_400(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(os.path, "expanduser", lambda p: str(tmp_path) if p == "~" else p)
        r = client.post("/agent/start", json={"runner": "codex"})
        assert r.status_code == 400
        assert "not found" in r.json()["detail"].lower()

    @patch("subprocess.Popen")
    def test_start_success(self, mock_popen, client, tmp_path, monkeypatch):
        monkeypatch.setattr(os.path, "expanduser", lambda p: str(tmp_path) if p == "~" else p)
        # Create the files it expects
        (tmp_path / "gmail-prompt.txt").write_text("prompt")
        script = tmp_path / "run-cleanup-codex.sh"
        script.write_text("#!/bin/bash\necho hi")
        script.chmod(0o755)

        r = client.post("/agent/start", json={"runner": "codex"})
        assert r.status_code == 200
        assert r.json()["ok"] is True
        mock_popen.assert_called_once()
