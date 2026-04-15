"""Tests for checklist API routes in main.py."""
import pytest

import checklist


@pytest.fixture(autouse=True)
def _temp_checklist(tmp_path, monkeypatch):
    """Point checklist at a temp file for each test."""
    monkeypatch.setattr(checklist, "_FILE", tmp_path / "checklist.json")


class TestGetChecklist:
    def test_empty_list(self, client):
        resp = client.get("/checklist")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_items(self, client):
        client.post("/checklist", json={"text": "Task 1", "date": "2026-04-14"})
        client.post("/checklist", json={"text": "Task 2", "date": "2026-04-14"})
        resp = client.get("/checklist")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_filter_date_from(self, client):
        client.post("/checklist", json={"text": "Old", "date": "2026-04-10"})
        client.post("/checklist", json={"text": "New", "date": "2026-04-20"})
        resp = client.get("/checklist?date_from=2026-04-15")
        assert len(resp.json()) == 1
        assert resp.json()[0]["text"] == "New"

    def test_filter_date_to(self, client):
        client.post("/checklist", json={"text": "Old", "date": "2026-04-10"})
        client.post("/checklist", json={"text": "New", "date": "2026-04-20"})
        resp = client.get("/checklist?date_to=2026-04-15")
        assert len(resp.json()) == 1
        assert resp.json()[0]["text"] == "Old"

    def test_filter_done(self, client):
        resp = client.post("/checklist", json={"text": "Task", "date": "2026-04-14"})
        item_id = resp.json()["id"]
        client.put(f"/checklist/{item_id}", json={"done": True})
        client.post("/checklist", json={"text": "Pending", "date": "2026-04-14"})

        done = client.get("/checklist?done=true")
        assert len(done.json()) == 1
        assert done.json()[0]["done"] is True

        pending = client.get("/checklist?done=false")
        assert len(pending.json()) == 1
        assert pending.json()[0]["done"] is False


class TestCreateChecklist:
    def test_create_minimal(self, client):
        resp = client.post("/checklist", json={"text": "Buy milk", "date": "2026-04-14"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["text"] == "Buy milk"
        assert data["date"] == "2026-04-14"
        assert data["done"] is False
        assert data["priority"] is False
        assert data["sort_order"] == 0

    def test_create_with_priority(self, client):
        resp = client.post("/checklist", json={"text": "Urgent", "date": "2026-04-14", "priority": True})
        assert resp.status_code == 200
        assert resp.json()["priority"] is True

    def test_create_with_sort_order(self, client):
        resp = client.post("/checklist", json={"text": "Third", "date": "2026-04-14", "sort_order": 2})
        assert resp.status_code == 200
        assert resp.json()["sort_order"] == 2

    def test_create_missing_text(self, client):
        resp = client.post("/checklist", json={"date": "2026-04-14"})
        assert resp.status_code == 422

    def test_create_missing_date(self, client):
        resp = client.post("/checklist", json={"text": "No date"})
        assert resp.status_code == 422


class TestUpdateChecklist:
    def test_update_text(self, client):
        item = client.post("/checklist", json={"text": "Old", "date": "2026-04-14"}).json()
        resp = client.put(f"/checklist/{item['id']}", json={"text": "New"})
        assert resp.status_code == 200
        assert resp.json()["text"] == "New"

    def test_update_done(self, client):
        item = client.post("/checklist", json={"text": "Task", "date": "2026-04-14"}).json()
        resp = client.put(f"/checklist/{item['id']}", json={"done": True})
        assert resp.status_code == 200
        assert resp.json()["done"] is True

    def test_update_priority(self, client):
        item = client.post("/checklist", json={"text": "Task", "date": "2026-04-14"}).json()
        resp = client.put(f"/checklist/{item['id']}", json={"priority": True})
        assert resp.status_code == 200
        assert resp.json()["priority"] is True

    def test_update_date(self, client):
        item = client.post("/checklist", json={"text": "Task", "date": "2026-04-14"}).json()
        resp = client.put(f"/checklist/{item['id']}", json={"date": "2026-04-20"})
        assert resp.status_code == 200
        assert resp.json()["date"] == "2026-04-20"

    def test_update_sort_order(self, client):
        item = client.post("/checklist", json={"text": "Task", "date": "2026-04-14"}).json()
        resp = client.put(f"/checklist/{item['id']}", json={"sort_order": 5})
        assert resp.status_code == 200
        assert resp.json()["sort_order"] == 5

    def test_update_nonexistent(self, client):
        resp = client.put("/checklist/nonexistent", json={"text": "X"})
        assert resp.status_code == 404


class TestReorderChecklist:
    def test_reorder(self, client):
        a = client.post("/checklist", json={"text": "A", "date": "2026-04-14", "sort_order": 0}).json()
        b = client.post("/checklist", json={"text": "B", "date": "2026-04-14", "sort_order": 1}).json()
        c = client.post("/checklist", json={"text": "C", "date": "2026-04-14", "sort_order": 2}).json()

        resp = client.post("/checklist/reorder", json={"item_ids": [c["id"], a["id"], b["id"]]})
        assert resp.status_code == 200

        items = client.get("/checklist").json()
        assert items[0]["id"] == c["id"]
        assert items[1]["id"] == a["id"]
        assert items[2]["id"] == b["id"]


class TestDeleteChecklist:
    def test_delete_existing(self, client):
        item = client.post("/checklist", json={"text": "Delete me", "date": "2026-04-14"}).json()
        resp = client.delete(f"/checklist/{item['id']}")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert client.get("/checklist").json() == []

    def test_delete_nonexistent(self, client):
        resp = client.delete("/checklist/nonexistent")
        assert resp.status_code == 404

    def test_delete_preserves_others(self, client):
        a = client.post("/checklist", json={"text": "Keep", "date": "2026-04-14"}).json()
        b = client.post("/checklist", json={"text": "Delete", "date": "2026-04-14"}).json()
        client.delete(f"/checklist/{b['id']}")
        items = client.get("/checklist").json()
        assert len(items) == 1
        assert items[0]["id"] == a["id"]
