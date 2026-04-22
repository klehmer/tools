"""Tests for links module."""
import pytest

import links


@pytest.fixture(autouse=True)
def _temp_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(links, "_FILE", tmp_path / "links.json")


class TestCreateLink:
    def test_creates_with_defaults(self):
        link = links.create_link("https://example.com")
        assert link["url"] == "https://example.com"
        assert link["title"] == ""
        assert "id" in link
        assert "created_at" in link

    def test_creates_with_title(self):
        link = links.create_link("https://example.com", "Example")
        assert link["title"] == "Example"

    def test_ids_are_unique(self):
        a = links.create_link("https://a.com")
        b = links.create_link("https://b.com")
        assert a["id"] != b["id"]

    def test_multiple_creates_persist(self):
        links.create_link("https://a.com")
        links.create_link("https://b.com")
        assert len(links._read()) == 2


class TestListLinks:
    def test_returns_all_sorted_by_created(self):
        a = links.create_link("https://a.com", "A")
        b = links.create_link("https://b.com", "B")
        items = links.list_links()
        # Most recently created first
        assert items[0]["id"] == b["id"]
        assert items[1]["id"] == a["id"]

    def test_empty_list(self):
        assert links.list_links() == []


class TestUpdateLink:
    def test_update_url(self):
        link = links.create_link("https://old.com")
        result = links.update_link(link["id"], {"url": "https://new.com"})
        assert result["url"] == "https://new.com"

    def test_update_title(self):
        link = links.create_link("https://example.com", "Old")
        result = links.update_link(link["id"], {"title": "New"})
        assert result["title"] == "New"

    def test_update_both_fields(self):
        link = links.create_link("https://old.com", "Old")
        result = links.update_link(link["id"], {"url": "https://new.com", "title": "New"})
        assert result["url"] == "https://new.com"
        assert result["title"] == "New"

    def test_update_ignores_none_values(self):
        link = links.create_link("https://example.com", "Title")
        result = links.update_link(link["id"], {"url": None, "title": "Updated"})
        assert result["url"] == "https://example.com"
        assert result["title"] == "Updated"

    def test_update_nonexistent_returns_none(self):
        assert links.update_link("nonexistent", {"url": "https://x.com"}) is None


class TestDeleteLink:
    def test_delete_existing(self):
        link = links.create_link("https://example.com")
        assert links.delete_link(link["id"]) is True
        assert links._read() == []

    def test_delete_nonexistent(self):
        assert links.delete_link("nonexistent") is False

    def test_delete_preserves_other_links(self):
        a = links.create_link("https://keep.com")
        b = links.create_link("https://delete.com")
        links.delete_link(b["id"])
        items = links._read()
        assert len(items) == 1
        assert items[0]["id"] == a["id"]
