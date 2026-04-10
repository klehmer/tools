"""Tests for agent report CRUD, merge logic, action marking, and unsubscribed memory."""

import json
import pytest
from conftest import FAKE_TOKEN


# ===================================================================
# _norm_sender
# ===================================================================

class TestNormSender:
    def test_bare_email(self):
        from main import _norm_sender
        assert _norm_sender("foo@bar.com") == "foo@bar.com"

    def test_display_name_angle_brackets(self):
        from main import _norm_sender
        assert _norm_sender("John Doe <john@corp.com>") == "john@corp.com"

    def test_case_insensitive(self):
        from main import _norm_sender
        assert _norm_sender("FOO@BAR.COM") == "foo@bar.com"

    def test_empty_and_none(self):
        from main import _norm_sender
        assert _norm_sender("") == ""
        assert _norm_sender(None) == ""


# ===================================================================
# _merge_groups
# ===================================================================

class TestMergeGroups:
    def test_no_overlap(self):
        from main import _merge_groups
        a = [{"sender": "a@x.com", "suggested_action": "delete", "count": 10,
              "reason": "old", "email_ids": ["1", "2"]}]
        b = [{"sender": "b@x.com", "suggested_action": "block", "count": 5,
              "reason": "spam", "email_ids": ["3"]}]
        merged = _merge_groups(a, b)
        assert len(merged) == 2

    def test_same_sender_same_action_merges(self):
        from main import _merge_groups
        a = [{"sender": "a@x.com", "suggested_action": "delete", "count": 10,
              "reason": "old", "email_ids": ["1", "2"]}]
        b = [{"sender": "a@x.com", "suggested_action": "delete", "count": 15,
              "reason": "newer reason", "email_ids": ["2", "3"]}]
        merged = _merge_groups(a, b)
        assert len(merged) == 1
        g = merged[0]
        assert g["count"] == 15  # max
        assert set(g["email_ids"]) == {"1", "2", "3"}  # union
        assert g["reason"] == "newer reason"  # later wins

    def test_same_sender_different_action_kept_separate(self):
        from main import _merge_groups
        a = [{"sender": "a@x.com", "suggested_action": "delete", "count": 10,
              "reason": "r", "email_ids": []}]
        b = [{"sender": "a@x.com", "suggested_action": "block", "count": 5,
              "reason": "r", "email_ids": []}]
        merged = _merge_groups(a, b)
        assert len(merged) == 2

    def test_display_name_normalized(self):
        from main import _merge_groups
        a = [{"sender": "John <a@x.com>", "suggested_action": "delete",
              "count": 10, "reason": "r", "email_ids": ["1"]}]
        b = [{"sender": "a@x.com", "suggested_action": "delete",
              "count": 5, "reason": "r", "email_ids": ["2"]}]
        merged = _merge_groups(a, b)
        assert len(merged) == 1

    def test_size_takes_max(self):
        from main import _merge_groups
        a = [{"sender": "a@x.com", "suggested_action": "delete", "count": 1,
              "reason": "r", "email_ids": [], "estimated_size_mb": 10.0}]
        b = [{"sender": "a@x.com", "suggested_action": "delete", "count": 1,
              "reason": "r", "email_ids": [], "estimated_size_mb": 25.0}]
        merged = _merge_groups(a, b)
        assert merged[0]["estimated_size_mb"] == 25.0

    def test_query_and_link_later_wins(self):
        from main import _merge_groups
        a = [{"sender": "a@x.com", "suggested_action": "unsubscribe", "count": 1,
              "reason": "old", "email_ids": [], "query": "from:a@x.com",
              "unsubscribe_link": "https://old.com"}]
        b = [{"sender": "a@x.com", "suggested_action": "unsubscribe", "count": 1,
              "reason": "new", "email_ids": [], "query": "from:a@x.com newer",
              "unsubscribe_link": "https://new.com"}]
        merged = _merge_groups(a, b)
        assert merged[0]["query"] == "from:a@x.com newer"
        assert merged[0]["unsubscribe_link"] == "https://new.com"

    def test_empty_inputs(self):
        from main import _merge_groups
        assert _merge_groups([], []) == []
        assert _merge_groups(None, None) == []


# ===================================================================
# agent report API endpoints
# ===================================================================

class TestAgentReportEndpoints:
    def test_get_empty_report(self, client):
        r = client.get("/agent/report")
        assert r.status_code == 200
        assert r.json() is None

    def test_post_and_get_report(self, client):
        report = {
            "runner": "codex",
            "status": "running",
            "summary": "pass 1",
            "starting_total": 5000,
            "current_total": 4800,
            "deleted_so_far": 200,
            "groups": [
                {"sender": "promo@store.com", "count": 50,
                 "suggested_action": "delete", "reason": "old promos",
                 "query": "from:promo@store.com"}
            ],
        }
        r = client.post("/agent/report", json=report)
        assert r.status_code == 200
        data = r.json()
        assert data["runner"] == "codex"
        assert len(data["groups"]) == 1

        r = client.get("/agent/report")
        assert r.json()["summary"] == "pass 1"

    def test_merge_across_posts(self, client):
        g1 = {"sender": "a@x.com", "count": 10, "suggested_action": "delete",
               "reason": "old", "email_ids": ["1", "2"]}
        client.post("/agent/report", json={
            "runner": "codex", "status": "running", "groups": [g1]})

        g2 = {"sender": "a@x.com", "count": 20, "suggested_action": "delete",
               "reason": "newer", "email_ids": ["2", "3"]}
        r = client.post("/agent/report", json={
            "runner": "codex", "status": "running", "groups": [g2]})
        groups = r.json()["groups"]
        assert len(groups) == 1
        assert groups[0]["count"] == 20
        assert set(groups[0]["email_ids"]) == {"1", "2", "3"}

    def test_actioned_keys_preserved(self, client):
        client.post("/agent/report", json={
            "runner": "codex", "status": "running", "groups": []})
        # Mark a key
        client.post("/agent/report/action", json={
            "key": "a@x.com:delete", "deleted_count": 5})
        # Re-post report WITHOUT actioned_keys — should be preserved
        r = client.post("/agent/report", json={
            "runner": "codex", "status": "running", "groups": []})
        assert "a@x.com:delete" in r.json()["actioned_keys"]

    def test_delete_report(self, client):
        client.post("/agent/report", json={
            "runner": "codex", "status": "running", "groups": []})
        r = client.delete("/agent/report")
        assert r.status_code == 200
        assert client.get("/agent/report").json() is None


class TestActionMark:
    def test_mark_increments_deleted(self, client):
        client.post("/agent/report", json={
            "runner": "codex", "status": "running",
            "current_total": 1000, "deleted_so_far": 0, "groups": []})
        r = client.post("/agent/report/action", json={
            "key": "g1", "deleted_count": 50, "freed_mb": 10.0})
        data = r.json()
        assert data["deleted_so_far"] == 50
        assert data["current_total"] == 950
        assert "g1" in data["actioned_keys"]

    def test_mark_multiple_actions_accumulate(self, client):
        client.post("/agent/report", json={
            "runner": "codex", "status": "running",
            "current_total": 1000, "deleted_so_far": 0, "groups": []})
        client.post("/agent/report/action", json={"key": "g1", "deleted_count": 100})
        r = client.post("/agent/report/action", json={"key": "g2", "deleted_count": 200})
        data = r.json()
        assert data["deleted_so_far"] == 300
        assert data["current_total"] == 700
        assert set(data["actioned_keys"]) == {"g1", "g2"}

    def test_current_total_floors_at_zero(self, client):
        client.post("/agent/report", json={
            "runner": "codex", "status": "running",
            "current_total": 10, "deleted_so_far": 0, "groups": []})
        r = client.post("/agent/report/action", json={"key": "g1", "deleted_count": 999})
        assert r.json()["current_total"] == 0


# ===================================================================
# unsubscribed senders memory
# ===================================================================

class TestUnsubscribedMemory:
    def test_empty_initially(self, client):
        r = client.get("/agent/unsubscribed")
        assert r.status_code == 200
        assert r.json()["senders"] == []

    def test_add_and_list(self, client):
        client.post("/agent/unsubscribed", json={"sender_email": "news@x.com"})
        client.post("/agent/unsubscribed", json={"sender_email": "promo@y.com"})
        r = client.get("/agent/unsubscribed")
        senders = r.json()["senders"]
        assert "news@x.com" in senders
        assert "promo@y.com" in senders

    def test_deduplicates(self, client):
        client.post("/agent/unsubscribed", json={"sender_email": "dup@x.com"})
        client.post("/agent/unsubscribed", json={"sender_email": "dup@x.com"})
        r = client.get("/agent/unsubscribed")
        assert r.json()["senders"].count("dup@x.com") == 1
