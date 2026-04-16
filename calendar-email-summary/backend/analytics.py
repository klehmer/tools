"""Cross-report analytics powered by the same LLM backend as summarizer."""
import json

from summarizer import _call_llm, _extract_json


def generate(reports: list[dict]) -> dict:
    """Analyze multiple reports and return structured analytics."""
    # Separate email and calendar results with temporal context
    email_data = []
    calendar_data = []

    for r in reports[:20]:  # cap to avoid prompt overflow
        created = r.get("created_at", "unknown date")
        name = r.get("job_name", "Report")
        results = r.get("results", {})

        if "email" in results:
            entry = results["email"].copy()
            entry["_report_date"] = created
            entry["_report_name"] = name
            email_data.append(entry)

        if "calendar" in results:
            entry = results["calendar"].copy()
            entry["_report_date"] = created
            entry["_report_name"] = name
            calendar_data.append(entry)

    sections = []
    if calendar_data:
        sections.append(f"""CALENDAR REPORTS ({len(calendar_data)} reports):
{json.dumps(calendar_data, indent=1, default=str)[:40000]}""")

    if email_data:
        sections.append(f"""EMAIL REPORTS ({len(email_data)} reports):
{json.dumps(email_data, indent=1, default=str)[:40000]}""")

    if not sections:
        return {
            "overall_summary": "No email or calendar data found in the selected reports.",
            "cross_insights": [],
        }

    data_block = "\n\n".join(sections)

    prompt = f"""You are a productivity analyst. Analyze the following collection of summary reports and produce detailed analytics.

{data_block}

Return a single JSON object with this exact shape (omit sections that have no data):
{{
  "calendar_analytics": {{
    "hours_by_category": [{{"category": "1:1s", "hours": 5.5}}, ...],
    "busiest_days": [{{"day": "Monday", "event_count": 8, "hours": 6}}, ...],
    "recurring_patterns": ["Daily standup at 9am", ...],
    "top_attendees": [{{"name": "Jane Smith", "meeting_count": 12}}, ...],
    "meeting_load": {{"total_events": 0, "total_hours": 0, "avg_per_day": 0}},
    "summary": "2-3 sentence analysis of calendar patterns"
  }},
  "email_analytics": {{
    "top_senders": [{{"sender": "notifications@github.com", "count": 45}}, ...],
    "categories": [{{"category": "Automated/Notifications", "pct": 60}}, {{"category": "Important/Personal", "pct": 25}}, {{"category": "Newsletters/Marketing", "pct": 15}}],
    "response_needed": ["Subject line or description of email needing response"],
    "volume_trend": [{{"period": "report date or label", "count": 50}}, ...],
    "summary": "2-3 sentence analysis of email patterns"
  }},
  "cross_insights": [
    "Insight that spans both email and calendar data",
    "Another cross-cutting observation"
  ],
  "overall_summary": "3-5 sentence executive overview of productivity patterns, time allocation, and recommendations"
}}

For calendar analytics:
- Group meetings into categories (1:1s, team meetings, external, interviews, focus time, etc.)
- Identify which days are most packed
- Find recurring meetings and patterns
- Rank most frequent collaborators

For email analytics:
- Rank top senders by volume
- Classify emails into categories (automated/notifications, important/personal, newsletters/spam)
- Identify emails that likely need a response
- Show volume trends across the report dates

Be specific with numbers. Use actual data from the reports. Respond with ONLY the JSON object."""

    text = _call_llm(prompt)
    return _extract_json(text)
