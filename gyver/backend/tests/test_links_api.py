"""Tests for links API routes in main.py."""
import pytest

import links


@pytest.fixture(autouse=True)
def _temp_links(tmp_path, monkeypatch):
    monkeypatch.setattr(links, "_FILE", tmp_path / "links.json")


class TestGetLinks:
    def test_empty_list(self, client):
        resp = client.get("/links")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_links(self, client):
        client.post("/links", json={"url": "https://a.com"})
        client.post("/links", json={"url": "https://b.com"})
        resp = client.get("/links")
        assert len(resp.json()) == 2


class TestCreateLink:
    def test_create_minimal(self, client):
        resp = client.post("/links", json={"url": "https://example.com"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["url"] == "https://example.com"
        assert data["title"] == ""
        assert "created_at" in data

    def test_create_with_title(self, client):
        resp = client.post("/links", json={"url": "https://example.com", "title": "Example"})
        assert resp.json()["title"] == "Example"

    def test_create_missing_url(self, client):
        resp = client.post("/links", json={"title": "No URL"})
        assert resp.status_code == 422


class TestUpdateLink:
    def test_update_url(self, client):
        link = client.post("/links", json={"url": "https://old.com"}).json()
        resp = client.put(f"/links/{link['id']}", json={"url": "https://new.com"})
        assert resp.status_code == 200
        assert resp.json()["url"] == "https://new.com"

    def test_update_title(self, client):
        link = client.post("/links", json={"url": "https://example.com", "title": "Old"}).json()
        resp = client.put(f"/links/{link['id']}", json={"title": "New"})
        assert resp.json()["title"] == "New"

    def test_update_nonexistent(self, client):
        resp = client.put("/links/nonexistent", json={"url": "https://x.com"})
        assert resp.status_code == 404


class TestDeleteLink:
    def test_delete_existing(self, client):
        link = client.post("/links", json={"url": "https://example.com"}).json()
        resp = client.delete(f"/links/{link['id']}")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert client.get("/links").json() == []

    def test_delete_nonexistent(self, client):
        resp = client.delete("/links/nonexistent")
        assert resp.status_code == 404

    def test_delete_preserves_others(self, client):
        a = client.post("/links", json={"url": "https://keep.com"}).json()
        b = client.post("/links", json={"url": "https://delete.com"}).json()
        client.delete(f"/links/{b['id']}")
        items = client.get("/links").json()
        assert len(items) == 1
        assert items[0]["id"] == a["id"]
