"""Tests for gmail_service.py — all Google API calls are mocked."""

import base64
from unittest.mock import MagicMock, patch, call
import pytest
from gmail_service import GmailService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_service():
    """Build a GmailService with a fully mocked credentials + google API."""
    creds = MagicMock()
    creds.expired = False
    creds.refresh_token = None
    with patch("gmail_service.build") as mock_build:
        svc = GmailService(creds)
    return svc, svc.service


def _header(name, value):
    return {"name": name, "value": value}


# ===================================================================
# __init__
# ===================================================================

class TestInit:
    def test_does_not_refresh_when_not_expired(self):
        creds = MagicMock()
        creds.expired = False
        with patch("gmail_service.build"):
            GmailService(creds)
        creds.refresh.assert_not_called()

    def test_refreshes_when_expired(self):
        creds = MagicMock()
        creds.expired = True
        creds.refresh_token = "rt"
        with patch("gmail_service.build"), patch("gmail_service.Request") as mock_req:
            GmailService(creds)
        creds.refresh.assert_called_once()


# ===================================================================
# get_inbox_overview
# ===================================================================

class TestGetInboxOverview:
    def test_success(self):
        svc, api = _make_service()
        api.users().getProfile().execute.return_value = {
            "emailAddress": "me@test.com",
            "messagesTotal": 42000,
            "threadsTotal": 20000,
        }
        drive_mock = MagicMock()
        drive_mock.about().get().execute.return_value = {
            "storageQuota": {"usage": "5000000", "limit": "15000000000"}
        }
        # Method does `from googleapiclient.discovery import build as _build` (local import)
        with patch("googleapiclient.discovery.build", return_value=drive_mock):
            result = svc.get_inbox_overview()
        assert result["email_address"] == "me@test.com"
        assert result["total_messages"] == 42000
        assert result["storage_used_bytes"] == 5000000

    def test_drive_failure_returns_none_storage(self):
        svc, api = _make_service()
        api.users().getProfile().execute.return_value = {
            "emailAddress": "me@test.com",
            "messagesTotal": 100,
            "threadsTotal": 50,
        }
        with patch("googleapiclient.discovery.build", side_effect=Exception("drive broken")):
            result = svc.get_inbox_overview()
        assert result["storage_used_bytes"] is None
        assert result["storage_limit_bytes"] is None

    def test_http_error(self):
        from googleapiclient.errors import HttpError
        svc, api = _make_service()
        resp = MagicMock(status=500)
        api.users().getProfile().execute.side_effect = HttpError(resp, b"fail")
        result = svc.get_inbox_overview()
        assert "error" in result


# ===================================================================
# get_user_profile
# ===================================================================

class TestGetUserProfile:
    def test_success_via_oauth2(self):
        svc, api = _make_service()
        oauth2 = MagicMock()
        oauth2.userinfo().get().execute.return_value = {
            "email": "me@test.com",
            "name": "Me",
            "picture": "https://pic.url",
        }
        with patch("googleapiclient.discovery.build", return_value=oauth2):
            result = svc.get_user_profile()
        assert result["email"] == "me@test.com"
        assert result["name"] == "Me"

    def test_fallback_to_gmail_profile(self):
        svc, api = _make_service()
        with patch("googleapiclient.discovery.build", side_effect=Exception("oauth2 fail")):
            api.users().getProfile().execute.return_value = {
                "emailAddress": "fallback@test.com"
            }
            result = svc.get_user_profile()
        assert result["email"] == "fallback@test.com"
        assert result["name"] == ""


# ===================================================================
# get_top_senders
# ===================================================================

class TestGetTopSenders:
    def test_empty_inbox(self):
        svc, api = _make_service()
        api.users().messages().list().execute.return_value = {"messages": []}
        result = svc.get_top_senders(10)
        assert result == {"senders": [], "total_sampled": 0}

    def test_tallies_senders(self):
        svc, api = _make_service()
        api.users().messages().list().execute.return_value = {
            "messages": [{"id": "m1"}, {"id": "m2"}, {"id": "m3"}]
        }
        # Mock batch: invoke callbacks
        def fake_batch_execute(batch_mock):
            callbacks = batch_mock._callbacks
            for rid, cb in callbacks:
                headers = []
                if rid == "m1":
                    headers = [_header("From", "a@x.com"), _header("Date", "2024-01-01")]
                elif rid == "m2":
                    headers = [_header("From", "a@x.com"), _header("Date", "2024-06-01")]
                elif rid == "m3":
                    headers = [_header("From", "b@x.com"), _header("Date", "2024-03-01")]
                cb(rid, {"payload": {"headers": headers}, "sizeEstimate": 5000}, None)

        batch_mock = MagicMock()
        batch_mock._callbacks = []
        def add_side_effect(req, request_id, callback):
            batch_mock._callbacks.append((request_id, callback))
        batch_mock.add = add_side_effect
        batch_mock.execute = lambda: fake_batch_execute(batch_mock)
        api.new_batch_http_request.return_value = batch_mock

        result = svc.get_top_senders(10)
        assert result["total_sampled"] == 3
        assert result["senders"][0]["sender"] == "a@x.com"
        assert result["senders"][0]["count"] == 2
        assert len(result["senders"]) == 2


# ===================================================================
# search_emails
# ===================================================================

class TestSearchEmails:
    def test_empty_results(self):
        svc, api = _make_service()
        api.users().messages().list().execute.return_value = {"messages": []}
        result = svc.search_emails("query", 10)
        assert result == {"emails": [], "total_found": 0}

    def test_http_error(self):
        from googleapiclient.errors import HttpError
        svc, api = _make_service()
        resp = MagicMock(status=400)
        api.users().messages().list().execute.side_effect = HttpError(resp, b"bad query")
        result = svc.search_emails("bad:", 10)
        assert result["emails"] == []
        assert "error" in result

    def test_returns_emails_with_metadata(self):
        svc, api = _make_service()
        api.users().messages().list().execute.return_value = {
            "messages": [{"id": "m1"}],
            "resultSizeEstimate": 1,
        }
        batch_mock = MagicMock()
        batch_mock._callbacks = []
        def add_side_effect(req, request_id, callback):
            batch_mock._callbacks.append((request_id, callback))
        batch_mock.add = add_side_effect
        def execute():
            for rid, cb in batch_mock._callbacks:
                cb(rid, {
                    "payload": {"headers": [
                        _header("From", "sender@x.com"),
                        _header("Subject", "Hello"),
                        _header("Date", "2024-01-01"),
                        _header("List-Unsubscribe", "<https://unsub.example.com>"),
                    ]},
                    "sizeEstimate": 3000,
                }, None)
        batch_mock.execute = execute
        api.new_batch_http_request.return_value = batch_mock

        result = svc.search_emails("from:sender@x.com", 50)
        assert len(result["emails"]) == 1
        email = result["emails"][0]
        assert email["sender"] == "sender@x.com"
        assert email["has_unsubscribe"] is True
        assert email["unsubscribe_link"] == "https://unsub.example.com"


# ===================================================================
# get_messages_metadata
# ===================================================================

class TestGetMessagesMetadata:
    def test_empty_list(self):
        svc, _ = _make_service()
        assert svc.get_messages_metadata([]) == []

    def test_missing_message_returns_unavailable(self):
        svc, api = _make_service()
        batch_mock = MagicMock()
        batch_mock._callbacks = []
        def add_side_effect(req, request_id, callback):
            batch_mock._callbacks.append((request_id, callback))
        batch_mock.add = add_side_effect
        def execute():
            for rid, cb in batch_mock._callbacks:
                # Simulate exception — callback gets None response
                cb(rid, None, Exception("not found"))
        batch_mock.execute = execute
        api.new_batch_http_request.return_value = batch_mock

        result = svc.get_messages_metadata(["missing1"])
        assert result[0]["subject"] == "(unavailable)"


# ===================================================================
# get_emails_with_unsubscribe
# ===================================================================

class TestGetEmailsWithUnsubscribe:
    def test_delegates_to_search(self):
        svc, api = _make_service()
        api.users().messages().list().execute.return_value = {"messages": []}
        result = svc.get_emails_with_unsubscribe(25)
        assert result["emails"] == []


# ===================================================================
# delete_emails
# ===================================================================

class TestDeleteEmails:
    def test_empty_list(self):
        svc, _ = _make_service()
        assert svc.delete_emails([]) == {"deleted": 0}

    def test_batch_delete(self):
        svc, api = _make_service()
        api.users().messages().batchDelete().execute.return_value = None
        result = svc.delete_emails(["a", "b", "c"])
        assert result["deleted"] == 3

    def test_http_error_captured(self):
        from googleapiclient.errors import HttpError
        svc, api = _make_service()
        resp = MagicMock(status=403)
        api.users().messages().batchDelete().execute.side_effect = HttpError(resp, b"forbidden")
        result = svc.delete_emails(["a"])
        assert result["deleted"] == 0
        assert len(result["errors"]) == 1


# ===================================================================
# create_block_filter
# ===================================================================

class TestCreateBlockFilter:
    def test_success(self):
        svc, api = _make_service()
        api.users().settings().filters().create().execute.return_value = {"id": "f123"}
        result = svc.create_block_filter("spam@x.com")
        assert result["success"] is True
        assert result["filter_id"] == "f123"

    def test_http_error(self):
        from googleapiclient.errors import HttpError
        svc, api = _make_service()
        resp = MagicMock(status=400)
        api.users().settings().filters().create().execute.side_effect = HttpError(resp, b"fail")
        result = svc.create_block_filter("spam@x.com")
        assert result["success"] is False


# ===================================================================
# send_unsubscribe_email
# ===================================================================

class TestSendUnsubscribeEmail:
    def test_success(self):
        svc, api = _make_service()
        api.users().messages().send().execute.return_value = {"id": "sent1"}
        result = svc.send_unsubscribe_email("mailto:unsub@list.com?subject=Unsubscribe")
        assert result is True

    def test_failure(self):
        from googleapiclient.errors import HttpError
        svc, api = _make_service()
        resp = MagicMock(status=400)
        api.users().messages().send().execute.side_effect = HttpError(resp, b"fail")
        result = svc.send_unsubscribe_email("mailto:unsub@list.com")
        assert result is False


# ===================================================================
# download_email_as_eml
# ===================================================================

class TestDownloadEmailAsEml:
    def test_decodes_raw(self):
        svc, api = _make_service()
        raw_bytes = b"From: test@example.com\r\nSubject: Hi\r\n\r\nBody"
        encoded = base64.urlsafe_b64encode(raw_bytes).decode()
        api.users().messages().get().execute.return_value = {"raw": encoded}
        result = svc.download_email_as_eml("m1")
        assert result == raw_bytes


# ===================================================================
# get_email_subject
# ===================================================================

class TestGetEmailSubject:
    def test_returns_subject(self):
        svc, api = _make_service()
        api.users().messages().get().execute.return_value = {
            "payload": {"headers": [_header("Subject", "Important")]}
        }
        assert svc.get_email_subject("m1") == "Important"

    def test_returns_id_on_error(self):
        from googleapiclient.errors import HttpError
        svc, api = _make_service()
        resp = MagicMock(status=404)
        api.users().messages().get().execute.side_effect = HttpError(resp, b"gone")
        assert svc.get_email_subject("m1") == "m1"

    def test_returns_id_when_no_subject_header(self):
        svc, api = _make_service()
        api.users().messages().get().execute.return_value = {
            "payload": {"headers": [_header("From", "a@x.com")]}
        }
        assert svc.get_email_subject("m1") == "m1"


# ===================================================================
# get_attachments
# ===================================================================

class TestGetAttachments:
    def test_no_attachments(self):
        svc, api = _make_service()
        api.users().messages().get().execute.return_value = {
            "payload": {"headers": [], "body": {"size": 100}}
        }
        assert svc.get_attachments("m1") == []

    def test_with_attachments(self):
        svc, api = _make_service()
        api.users().messages().get().execute.return_value = {
            "payload": {
                "parts": [
                    {
                        "filename": "doc.pdf",
                        "mimeType": "application/pdf",
                        "body": {"attachmentId": "att1", "size": 50000},
                    },
                    {
                        "filename": "",
                        "body": {"size": 100},
                    },
                ]
            }
        }
        atts = svc.get_attachments("m1")
        assert len(atts) == 1
        assert atts[0]["filename"] == "doc.pdf"

    def test_nested_parts(self):
        svc, api = _make_service()
        api.users().messages().get().execute.return_value = {
            "payload": {
                "parts": [
                    {
                        "filename": "",
                        "body": {"size": 0},
                        "parts": [
                            {
                                "filename": "nested.txt",
                                "mimeType": "text/plain",
                                "body": {"attachmentId": "att2", "size": 200},
                            }
                        ],
                    }
                ]
            }
        }
        atts = svc.get_attachments("m1")
        assert len(atts) == 1
        assert atts[0]["filename"] == "nested.txt"

    def test_http_error_returns_empty(self):
        from googleapiclient.errors import HttpError
        svc, api = _make_service()
        resp = MagicMock(status=404)
        api.users().messages().get().execute.side_effect = HttpError(resp, b"gone")
        assert svc.get_attachments("m1") == []


# ===================================================================
# download_attachment
# ===================================================================

class TestDownloadAttachment:
    def test_decodes_data(self):
        svc, api = _make_service()
        raw = b"binary attachment data"
        encoded = base64.urlsafe_b64encode(raw).decode()
        api.users().messages().attachments().get().execute.return_value = {"data": encoded}
        result = svc.download_attachment("m1", "att1")
        assert result == raw


# ===================================================================
# _parse_unsubscribe_header
# ===================================================================

class TestParseUnsubscribeHeader:
    def test_empty(self):
        assert GmailService._parse_unsubscribe_header("") is None

    def test_http_link(self):
        h = "<https://unsub.example.com/opt-out>"
        assert GmailService._parse_unsubscribe_header(h) == "https://unsub.example.com/opt-out"

    def test_mailto_link(self):
        h = "<mailto:unsub@list.com?subject=Unsubscribe>"
        assert GmailService._parse_unsubscribe_header(h) == "mailto:unsub@list.com?subject=Unsubscribe"

    def test_prefers_http_over_mailto(self):
        h = "<mailto:unsub@list.com>, <https://unsub.example.com>"
        assert GmailService._parse_unsubscribe_header(h) == "https://unsub.example.com"

    def test_no_angle_brackets(self):
        assert GmailService._parse_unsubscribe_header("just text") is None
