"""
LLM agent that analyses a Gmail inbox and returns structured recommendations
using Claude claude-opus-4-6 with tool use.
"""

import asyncio
import json
import logging
import re
from typing import Any, Dict

import anthropic

logger = logging.getLogger("agent")
logger.setLevel(logging.INFO)

import rules_manager
from gmail_service import GmailService
from models import AnalysisResult, EmailGroup


def _rules_block() -> str:
    rules = rules_manager.get_rules()
    parts = ["\n## User-defined cleanup rules (MUST follow)"]
    if rules.get("require_approval"):
        parts.append(
            "- Approval is required: only RECOMMEND deletes/blocks. The user will approve them in the UI."
        )
    if rules.get("download_before_delete"):
        parts.append(
            "- The user wants emails downloaded before deletion. Mention this in suggestion_reason where relevant."
        )
    protected = rules.get("protected_senders") or []
    if protected:
        parts.append("- NEVER suggest deleting/blocking these senders: " + ", ".join(protected))
    keywords = rules.get("protected_keywords") or []
    if keywords:
        parts.append("- NEVER suggest deleting emails whose subject contains: " + ", ".join(keywords))
    custom = (rules.get("custom_instructions") or "").strip()
    if custom:
        parts.append("- Additional user instructions: " + custom)
    if len(parts) == 1:
        return ""
    return "\n".join(parts) + "\n"

SYSTEM_PROMPT = """You are an expert Gmail inbox management assistant. \
Your goal is to analyse the user's Gmail inbox and produce actionable \
recommendations to free up storage and reduce clutter.

Use the available tools to gather data:
1. Start with get_inbox_overview to understand the inbox size.
2. Use get_top_senders to find who sends the most emails.
3. Use search_emails with queries like "category:promotions", \
"category:forums", "older_than:2y", "has:attachment larger:1M" \
to surface candidate groups.
4. Use get_emails_with_unsubscribe to find newsletter subscriptions.
5. Call search_emails again for any specific senders or patterns \
you want to investigate further.

After 4-8 tool calls, return your complete analysis as a single \
JSON code block (```json ... ```) with this exact structure:

{
  "analysis_summary": "2-3 sentence summary",
  "email_groups": [
    {
      "sender": "noreply@example.com",
      "sender_name": "Example Newsletter",
      "count": 120,
      "total_size_mb": 38.5,
      "oldest_date": "2019-06-01",
      "newest_date": "2024-01-10",
      "email_ids": ["id1", "id2"],
      "category": "delete",
      "suggestion_reason": "120 promotional emails since 2019",
      "unsubscribe_link": null
    }
  ],
  "total_emails_to_process": 600,
  "estimated_storage_freed_mb": 250.0
}

Rules:
- category must be "delete", "unsubscribe", or "block"
- For "unsubscribe" include unsubscribe_link when available
- Provide 10-50 email_ids per group
- Return 5-15 groups that will have the most impact
- Only return the JSON code block; no extra commentary after it
"""

TOOLS = [
    {
        "name": "get_inbox_overview",
        "description": (
            "Get a high-level overview of the Gmail inbox: "
            "email address, total message count."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_top_senders",
        "description": (
            "Sample up to 500 recent inbox messages and return the top "
            "senders by message count, with estimated size and email IDs."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of top senders to return (default 30)",
                }
            },
            "required": [],
        },
    },
    {
        "name": "search_emails",
        "description": (
            "Search Gmail with Gmail search syntax (e.g. "
            "'category:promotions', 'older_than:2y', "
            "'has:attachment larger:5M', 'from:noreply@'). "
            "Returns emails with sender, subject, date, size, and unsubscribe link."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Gmail search query string",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max emails to return (default 50, max 200)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_emails_with_unsubscribe",
        "description": (
            "Find promotional/newsletter emails that have unsubscribe links. "
            "Returns a list with sender info and unsubscribe URLs."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Max emails to return (default 50)",
                }
            },
            "required": [],
        },
    },
]


class GmailAnalysisAgent:
    def __init__(self, gmail: GmailService):
        self.gmail = gmail
        self.client = anthropic.Anthropic()

    async def analyze(self) -> AnalysisResult:
        """Run the agentic analysis loop and return structured recommendations."""
        messages = [
            {
                "role": "user",
                "content": (
                    "Please analyse my Gmail inbox and identify:\n"
                    "1. Bulk emails I can delete\n"
                    "2. Subscriptions I should unsubscribe from\n"
                    "3. Spam/unwanted senders to block\n\n"
                    "Focus on the changes that will free the most storage "
                    "and clean the inbox most effectively."
                ),
            }
        ]

        loop = asyncio.get_event_loop()
        max_iterations = 15

        for i in range(max_iterations):
            # On the final iteration, drop tools so the model is forced to emit the JSON
            is_final = i == max_iterations - 1
            call_kwargs = dict(
                model="claude-haiku-4-5",
                max_tokens=8192,
                system=SYSTEM_PROMPT + _rules_block(),
                messages=messages,
            )
            if not is_final:
                call_kwargs["tools"] = TOOLS
            else:
                messages.append({
                    "role": "user",
                    "content": "You have gathered enough data. Return the final JSON analysis now, with no further tool calls.",
                })
                call_kwargs["messages"] = messages

            logger.info("agent iteration %d (final=%s)", i, is_final)
            response = await loop.run_in_executor(
                None,
                lambda kw=call_kwargs: self.client.messages.create(**kw),
            )
            logger.info(
                "iter %d: stop_reason=%s in=%d out=%d",
                i,
                response.stop_reason,
                response.usage.input_tokens,
                response.usage.output_tokens,
            )

            # Append the full assistant content (including thinking blocks)
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                # Extract text and parse JSON
                for block in response.content:
                    if hasattr(block, "type") and block.type == "text":
                        return self._parse_result(block.text)
                raise ValueError("Agent returned end_turn with no text block")

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if hasattr(block, "type") and block.type == "tool_use":
                        logger.info("tool_call %s input=%s", block.name, block.input)
                        result = await loop.run_in_executor(
                            None,
                            lambda b=block: self._execute_tool(b.name, b.input),
                        )
                        content = json.dumps(result)
                        # Truncate huge payloads to stay under rate-limit & keep latency sane
                        if len(content) > 8000:
                            content = content[:8000] + "...[truncated]"
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": content,
                            }
                        )
                messages.append({"role": "user", "content": tool_results})
            else:
                break

        raise RuntimeError("Agent did not complete analysis within iteration limit")

    def _execute_tool(self, name: str, input_data: Dict[str, Any]) -> Any:
        if name == "get_inbox_overview":
            return self.gmail.get_inbox_overview()
        elif name == "get_top_senders":
            limit = input_data.get("limit", 30)
            return self.gmail.get_top_senders(limit)
        elif name == "search_emails":
            query = input_data["query"]
            limit = input_data.get("limit", 50)
            return self.gmail.search_emails(query, min(limit, 50))
        elif name == "get_emails_with_unsubscribe":
            limit = input_data.get("limit", 50)
            return self.gmail.get_emails_with_unsubscribe(limit)
        else:
            return {"error": f"Unknown tool: {name}"}

    @staticmethod
    def _parse_result(text: str) -> AnalysisResult:
        # Try JSON code block first
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            raw = json.loads(match.group(1))
        else:
            # Fallback: find the outermost JSON object
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if not match:
                raise ValueError("No JSON found in agent response")
            raw = json.loads(match.group(0))

        groups = [EmailGroup(**g) for g in raw.get("email_groups", [])]
        return AnalysisResult(
            analysis_summary=raw.get("analysis_summary", ""),
            email_groups=groups,
            total_emails_to_process=raw.get("total_emails_to_process", 0),
            estimated_storage_freed_mb=raw.get("estimated_storage_freed_mb", 0.0),
        )
