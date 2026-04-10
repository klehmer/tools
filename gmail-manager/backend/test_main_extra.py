"""Tests for main.py endpoints not covered by other test files:
unsubscribe, download, auth callback, approval enforcement, runner script."""

import io
import zipfile
from unittest.mock import MagicMock, patch
import pytest
from conftest import FAKE_TOKEN


# ===================================================================
# Approval enforcement
# ===================================================================

class TestApprovalEnforcement:
    def test_delete_blocked_when_approval_required_no_header(self, client):
        import rules_manager
        rules_manager.save_rules({"require_approval": True})
        r = client.post("/actions/delete", json={"email_ids": ["a"]})
        assert r.status_code == 403
        assert "require_approval" in r.json()["detail"]

    def test_delete_allowed_with_x_approved(self, client, gmail_mock):
        import rules_manager
        rules_manager.save_rules({"require_approval": True})
        r = client.post("/actions/delete",
                        json={"email_ids": ["a"]},
                        headers={"X-Approved": "1"})
        assert r.status_code == 200

    def test_delete_allowed_when_approval_not_required(self, client, gmail_mock):
        import rules_manager
        rules_manager.save_rules({"require_approval": False})
        r = client.post("/actions/delete", json={"email_ids": ["a"]})
        assert r.status_code == 200


# ===================================================================
# Unsubscribe endpoint
# ===================================================================

class TestUnsubscribe:
    def test_mailto_link(self, client, gmail_mock):
        gmail_mock.send_unsubscribe_email.return_value = True
        r = client.post("/actions/unsubscribe", json={
            "email_id": "e1",
            "sender_email": "list@x.com",
            "unsubscribe_link": "mailto:unsub@list.com?subject=Unsub",
        })
        assert r.status_code == 200
        assert r.json()["method"] == "email"
        assert r.json()["success"] is True

    def test_http_link(self, client, gmail_mock):
        r = client.post("/actions/unsubscribe", json={
            "email_id": "e1",
            "sender_email": "list@x.com",
            "unsubscribe_link": "https://unsub.example.com/opt-out",
        })
        assert r.status_code == 200
        assert r.json()["method"] == "http"
        assert r.json()["url"] == "https://unsub.example.com/opt-out"

    def test_fallback_delete(self, client, gmail_mock):
        gmail_mock.search_emails.return_value = {
            "emails": [{"id": "e1"}, {"id": "e2"}],
            "total_found": 2,
        }
        gmail_mock.delete_emails.return_value = {"deleted": 2, "errors": []}
        r = client.post("/actions/unsubscribe", json={
            "email_id": "e1",
            "sender_email": "list@x.com",
        })
        assert r.status_code == 200
        assert r.json()["method"] == "delete"
        assert r.json()["deleted"] == 2

    def test_fallback_no_emails(self, client, gmail_mock):
        gmail_mock.search_emails.return_value = {"emails": [], "total_found": 0}
        r = client.post("/actions/unsubscribe", json={
            "email_id": "e1",
            "sender_email": "unknown@x.com",
        })
        assert r.json()["method"] == "delete"
        assert r.json()["deleted"] == 0


# ===================================================================
# Block with protected sender
# ===================================================================

class TestBlockProtected:
    def test_block_protected_sender_403(self, client, gmail_mock):
        import rules_manager
        rules_manager.save_rules({"protected_senders": ["boss@corp.com"]})
        r = client.post("/actions/block",
                        json={"sender_email": "boss@corp.com"},
                        headers={"X-Approved": "1"})
        assert r.status_code == 403
        assert "protected_senders" in r.json()["detail"]


# ===================================================================
# Download endpoints
# ===================================================================

class TestDownloadSingle:
    def test_download_email(self, client, gmail_mock):
        gmail_mock.download_email_as_eml.return_value = b"From: test\r\n\r\nBody"
        r = client.get("/emails/m1/download")
        assert r.status_code == 200
        assert r.headers["content-type"] == "message/rfc822"
        assert b"From: test" in r.content

    def test_list_attachments(self, client, gmail_mock):
        gmail_mock.get_attachments.return_value = [
            {"attachment_id": "a1", "filename": "doc.pdf",
             "mime_type": "application/pdf", "size_bytes": 5000}
        ]
        r = client.get("/emails/m1/attachments")
        assert r.status_code == 200
        assert len(r.json()["attachments"]) == 1

    def test_download_attachment(self, client, gmail_mock):
        gmail_mock.download_attachment.return_value = b"PDF_BYTES"
        r = client.get("/emails/m1/attachments/a1/download?filename=doc.pdf")
        assert r.status_code == 200
        assert r.content == b"PDF_BYTES"
        assert "doc.pdf" in r.headers["content-disposition"]

    def test_download_attachment_sanitizes_filename(self, client, gmail_mock):
        gmail_mock.download_attachment.return_value = b"data"
        r = client.get("/emails/m1/attachments/a1/download?filename=../../etc/passwd")
        assert ".." not in r.headers["content-disposition"]


class TestDownloadBulk:
    def test_download_bulk_zip(self, client, gmail_mock):
        # Override the download_bulk dependency directly — it builds its own GmailService
        # so we need to mock at a lower level
        import main
        import asyncio

        async def fake_download_bulk(body, session_token=FAKE_TOKEN):
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as zf:
                zf.writestr("emails/m1.eml", "From: test\r\n\r\nBody")
            buf.seek(0)
            from starlette.responses import StreamingResponse
            return StreamingResponse(buf, media_type="application/zip")

        # Patch at the route level
        with patch.object(main, "download_bulk", fake_download_bulk):
            # Re-register won't work easily, so just test the endpoint with mocked auth
            # We test the actual logic by calling it directly instead
            pass

        # Direct test of the handler logic
        from main import app
        from starlette.testclient import TestClient
        import auth

        # Mock auth.get_credentials to return a mock that GmailService can use
        mock_creds = MagicMock()
        mock_creds.expired = False
        mock_creds.refresh_token = None

        with patch.object(auth, "get_credentials", return_value=mock_creds), \
             patch("main.GmailService") as MockGmail:
            mock_svc = MagicMock()
            mock_svc.download_email_as_eml.return_value = b"From: x\r\n\r\nBody"
            mock_svc.get_attachments.return_value = []
            MockGmail.return_value = mock_svc

            r = client.post("/emails/download-bulk", json={
                "email_ids": ["m1", "m2"],
                "include_attachments": False,
            })
            assert r.status_code == 200
            assert r.headers["content-type"] == "application/zip"
            z = zipfile.ZipFile(io.BytesIO(r.content))
            assert any("m1.eml" in n for n in z.namelist())

    def test_download_bulk_custom_filename(self, client, gmail_mock):
        import auth
        mock_creds = MagicMock()
        mock_creds.expired = False
        mock_creds.refresh_token = None

        with patch.object(auth, "get_credentials", return_value=mock_creds), \
             patch("main.GmailService") as MockGmail:
            mock_svc = MagicMock()
            mock_svc.download_email_as_eml.return_value = b"raw"
            mock_svc.get_attachments.return_value = []
            MockGmail.return_value = mock_svc

            r = client.post("/emails/download-bulk", json={
                "email_ids": ["m1"],
                "include_attachments": False,
                "filename": "my-backup",
            })
            assert r.status_code == 200
            assert "my-backup.zip" in r.headers["content-disposition"]

    def test_download_bulk_failed_email_skipped(self, client, gmail_mock):
        import auth
        mock_creds = MagicMock()
        mock_creds.expired = False
        mock_creds.refresh_token = None

        with patch.object(auth, "get_credentials", return_value=mock_creds), \
             patch("main.GmailService") as MockGmail:
            mock_svc = MagicMock()
            mock_svc.download_email_as_eml.side_effect = Exception("not found")
            mock_svc.get_attachments.return_value = []
            MockGmail.return_value = mock_svc

            r = client.post("/emails/download-bulk", json={
                "email_ids": ["bad1"],
                "include_attachments": False,
            })
            assert r.status_code == 200
            z = zipfile.ZipFile(io.BytesIO(r.content))
            assert len(z.namelist()) == 0  # failed email skipped

    def test_download_bulk_with_attachments(self, client, gmail_mock):
        import auth
        mock_creds = MagicMock()
        mock_creds.expired = False
        mock_creds.refresh_token = None

        with patch.object(auth, "get_credentials", return_value=mock_creds), \
             patch("main.GmailService") as MockGmail:
            mock_svc = MagicMock()
            mock_svc.download_email_as_eml.return_value = b"raw eml"
            mock_svc.get_attachments.return_value = [
                {"attachment_id": "a1", "filename": "pic.jpg",
                 "mime_type": "image/jpeg", "size_bytes": 100}
            ]
            mock_svc.download_attachment.return_value = b"jpeg_bytes"
            MockGmail.return_value = mock_svc

            r = client.post("/emails/download-bulk", json={
                "email_ids": ["m1"],
                "include_attachments": True,
            })
            assert r.status_code == 200
            z = zipfile.ZipFile(io.BytesIO(r.content))
            names = z.namelist()
            assert any("m1.eml" in n for n in names)
            assert any("pic.jpg" in n for n in names)


# ===================================================================
# Auth callback
# ===================================================================

class TestAuthCallback:
    def test_success_redirects_with_token(self, unauthed_client):
        with patch("auth.exchange_code", return_value="session-tok-123"):
            r = unauthed_client.get("/auth/callback?code=auth_code&state=s1",
                                     follow_redirects=False)
            assert r.status_code == 307
            assert "session_token=session-tok-123" in r.headers["location"]

    def test_failure_redirects_with_error(self, unauthed_client):
        with patch("auth.exchange_code", side_effect=Exception("bad code")):
            r = unauthed_client.get("/auth/callback?code=bad",
                                     follow_redirects=False)
            assert r.status_code == 307
            assert "error=auth_failed" in r.headers["location"]


# ===================================================================
# Auth URL
# ===================================================================

class TestAuthUrl:
    def test_returns_url(self, unauthed_client):
        with patch("auth.get_auth_url", return_value="https://accounts.google.com/auth"):
            r = unauthed_client.get("/auth/url")
            assert r.status_code == 200
            assert r.json()["url"] == "https://accounts.google.com/auth"


# ===================================================================
# Runner script generation
# ===================================================================

class TestRunnerScript:
    def test_codex_runner(self, client):
        r = client.get("/agent/runner-script?runner=codex")
        assert r.status_code == 200
        body = r.text
        assert "codex exec" in body
        assert "#!/usr/bin/env bash" in body

    def test_claude_runner(self, client):
        r = client.get("/agent/runner-script?runner=claude-code")
        assert r.status_code == 200
        assert "claude -p" in r.text

    def test_invalid_runner_defaults_to_codex(self, client):
        r = client.get("/agent/runner-script?runner=invalid")
        assert r.status_code == 200
        assert "codex exec" in r.text
