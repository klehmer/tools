"""Tests for notes module."""
import pytest

import notes


@pytest.fixture(autouse=True)
def _temp_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(notes, "_FILE", tmp_path / "notes.json")


class TestCreateNote:
    def test_creates_with_defaults(self):
        note = notes.create_note("My Note")
        assert note["title"] == "My Note"
        assert note["content"] == ""
        assert note["archived"] is False
        assert "id" in note
        assert "created_at" in note
        assert "updated_at" in note

    def test_creates_with_content(self):
        note = notes.create_note("Title", "Some content")
        assert note["content"] == "Some content"

    def test_ids_are_unique(self):
        a = notes.create_note("A")
        b = notes.create_note("B")
        assert a["id"] != b["id"]

    def test_multiple_creates_persist(self):
        notes.create_note("First")
        notes.create_note("Second")
        assert len(notes._read()) == 2


class TestListNotes:
    def test_returns_all_sorted_by_updated(self):
        a = notes.create_note("A")
        b = notes.create_note("B")
        items = notes.list_notes()
        # Most recently created first
        assert items[0]["id"] == b["id"]
        assert items[1]["id"] == a["id"]

    def test_filter_archived_false(self):
        a = notes.create_note("Active")
        b = notes.create_note("Archived")
        notes.update_note(b["id"], {"archived": True})
        items = notes.list_notes(archived=False)
        assert len(items) == 1
        assert items[0]["title"] == "Active"

    def test_filter_archived_true(self):
        a = notes.create_note("Active")
        b = notes.create_note("Archived")
        notes.update_note(b["id"], {"archived": True})
        items = notes.list_notes(archived=True)
        assert len(items) == 1
        assert items[0]["title"] == "Archived"

    def test_empty_list(self):
        assert notes.list_notes() == []


class TestGetNote:
    def test_get_existing(self):
        note = notes.create_note("Find me")
        found = notes.get_note(note["id"])
        assert found is not None
        assert found["title"] == "Find me"

    def test_get_nonexistent(self):
        assert notes.get_note("nonexistent") is None


class TestUpdateNote:
    def test_update_title(self):
        note = notes.create_note("Old")
        result = notes.update_note(note["id"], {"title": "New"})
        assert result["title"] == "New"

    def test_update_content(self):
        note = notes.create_note("Title")
        result = notes.update_note(note["id"], {"content": "New content"})
        assert result["content"] == "New content"

    def test_update_archived(self):
        note = notes.create_note("Title")
        result = notes.update_note(note["id"], {"archived": True})
        assert result["archived"] is True

    def test_update_changes_updated_at(self):
        note = notes.create_note("Title")
        original_ts = note["updated_at"]
        result = notes.update_note(note["id"], {"title": "Changed"})
        assert result["updated_at"] >= original_ts

    def test_update_preserves_created_at(self):
        note = notes.create_note("Title")
        original = note["created_at"]
        result = notes.update_note(note["id"], {"title": "Changed"})
        assert result["created_at"] == original

    def test_update_ignores_none_values(self):
        note = notes.create_note("Original", "Content")
        result = notes.update_note(note["id"], {"title": None, "content": "Updated"})
        assert result["title"] == "Original"
        assert result["content"] == "Updated"

    def test_update_nonexistent_returns_none(self):
        assert notes.update_note("nonexistent", {"title": "X"}) is None

    def test_update_multiple_fields(self):
        note = notes.create_note("Old Title", "Old Content")
        result = notes.update_note(note["id"], {"title": "New Title", "content": "New Content", "archived": True})
        assert result["title"] == "New Title"
        assert result["content"] == "New Content"
        assert result["archived"] is True


class TestDeleteNote:
    def test_delete_existing(self):
        note = notes.create_note("Delete me")
        assert notes.delete_note(note["id"]) is True
        assert notes._read() == []

    def test_delete_nonexistent(self):
        assert notes.delete_note("nonexistent") is False

    def test_delete_preserves_other_notes(self):
        a = notes.create_note("Keep")
        b = notes.create_note("Delete")
        notes.delete_note(b["id"])
        items = notes._read()
        assert len(items) == 1
        assert items[0]["id"] == a["id"]


class TestArchiveWorkflow:
    def test_archive_and_unarchive(self):
        note = notes.create_note("My Note", "Content")
        # Archive
        notes.update_note(note["id"], {"archived": True})
        assert len(notes.list_notes(archived=False)) == 0
        assert len(notes.list_notes(archived=True)) == 1
        # Unarchive
        notes.update_note(note["id"], {"archived": False})
        assert len(notes.list_notes(archived=False)) == 1
        assert len(notes.list_notes(archived=True)) == 0

    def test_archived_note_preserves_content(self):
        note = notes.create_note("Title", "Important content")
        notes.update_note(note["id"], {"archived": True})
        archived = notes.list_notes(archived=True)
        assert archived[0]["content"] == "Important content"
