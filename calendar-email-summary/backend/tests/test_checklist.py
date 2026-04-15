"""Tests for checklist module."""
import json

import pytest

import checklist


@pytest.fixture(autouse=True)
def _temp_storage(tmp_path, monkeypatch):
    """Point checklist at a temporary JSON file."""
    file = tmp_path / "checklist.json"
    monkeypatch.setattr(checklist, "_FILE", file)
    yield file


class TestReadWrite:
    def test_read_empty_when_no_file(self):
        assert checklist._read() == []

    def test_write_and_read_roundtrip(self, _temp_storage):
        items = [{"id": "a", "text": "hello"}]
        checklist._write(items)
        assert checklist._read() == items


class TestCreateItem:
    def test_creates_item_with_defaults(self):
        item = checklist.create_item("Buy milk", "2026-04-14")
        assert item["text"] == "Buy milk"
        assert item["date"] == "2026-04-14"
        assert item["done"] is False
        assert item["priority"] is False
        assert item["sort_order"] == 0
        assert "id" in item
        assert "created_at" in item

    def test_creates_item_with_priority(self):
        item = checklist.create_item("Urgent task", "2026-04-14", priority=True)
        assert item["priority"] is True

    def test_creates_item_with_sort_order(self):
        item = checklist.create_item("Third", "2026-04-14", sort_order=2)
        assert item["sort_order"] == 2

    def test_multiple_creates_persist(self):
        checklist.create_item("First", "2026-04-14")
        checklist.create_item("Second", "2026-04-14")
        items = checklist._read()
        assert len(items) == 2

    def test_ids_are_unique(self):
        a = checklist.create_item("A", "2026-04-14")
        b = checklist.create_item("B", "2026-04-14")
        assert a["id"] != b["id"]


class TestListItems:
    def test_returns_all_items_sorted(self):
        checklist.create_item("B", "2026-04-15", sort_order=1)
        checklist.create_item("A", "2026-04-14", sort_order=0)
        checklist.create_item("C", "2026-04-15", sort_order=0)
        items = checklist.list_items()
        assert [i["text"] for i in items] == ["A", "C", "B"]

    def test_filter_by_date_from(self):
        checklist.create_item("Old", "2026-04-10")
        checklist.create_item("New", "2026-04-15")
        items = checklist.list_items(date_from="2026-04-14")
        assert len(items) == 1
        assert items[0]["text"] == "New"

    def test_filter_by_date_to(self):
        checklist.create_item("Old", "2026-04-10")
        checklist.create_item("New", "2026-04-15")
        items = checklist.list_items(date_to="2026-04-12")
        assert len(items) == 1
        assert items[0]["text"] == "Old"

    def test_filter_by_date_range(self):
        checklist.create_item("Before", "2026-04-09")
        checklist.create_item("In range", "2026-04-12")
        checklist.create_item("After", "2026-04-20")
        items = checklist.list_items(date_from="2026-04-10", date_to="2026-04-15")
        assert len(items) == 1
        assert items[0]["text"] == "In range"

    def test_filter_by_done_true(self):
        a = checklist.create_item("Done task", "2026-04-14")
        checklist.update_item(a["id"], {"done": True})
        checklist.create_item("Pending", "2026-04-14")
        items = checklist.list_items(done=True)
        assert len(items) == 1
        assert items[0]["text"] == "Done task"

    def test_filter_by_done_false(self):
        a = checklist.create_item("Done task", "2026-04-14")
        checklist.update_item(a["id"], {"done": True})
        checklist.create_item("Pending", "2026-04-14")
        items = checklist.list_items(done=False)
        assert len(items) == 1
        assert items[0]["text"] == "Pending"

    def test_empty_list(self):
        assert checklist.list_items() == []


class TestUpdateItem:
    def test_update_text(self):
        item = checklist.create_item("Old text", "2026-04-14")
        result = checklist.update_item(item["id"], {"text": "New text"})
        assert result["text"] == "New text"
        assert checklist._read()[0]["text"] == "New text"

    def test_update_date(self):
        item = checklist.create_item("Task", "2026-04-14")
        result = checklist.update_item(item["id"], {"date": "2026-04-20"})
        assert result["date"] == "2026-04-20"

    def test_update_done(self):
        item = checklist.create_item("Task", "2026-04-14")
        result = checklist.update_item(item["id"], {"done": True})
        assert result["done"] is True

    def test_update_priority(self):
        item = checklist.create_item("Task", "2026-04-14")
        result = checklist.update_item(item["id"], {"priority": True})
        assert result["priority"] is True

    def test_update_sort_order(self):
        item = checklist.create_item("Task", "2026-04-14")
        result = checklist.update_item(item["id"], {"sort_order": 5})
        assert result["sort_order"] == 5

    def test_update_multiple_fields(self):
        item = checklist.create_item("Task", "2026-04-14")
        result = checklist.update_item(item["id"], {"text": "Updated", "done": True, "priority": True})
        assert result["text"] == "Updated"
        assert result["done"] is True
        assert result["priority"] is True

    def test_update_ignores_none_values(self):
        item = checklist.create_item("Original", "2026-04-14")
        result = checklist.update_item(item["id"], {"text": None, "done": True})
        assert result["text"] == "Original"
        assert result["done"] is True

    def test_update_nonexistent_returns_none(self):
        assert checklist.update_item("nonexistent", {"text": "X"}) is None

    def test_update_ignores_unknown_fields(self):
        item = checklist.create_item("Task", "2026-04-14")
        result = checklist.update_item(item["id"], {"unknown_field": "value", "text": "Updated"})
        assert result["text"] == "Updated"
        assert "unknown_field" not in result


class TestDeleteItem:
    def test_delete_existing(self):
        item = checklist.create_item("To delete", "2026-04-14")
        assert checklist.delete_item(item["id"]) is True
        assert checklist._read() == []

    def test_delete_nonexistent(self):
        assert checklist.delete_item("nonexistent") is False

    def test_delete_preserves_other_items(self):
        a = checklist.create_item("Keep", "2026-04-14")
        b = checklist.create_item("Delete", "2026-04-14")
        checklist.delete_item(b["id"])
        items = checklist._read()
        assert len(items) == 1
        assert items[0]["id"] == a["id"]


class TestReorderItems:
    def test_reorder_updates_sort_order(self):
        a = checklist.create_item("A", "2026-04-14", sort_order=0)
        b = checklist.create_item("B", "2026-04-14", sort_order=1)
        c = checklist.create_item("C", "2026-04-14", sort_order=2)
        # Reverse order
        checklist.reorder_items([c["id"], b["id"], a["id"]])
        items = checklist.list_items()
        assert items[0]["id"] == c["id"]
        assert items[0]["sort_order"] == 0
        assert items[1]["id"] == b["id"]
        assert items[1]["sort_order"] == 1
        assert items[2]["id"] == a["id"]
        assert items[2]["sort_order"] == 2

    def test_reorder_partial_list(self):
        a = checklist.create_item("A", "2026-04-14", sort_order=0)
        b = checklist.create_item("B", "2026-04-14", sort_order=1)
        c = checklist.create_item("C", "2026-04-15", sort_order=0)
        # Only reorder B, A — C is on another day
        result = checklist.reorder_items([b["id"], a["id"]])
        assert len(result) == 2
        # C should be untouched
        all_items = checklist._read()
        c_item = [i for i in all_items if i["id"] == c["id"]][0]
        assert c_item["sort_order"] == 0
