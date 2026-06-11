"""Tests for app launcher API routes in main.py."""
import pytest

import app_launcher


@pytest.fixture(autouse=True)
def _temp_apps(tmp_path, monkeypatch):
    monkeypatch.setattr(app_launcher, "_FILE", tmp_path / "apps.json")
    app_launcher._processes.clear()


class TestGetApps:
    def test_empty_list(self, client):
        resp = client.get("/apps")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_apps(self, client):
        client.post("/apps", json={"name": "App 1", "start_script": "./a.sh"})
        client.post("/apps", json={"name": "App 2", "start_script": "./b.sh"})
        resp = client.get("/apps")
        assert len(resp.json()) == 2


class TestGetApp:
    def test_get_existing(self, client):
        created = client.post("/apps", json={"name": "Find", "start_script": "./s.sh"}).json()
        resp = client.get(f"/apps/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Find"

    def test_get_nonexistent(self, client):
        resp = client.get("/apps/nonexistent")
        assert resp.status_code == 404


class TestCreateApp:
    def test_create_minimal(self, client):
        resp = client.post("/apps", json={"name": "My App", "start_script": "./start.sh"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "My App"
        assert data["start_script"] == "./start.sh"
        assert data["stop_script"] == ""
        assert data["url"] == ""
        assert data["working_dir"] == ""
        assert data["running"] is False

    def test_create_with_all_fields(self, client):
        resp = client.post("/apps", json={
            "name": "Full",
            "start_script": "./start.sh",
            "stop_script": "./stop.sh",
            "url": "http://localhost:3000",
            "working_dir": "/path/to/app",
        })
        data = resp.json()
        assert data["stop_script"] == "./stop.sh"
        assert data["url"] == "http://localhost:3000"
        assert data["working_dir"] == "/path/to/app"

    def test_create_missing_name(self, client):
        resp = client.post("/apps", json={"start_script": "./start.sh"})
        assert resp.status_code == 422

    def test_create_missing_start_script(self, client):
        resp = client.post("/apps", json={"name": "App"})
        assert resp.status_code == 422


class TestUpdateApp:
    def test_update_name(self, client):
        app = client.post("/apps", json={"name": "Old", "start_script": "./s.sh"}).json()
        resp = client.put(f"/apps/{app['id']}", json={"name": "New"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "New"

    def test_update_scripts(self, client):
        app = client.post("/apps", json={"name": "App", "start_script": "./old.sh"}).json()
        resp = client.put(f"/apps/{app['id']}", json={
            "start_script": "./new.sh",
            "stop_script": "./stop.sh",
        })
        assert resp.json()["start_script"] == "./new.sh"
        assert resp.json()["stop_script"] == "./stop.sh"

    def test_update_nonexistent(self, client):
        resp = client.put("/apps/nonexistent", json={"name": "X"})
        assert resp.status_code == 404


class TestStartStopApp:
    def test_start_app(self, client, tmp_path):
        marker = tmp_path / "started"
        app = client.post("/apps", json={
            "name": "Test",
            "start_script": f"touch {marker}",
        }).json()

        resp = client.post(f"/apps/{app['id']}/start")
        assert resp.status_code == 200
        assert resp.json()["running"] is True

    def test_start_nonexistent(self, client):
        resp = client.post("/apps/nonexistent/start")
        assert resp.status_code == 404

    def test_stop_app(self, client):
        app = client.post("/apps", json={
            "name": "Test",
            "start_script": "sleep 300",
        }).json()
        client.post(f"/apps/{app['id']}/start")

        resp = client.post(f"/apps/{app['id']}/stop")
        assert resp.status_code == 200
        assert resp.json()["running"] is False

    def test_stop_nonexistent(self, client):
        resp = client.post("/apps/nonexistent/stop")
        assert resp.status_code == 404


class TestDeleteApp:
    def test_delete_existing(self, client):
        app = client.post("/apps", json={"name": "Delete", "start_script": "./s.sh"}).json()
        resp = client.delete(f"/apps/{app['id']}")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert client.get("/apps").json() == []

    def test_delete_nonexistent(self, client):
        resp = client.delete("/apps/nonexistent")
        assert resp.status_code == 404

    def test_delete_preserves_others(self, client):
        a = client.post("/apps", json={"name": "Keep", "start_script": "./a.sh"}).json()
        b = client.post("/apps", json={"name": "Delete", "start_script": "./b.sh"}).json()
        client.delete(f"/apps/{b['id']}")
        items = client.get("/apps").json()
        assert len(items) == 1
        assert items[0]["id"] == a["id"]
