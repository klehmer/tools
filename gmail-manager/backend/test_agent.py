"""Tests for agent.py — Anthropic API calls are mocked."""

import json
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
import pytest
from agent import GmailAnalysisAgent, _rules_block


# ===================================================================
# _rules_block
# ===================================================================

class TestRulesBlock:
    def test_empty_rules(self):
        with patch("rules_manager.get_rules", return_value={
            "require_approval": False,
            "download_before_delete": False,
            "protected_senders": [],
            "protected_keywords": [],
            "custom_instructions": "",
        }):
            assert _rules_block() == ""

    def test_all_rules_populated(self):
        with patch("rules_manager.get_rules", return_value={
            "require_approval": True,
            "download_before_delete": True,
            "protected_senders": ["boss@corp.com", "@vip.com"],
            "protected_keywords": ["invoice", "receipt"],
            "custom_instructions": "Keep all starred emails",
        }):
            block = _rules_block()
            assert "Approval is required" in block
            assert "downloaded before deletion" in block
            assert "boss@corp.com" in block
            assert "@vip.com" in block
            assert "invoice" in block
            assert "Keep all starred" in block

    def test_partial_rules(self):
        with patch("rules_manager.get_rules", return_value={
            "require_approval": True,
            "download_before_delete": False,
            "protected_senders": [],
            "protected_keywords": ["important"],
            "custom_instructions": "",
        }):
            block = _rules_block()
            assert "Approval is required" in block
            assert "important" in block
            assert "downloaded" not in block


# ===================================================================
# _parse_result
# ===================================================================

class TestParseResult:
    def test_json_code_block(self):
        text = '''Here's my analysis:
```json
{
  "analysis_summary": "Found lots of junk",
  "email_groups": [
    {
      "sender": "promo@store.com",
      "sender_name": "Store",
      "count": 50,
      "total_size_mb": 15.0,
      "oldest_date": "2020-01-01",
      "newest_date": "2024-01-01",
      "email_ids": ["id1", "id2"],
      "category": "delete",
      "suggestion_reason": "Old promotions"
    }
  ],
  "total_emails_to_process": 50,
  "estimated_storage_freed_mb": 15.0
}
```'''
        result = GmailAnalysisAgent._parse_result(text)
        assert result.analysis_summary == "Found lots of junk"
        assert len(result.email_groups) == 1
        assert result.email_groups[0].sender == "promo@store.com"
        assert result.total_emails_to_process == 50

    def test_bare_json(self):
        text = '''{
  "analysis_summary": "Summary",
  "email_groups": [],
  "total_emails_to_process": 0,
  "estimated_storage_freed_mb": 0.0
}'''
        result = GmailAnalysisAgent._parse_result(text)
        assert result.analysis_summary == "Summary"

    def test_no_json_raises(self):
        with pytest.raises(ValueError, match="No JSON found"):
            GmailAnalysisAgent._parse_result("No structured data here")

    def test_defaults_for_missing_fields(self):
        text = '```json\n{"email_groups": []}\n```'
        result = GmailAnalysisAgent._parse_result(text)
        assert result.analysis_summary == ""
        assert result.total_emails_to_process == 0
        assert result.estimated_storage_freed_mb == 0.0


# ===================================================================
# _execute_tool
# ===================================================================

class TestExecuteTool:
    def setup_method(self):
        self.gmail = MagicMock()
        self.agent = GmailAnalysisAgent.__new__(GmailAnalysisAgent)
        self.agent.gmail = self.gmail

    def test_get_inbox_overview(self):
        self.gmail.get_inbox_overview.return_value = {"total": 5000}
        result = self.agent._execute_tool("get_inbox_overview", {})
        assert result["total"] == 5000

    def test_get_top_senders(self):
        self.gmail.get_top_senders.return_value = {"senders": []}
        result = self.agent._execute_tool("get_top_senders", {"limit": 10})
        self.gmail.get_top_senders.assert_called_once_with(10)

    def test_get_top_senders_default_limit(self):
        self.gmail.get_top_senders.return_value = {"senders": []}
        self.agent._execute_tool("get_top_senders", {})
        self.gmail.get_top_senders.assert_called_once_with(30)

    def test_search_emails(self):
        self.gmail.search_emails.return_value = {"emails": []}
        self.agent._execute_tool("search_emails", {"query": "from:test", "limit": 100})
        self.gmail.search_emails.assert_called_once_with("from:test", 50)  # capped

    def test_search_emails_default_limit(self):
        self.gmail.search_emails.return_value = {"emails": []}
        self.agent._execute_tool("search_emails", {"query": "test"})
        self.gmail.search_emails.assert_called_once_with("test", 50)

    def test_get_emails_with_unsubscribe(self):
        self.gmail.get_emails_with_unsubscribe.return_value = {"emails": []}
        self.agent._execute_tool("get_emails_with_unsubscribe", {"limit": 25})
        self.gmail.get_emails_with_unsubscribe.assert_called_once_with(25)

    def test_unknown_tool(self):
        result = self.agent._execute_tool("nonexistent_tool", {})
        assert "error" in result
        assert "Unknown tool" in result["error"]


# ===================================================================
# analyze (integration-style with mocked Anthropic)
# ===================================================================

class TestAnalyze:
    def _make_agent(self):
        gmail = MagicMock()
        gmail.get_inbox_overview.return_value = {"total_messages": 5000}
        gmail.get_top_senders.return_value = {"senders": [], "total_sampled": 0}
        gmail.search_emails.return_value = {"emails": [], "total_found": 0}
        agent = GmailAnalysisAgent.__new__(GmailAnalysisAgent)
        agent.gmail = gmail
        agent.client = MagicMock()
        return agent

    def _make_response(self, stop_reason, content):
        resp = MagicMock()
        resp.stop_reason = stop_reason
        resp.content = content
        resp.usage = MagicMock(input_tokens=100, output_tokens=200)
        return resp

    def _text_block(self, text):
        block = MagicMock()
        block.type = "text"
        block.text = text
        return block

    def _tool_use_block(self, name, input_data, tool_id="tu1"):
        block = MagicMock()
        block.type = "tool_use"
        block.name = name
        block.input = input_data
        block.id = tool_id
        return block

    @pytest.mark.asyncio
    async def test_simple_end_turn(self):
        agent = self._make_agent()
        json_result = json.dumps({
            "analysis_summary": "Clean inbox",
            "email_groups": [],
            "total_emails_to_process": 0,
            "estimated_storage_freed_mb": 0.0,
        })
        text_block = self._text_block(f"```json\n{json_result}\n```")
        agent.client.messages.create.return_value = self._make_response("end_turn", [text_block])

        result = await agent.analyze()
        assert result.analysis_summary == "Clean inbox"

    @pytest.mark.asyncio
    async def test_tool_use_then_end_turn(self):
        agent = self._make_agent()

        # First call: tool_use
        tool_block = self._tool_use_block("get_inbox_overview", {})
        resp1 = self._make_response("tool_use", [tool_block])

        # Second call: end_turn with result
        json_result = json.dumps({
            "analysis_summary": "Done",
            "email_groups": [],
            "total_emails_to_process": 0,
            "estimated_storage_freed_mb": 0.0,
        })
        text_block = self._text_block(f"```json\n{json_result}\n```")
        resp2 = self._make_response("end_turn", [text_block])

        agent.client.messages.create.side_effect = [resp1, resp2]
        result = await agent.analyze()
        assert result.analysis_summary == "Done"
        assert agent.client.messages.create.call_count == 2

    @pytest.mark.asyncio
    async def test_truncates_large_tool_output(self):
        agent = self._make_agent()
        agent.gmail.get_top_senders.return_value = {"data": "x" * 10000}

        tool_block = self._tool_use_block("get_top_senders", {"limit": 30})
        resp1 = self._make_response("tool_use", [tool_block])

        json_result = json.dumps({
            "analysis_summary": "Done",
            "email_groups": [],
            "total_emails_to_process": 0,
            "estimated_storage_freed_mb": 0.0,
        })
        text_block = self._text_block(f"```json\n{json_result}\n```")
        resp2 = self._make_response("end_turn", [text_block])

        agent.client.messages.create.side_effect = [resp1, resp2]
        result = await agent.analyze()
        # Check the tool result message was truncated
        messages_arg = agent.client.messages.create.call_args_list[1]
        tool_msg = messages_arg.kwargs.get("messages") or messages_arg[1].get("messages")
        # Find the tool_result in messages
        for m in tool_msg:
            if isinstance(m.get("content"), list):
                for item in m["content"]:
                    if isinstance(item, dict) and item.get("type") == "tool_result":
                        assert len(item["content"]) <= 8020  # 8000 + "[truncated]"

    @pytest.mark.asyncio
    async def test_max_iterations_raises(self):
        agent = self._make_agent()
        # Always return tool_use to exhaust iterations
        tool_block = self._tool_use_block("get_inbox_overview", {})
        resp = self._make_response("tool_use", [tool_block])

        # On the final iteration (no tools), return end_turn with no text
        no_text = self._make_response("end_turn", [])

        # 14 tool_use responses + 1 end_turn with no text block on final
        agent.client.messages.create.side_effect = [resp] * 14 + [no_text]
        with pytest.raises(ValueError, match="no text block"):
            await agent.analyze()

    @pytest.mark.asyncio
    async def test_unexpected_stop_reason_breaks(self):
        agent = self._make_agent()
        resp = self._make_response("max_tokens", [])
        agent.client.messages.create.return_value = resp
        with pytest.raises(RuntimeError, match="did not complete"):
            await agent.analyze()
