"""Tests for the Claude-connector fallback service."""
import json
from unittest.mock import MagicMock, patch

import pytest

import claude_mcp_service as cms

TOOL = cms._GMAIL_SEARCH


def _stream(result_content, is_error=False):
    lines = [
        {"type": "system", "subtype": "init"},
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "tu1", "name": TOOL, "input": {}}]}},
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "tu1", "content": result_content, "is_error": is_error}]}},
        {"type": "result", "subtype": "success"},
    ]
    return "\n".join(json.dumps(l) for l in lines)


def _run(stdout):
    return MagicMock(stdout=stdout, stderr="", returncode=0)


@pytest.fixture(autouse=True)
def _cli(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_BIN", "/fake/claude")
    monkeypatch.setattr(cms, "_WORK_DIR", tmp_path / "work")
    monkeypatch.setattr(cms, "_profile_cache", None)


class TestCallTool:
    def test_parses_inline_text_blocks(self):
        out = _stream([{"type": "text", "text": '{"threads": []}'}])
        with patch("claude_mcp_service.subprocess.run", return_value=_run(out)) as run:
            assert cms._call_tool(TOOL, {"query": "x"}) == {"threads": []}
        # API key must not leak into the CLI, or the claude.ai connectors vanish
        assert "ANTHROPIC_API_KEY" not in run.call_args.kwargs["env"]

    def test_reads_result_spilled_to_file(self, tmp_path):
        saved = tmp_path / "big.txt"
        saved.write_text('{"events": [{"id": "e1"}]}')
        out = _stream(f"Error: result exceeds maximum allowed tokens. Output has been saved to {saved}.\nFormat: JSON")
        with patch("claude_mcp_service.subprocess.run", return_value=_run(out)):
            assert cms._call_tool(TOOL, {}) == {"events": [{"id": "e1"}]}

    def test_raises_on_tool_error(self):
        out = _stream("Error: not authorized", is_error=True)
        with patch("claude_mcp_service.subprocess.run", return_value=_run(out)):
            with pytest.raises(cms.ClaudeMcpError):
                cms._call_tool(TOOL, {})

    def test_raises_when_tool_never_called(self):
        with patch("claude_mcp_service.subprocess.run", return_value=_run('{"type": "result"}')):
            with pytest.raises(cms.ClaudeMcpError):
                cms._call_tool(TOOL, {})


class TestService:
    def test_fetch_emails_maps_and_paginates(self):
        def thread(n):
            return {"id": f"t{n}", "messages": [{
                "id": f"m{n}", "sender": "a@x.com", "toRecipients": ["me@x.com"],
                "addressDisplayNames": [{"emailAddress": "a@x.com", "displayName": "Ann"}],
                "subject": f"s{n}", "date": "2026-11-18T00:00:00Z", "snippet": "hi", "labelIds": ["INBOX"]}]}
        pages = [{"threads": [thread(1)], "nextPageToken": "p2"}, {"threads": [thread(2)]}]
        with patch("claude_mcp_service._call_tool", side_effect=pages) as call:
            emails = cms.ClaudeMcpService().fetch_emails("day", max_results=10)
        assert [e["id"] for e in emails] == ["m1", "m2"]
        assert emails[0]["from"] == "Ann <a@x.com>"
        assert emails[0]["to"] == "me@x.com"
        assert call.call_args_list[1].args[1]["pageToken"] == "p2"

    def test_fetch_events_maps_fields(self):
        resp = {"events": [{"id": "e1", "summary": "Sync", "start": {"dateTime": "2026-11-18T09:00:00-07:00"},
                            "end": {"dateTime": "2026-11-18T09:30:00-07:00"},
                            "attendees": [{"email": "b@x.com"}], "organizer": {"email": "a@x.com"}}]}
        with patch("claude_mcp_service._call_tool", return_value=resp) as call:
            events = cms.ClaudeMcpService().fetch_events("day", "current")
        assert events[0]["summary"] == "Sync"
        assert events[0]["attendees"] == ["b@x.com"]
        assert events[0]["organizer"] == "a@x.com"
        args = call.call_args.args[1]
        assert "+" not in args["startTime"] and not args["startTime"].endswith("Z")

    def test_profile_uses_primary_calendar_name(self):
        with patch("claude_mcp_service._call_tool", return_value={"summary": "me@x.com", "events": []}):
            assert cms.ClaudeMcpService().get_user_profile()["email"] == "me@x.com"
