"""Tests for the approvals module and its API endpoints."""

import time
import pytest
from conftest import FAKE_TOKEN


# ===================================================================
# approvals module unit tests
# ===================================================================

class TestApprovalsModule:
    def test_request_creates_pending(self):
        import approvals
        rec = approvals.request_approval(
            email_ids=["a", "b"],
            sender="spam@example.com",
            reason="bulk promo",
            suggested_action="delete",
        )
        assert rec["status"] == "pending"
        assert rec["email_ids"] == ["a", "b"]
        assert rec["sender"] == "spam@example.com"
        assert rec["decided_at"] is None

    def test_list_all_and_by_status(self):
        import approvals
        approvals.request_approval(["1"], "a@x.com", "r", "delete")
        approvals.request_approval(["2"], "b@x.com", "r", "block")
        all_items = approvals.list_approvals()
        assert len(all_items) == 2

        pending = approvals.list_approvals("pending")
        assert len(pending) == 2

        approved = approvals.list_approvals("approved")
        assert len(approved) == 0

    def test_decide_approve_and_deny(self):
        import approvals
        rec = approvals.request_approval(["1"], "a@x.com", "r", "delete")
        aid = rec["id"]

        result = approvals.decide(aid, "approved")
        assert result["status"] == "approved"
        assert result["decided_at"] is not None

    def test_decide_invalid_status_raises(self):
        import approvals
        rec = approvals.request_approval(["1"], "a@x.com", "r", "delete")
        with pytest.raises(ValueError, match="must be 'approved' or 'denied'"):
            approvals.decide(rec["id"], "maybe")

    def test_decide_nonexistent_returns_none(self):
        import approvals
        assert approvals.decide("nonexistent-id", "approved") is None

    def test_get_approval(self):
        import approvals
        rec = approvals.request_approval(["1"], "a@x.com", "r", "delete")
        fetched = approvals.get_approval(rec["id"])
        assert fetched["id"] == rec["id"]
        assert approvals.get_approval("nope") is None

    def test_cleanup_old(self, monkeypatch):
        import approvals
        rec = approvals.request_approval(["1"], "a@x.com", "r", "delete")
        approvals.decide(rec["id"], "denied")

        # Patch decided_at to be old
        data = approvals._load()
        data[rec["id"]]["decided_at"] = time.time() - 100_000
        approvals._save(data)

        approvals.cleanup_old(max_age_seconds=1000)
        assert approvals.get_approval(rec["id"]) is None

    def test_cleanup_keeps_pending(self, monkeypatch):
        import approvals
        rec = approvals.request_approval(["1"], "a@x.com", "r", "delete")
        approvals.cleanup_old(max_age_seconds=0)
        assert approvals.get_approval(rec["id"]) is not None


# ===================================================================
# approvals API endpoints
# ===================================================================

class TestApprovalsEndpoints:
    def test_request_and_list(self, client):
        r = client.post("/approvals/request", json={
            "email_ids": ["e1", "e2"],
            "sender": "news@foo.com",
            "reason": "newsletter spam",
            "suggested_action": "delete",
        })
        assert r.status_code == 200
        aid = r.json()["id"]

        r = client.get("/approvals?status=pending")
        assert r.status_code == 200
        ids = [a["id"] for a in r.json()["approvals"]]
        assert aid in ids

    def test_get_single(self, client):
        r = client.post("/approvals/request", json={
            "email_ids": ["e1"],
            "sender": "s@x.com",
            "reason": "r",
        })
        aid = r.json()["id"]

        r = client.get(f"/approvals/{aid}")
        assert r.status_code == 200
        assert r.json()["sender"] == "s@x.com"

    def test_get_nonexistent_404(self, client):
        r = client.get("/approvals/nonexistent")
        assert r.status_code == 404

    def test_decide_approve(self, client):
        r = client.post("/approvals/request", json={
            "email_ids": ["e1"],
            "sender": "s@x.com",
            "reason": "r",
        })
        aid = r.json()["id"]

        r = client.post(f"/approvals/{aid}/decide", json={"status": "approved"})
        assert r.status_code == 200
        assert r.json()["status"] == "approved"

    def test_decide_nonexistent_404(self, client):
        r = client.post("/approvals/nope/decide", json={"status": "denied"})
        assert r.status_code == 404
