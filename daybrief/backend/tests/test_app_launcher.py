"""Tests for app_launcher module."""
import pytest

import app_launcher


@pytest.fixture(autouse=True)
def _temp_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(app_launcher, "_FILE", tmp_path / "apps.json")
    # Clear any tracked processes between tests
    app_launcher._processes.clear()


class TestCreateApp:
    def test_creates_with_defaults(self):
        app = app_launcher.create_app("My App", "/path/to/start.sh")
        assert app["name"] == "My App"
        assert app["start_script"] == "/path/to/start.sh"
        assert app["stop_script"] == ""
        assert app["url"] == ""
        assert app["working_dir"] == ""
        assert app["running"] is False
        assert "id" in app
        assert "created_at" in app

    def test_creates_with_all_fields(self):
        app = app_launcher.create_app(
            "Full App", "./start.sh",
            url="http://localhost:3000",
            stop_script="./stop.sh",
            working_dir="/home/user/app",
        )
        assert app["url"] == "http://localhost:3000"
        assert app["stop_script"] == "./stop.sh"
        assert app["working_dir"] == "/home/user/app"

    def test_ids_are_unique(self):
        a = app_launcher.create_app("A", "./a.sh")
        b = app_launcher.create_app("B", "./b.sh")
        assert a["id"] != b["id"]

    def test_multiple_creates_persist(self):
        app_launcher.create_app("A", "./a.sh")
        app_launcher.create_app("B", "./b.sh")
        assert len(app_launcher._read()) == 2


class TestListApps:
    def test_returns_all_sorted_by_created(self):
        a = app_launcher.create_app("A", "./a.sh")
        b = app_launcher.create_app("B", "./b.sh")
        items = app_launcher.list_apps()
        assert items[0]["id"] == a["id"]
        assert items[1]["id"] == b["id"]

    def test_empty_list(self):
        assert app_launcher.list_apps() == []

    def test_includes_running_status(self):
        app = app_launcher.create_app("App", "./start.sh")
        items = app_launcher.list_apps()
        assert items[0]["running"] is False


class TestGetApp:
    def test_get_existing(self):
        app = app_launcher.create_app("Find me", "./start.sh")
        found = app_launcher.get_app(app["id"])
        assert found is not None
        assert found["name"] == "Find me"
        assert "running" in found

    def test_get_nonexistent(self):
        assert app_launcher.get_app("nonexistent") is None


class TestUpdateApp:
    def test_update_name(self):
        app = app_launcher.create_app("Old", "./start.sh")
        result = app_launcher.update_app(app["id"], {"name": "New"})
        assert result["name"] == "New"

    def test_update_scripts(self):
        app = app_launcher.create_app("App", "./old.sh")
        result = app_launcher.update_app(app["id"], {
            "start_script": "./new.sh",
            "stop_script": "./stop.sh",
        })
        assert result["start_script"] == "./new.sh"
        assert result["stop_script"] == "./stop.sh"

    def test_update_url_and_working_dir(self):
        app = app_launcher.create_app("App", "./start.sh")
        result = app_launcher.update_app(app["id"], {
            "url": "http://localhost:5000",
            "working_dir": "/new/dir",
        })
        assert result["url"] == "http://localhost:5000"
        assert result["working_dir"] == "/new/dir"

    def test_update_ignores_none_values(self):
        app = app_launcher.create_app("Original", "./start.sh")
        result = app_launcher.update_app(app["id"], {"name": None, "url": "http://x.com"})
        assert result["name"] == "Original"
        assert result["url"] == "http://x.com"

    def test_update_nonexistent_returns_none(self):
        assert app_launcher.update_app("nonexistent", {"name": "X"}) is None


class TestDeleteApp:
    def test_delete_existing(self):
        app = app_launcher.create_app("Delete me", "./start.sh")
        assert app_launcher.delete_app(app["id"]) is True
        assert app_launcher._read() == []

    def test_delete_nonexistent(self):
        assert app_launcher.delete_app("nonexistent") is False

    def test_delete_preserves_other_apps(self):
        a = app_launcher.create_app("Keep", "./a.sh")
        b = app_launcher.create_app("Delete", "./b.sh")
        app_launcher.delete_app(b["id"])
        items = app_launcher._read()
        assert len(items) == 1
        assert items[0]["id"] == a["id"]


class TestStartStopApp:
    def test_start_runs_script(self, tmp_path):
        # Create a simple script that creates a marker file
        marker = tmp_path / "started"
        script = f"touch {marker}"
        app = app_launcher.create_app("Test", script)

        result = app_launcher.start_app(app["id"])
        assert result is not None
        assert result["running"] is True

        # Wait for process to finish
        proc = app_launcher._processes.get(app["id"])
        if proc:
            proc.wait(timeout=5)

        assert marker.exists()

    def test_start_nonexistent_returns_none(self):
        assert app_launcher.start_app("nonexistent") is None

    def test_start_no_script_returns_none(self):
        app = app_launcher.create_app("No Script", "")
        assert app_launcher.start_app(app["id"]) is None

    def test_stop_kills_process(self, tmp_path):
        # Start a long-running process
        app = app_launcher.create_app("Long", "sleep 300")
        app_launcher.start_app(app["id"])
        assert app_launcher._is_running(app["id"]) is True

        result = app_launcher.stop_app(app["id"])
        assert result is not None
        assert result["running"] is False
        assert not app_launcher._is_running(app["id"])

    def test_stop_nonexistent_returns_none(self):
        assert app_launcher.stop_app("nonexistent") is None

    def test_start_already_running_is_noop(self):
        app = app_launcher.create_app("App", "sleep 300")
        app_launcher.start_app(app["id"])
        # Start again — should return the app without starting a new process
        result = app_launcher.start_app(app["id"])
        assert result["running"] is True
        # Cleanup
        app_launcher.stop_app(app["id"])

    def test_stop_with_custom_stop_script(self, tmp_path):
        marker = tmp_path / "stopped"
        app = app_launcher.create_app(
            "App", "sleep 300",
            stop_script=f"touch {marker}",
        )
        app_launcher.start_app(app["id"])
        app_launcher.stop_app(app["id"])
        assert marker.exists()

    def test_is_running_false_when_not_started(self):
        app = app_launcher.create_app("App", "./start.sh")
        assert app_launcher._is_running(app["id"]) is False

    def test_delete_stops_running_app(self):
        app = app_launcher.create_app("App", "sleep 300")
        app_launcher.start_app(app["id"])
        assert app_launcher._is_running(app["id"]) is True
        app_launcher.delete_app(app["id"])
        assert app["id"] not in app_launcher._processes

    def test_start_with_working_dir(self, tmp_path):
        marker = tmp_path / "cwd_test"
        # pwd writes the cwd to the marker file
        app = app_launcher.create_app(
            "CWD Test", f"pwd > {marker}",
            working_dir=str(tmp_path),
        )
        result = app_launcher.start_app(app["id"])
        proc = app_launcher._processes.get(app["id"])
        if proc:
            proc.wait(timeout=5)
        assert marker.exists()
        assert tmp_path.name in marker.read_text()
