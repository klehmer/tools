"""Tests for notes API routes in main.py."""
import pytest

import notes


@pytest.fixture(autouse=True)
def _temp_notes(tmp_path, monkeypatch):
    monkeypatch.setattr(notes, "_FILE", tmp_path / "notes.json")


class TestGetNotes:
    def test_empty_list(self, client):
        resp = client.get("/notes")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_notes(self, client):
        client.post("/notes", json={"title": "Note 1"})
        client.post("/notes", json={"title": "Note 2"})
        resp = client.get("/notes")
        assert len(resp.json()) == 2

    def test_filter_archived(self, client):
        resp = client.post("/notes", json={"title": "Active"})
        note_id = resp.json()["id"]
        client.post("/notes", json={"title": "To Archive"})
        archive_resp = client.post("/notes", json={"title": "Archived"})
        client.put(f"/notes/{archive_resp.json()['id']}", json={"archived": True})

        active = client.get("/notes?archived=false")
        assert len(active.json()) == 2

        archived = client.get("/notes?archived=true")
        assert len(archived.json()) == 1
        assert archived.json()[0]["title"] == "Archived"


class TestGetNote:
    def test_get_existing(self, client):
        created = client.post("/notes", json={"title": "Find me"}).json()
        resp = client.get(f"/notes/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Find me"

    def test_get_nonexistent(self, client):
        resp = client.get("/notes/nonexistent")
        assert resp.status_code == 404


class TestCreateNote:
    def test_create_minimal(self, client):
        resp = client.post("/notes", json={"title": "My Note"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "My Note"
        assert data["content"] == ""
        assert data["archived"] is False
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_with_content(self, client):
        resp = client.post("/notes", json={"title": "Note", "content": "Body text"})
        assert resp.json()["content"] == "Body text"

    def test_create_missing_title(self, client):
        resp = client.post("/notes", json={"content": "No title"})
        assert resp.status_code == 422


class TestUpdateNote:
    def test_update_title(self, client):
        note = client.post("/notes", json={"title": "Old"}).json()
        resp = client.put(f"/notes/{note['id']}", json={"title": "New"})
        assert resp.status_code == 200
        assert resp.json()["title"] == "New"

    def test_update_content(self, client):
        note = client.post("/notes", json={"title": "Note"}).json()
        resp = client.put(f"/notes/{note['id']}", json={"content": "Updated"})
        assert resp.json()["content"] == "Updated"

    def test_update_archived(self, client):
        note = client.post("/notes", json={"title": "Note"}).json()
        resp = client.put(f"/notes/{note['id']}", json={"archived": True})
        assert resp.json()["archived"] is True

    def test_update_updates_timestamp(self, client):
        note = client.post("/notes", json={"title": "Note"}).json()
        resp = client.put(f"/notes/{note['id']}", json={"title": "Changed"})
        assert resp.json()["updated_at"] >= note["updated_at"]

    def test_update_nonexistent(self, client):
        resp = client.put("/notes/nonexistent", json={"title": "X"})
        assert resp.status_code == 404


class TestDeleteNote:
    def test_delete_existing(self, client):
        note = client.post("/notes", json={"title": "Delete me"}).json()
        resp = client.delete(f"/notes/{note['id']}")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert client.get("/notes").json() == []

    def test_delete_nonexistent(self, client):
        resp = client.delete("/notes/nonexistent")
        assert resp.status_code == 404

    def test_delete_preserves_others(self, client):
        a = client.post("/notes", json={"title": "Keep"}).json()
        b = client.post("/notes", json={"title": "Delete"}).json()
        client.delete(f"/notes/{b['id']}")
        items = client.get("/notes").json()
        assert len(items) == 1
        assert items[0]["id"] == a["id"]


class TestArchiveWorkflow:
    def test_archive_and_unarchive_via_api(self, client):
        note = client.post("/notes", json={"title": "Note", "content": "Body"}).json()

        # Archive
        client.put(f"/notes/{note['id']}", json={"archived": True})
        assert len(client.get("/notes?archived=false").json()) == 0
        assert len(client.get("/notes?archived=true").json()) == 1

        # Unarchive
        client.put(f"/notes/{note['id']}", json={"archived": False})
        assert len(client.get("/notes?archived=false").json()) == 1
        assert len(client.get("/notes?archived=true").json()) == 0
