import { useEffect, useMemo, useState } from "react";
import { Copy, Download, X, Check, Play } from "lucide-react";
import { getRules, getSessionToken, installCleanupFiles, startAgent } from "../services/api";
import type { CleanupRules } from "../types";

interface Props {
  runner: "claude-code" | "codex";
  totalMessages: number;
  onClose: () => void;
}

const BACKEND = "http://localhost:8000";

function rulesBlock(rules: CleanupRules | null): string {
  if (!rules) return "";
  const lines: string[] = ["## User-defined cleanup rules (MUST follow)"];

  if (rules.require_approval) {
    lines.push(
      "- APPROVAL REQUIRED: You MUST NOT call `/actions/delete` or `/actions/block` directly. DO NOT use `/approvals/request` either — that creates a parallel queue the user is not using.",
      "- Your ONLY job is to populate the live dashboard report by POSTing recommendations to `/agent/report`. The user will review them in the dashboard and click Delete / Download&Delete / Block / Unsubscribe / Skip themselves.",
      "- For each sender you want to recommend, add a group entry to the report's `groups` list with: sender, count, estimated_size_mb, suggested_action (`delete`|`block`|`unsubscribe`), reason, and EITHER a Gmail search `query` (e.g. `from:noreply@x.com`) OR an explicit `email_ids` list. Then re-POST `/agent/report` so the user sees it live."
    );
  } else {
    lines.push("- You may call `/actions/delete` and `/actions/block` directly with header `X-Approved: 1`.");
  }

  if (rules.download_before_delete) {
    lines.push(
      "- DOWNLOAD BEFORE DELETE: For every batch of email IDs you intend to delete, first call `POST /emails/download-bulk` with body `{\"email_ids\": [...], \"include_attachments\": true}` and save the returned ZIP to disk (e.g. `~/gmail-backup/<timestamp>.zip`). Only delete after the download succeeds."
    );
  }

  if (rules.protected_senders.length > 0) {
    lines.push(
      "- PROTECTED SENDERS — never delete, never block, never even suggest action against:",
      ...rules.protected_senders.map((s) => `    - ${s}`)
    );
  }

  if (rules.protected_keywords.length > 0) {
    lines.push(
      "- PROTECTED KEYWORDS — never delete any email whose subject contains:",
      ...rules.protected_keywords.map((k) => `    - ${k}`)
    );
  }

  if (rules.custom_instructions.trim()) {
    lines.push("- Additional instructions from the user:", `    ${rules.custom_instructions.trim()}`);
  }

  return lines.join("\n") + "\n\n";
}

function buildPrompt(token: string, total: number, rules: CleanupRules | null): string {
  return `You are an inbox cleanup agent. Your job is to dramatically reduce the user's Gmail inbox by deleting bulk/junk email, unsubscribing from newsletters, and blocking spam senders. The user has ${total.toLocaleString()} messages and wants the inbox burned down significantly.

You will run as a long-lived agent and work in iterations. Pace your work to respect Gmail API quotas — pause briefly between large delete batches if needed.

IMPORTANT — RATE LIMIT / CAPACITY HANDLING (NON-NEGOTIABLE):
- If you hit ANY model rate-limit, usage-limit, "out of capacity", quota, 429, "weekly limit reached", or similar error, DO NOT exit, DO NOT stop, and DO NOT ask the user to restart you.
- When you hit such an error, sleep for at least 15 minutes (\`sleep 900\`), then try a single small probe request. If it still fails, double the sleep (30m, 60m, ...) up to 6 hours, then continue probing once per hour until capacity returns.
- As soon as a probe succeeds, resume exactly where you left off in the strategy below. Persist any in-flight state (current sender being processed, last \`/agent/report\` you posted) to a small scratch file like \`/tmp/gmail_manager_agent_state.json\` so you can recover after a sleep.
- Append a one-line status to \`/tmp/gmail_manager_agent.log\` (e.g. \`echo "[$(date)] hit rate limit, sleeping 900s" >> /tmp/gmail_manager_agent.log\`) so the user can monitor progress in the dashboard.
- The user will NOT manually restart you. Treat this as a long-lived job — it is acceptable for it to run for many hours with sleep periods in between.

LIVE LOG: Append meaningful progress lines to \`/tmp/gmail_manager_agent.log\` continuously (start of run, before/after each sender batch, after each \`/agent/report\` POST, on error, on sleep, on resume). The dashboard tails this file. Format: \`[ISO timestamp] message\`. Example: \`echo "[$(date -u +%FT%TZ)] processed sender X — queued 312 ids for approval" >> /tmp/gmail_manager_agent.log\`.

SKIP ALREADY-UNSUBSCRIBED: Before recommending an "unsubscribe" action for a sender, GET \`/agent/unsubscribed\` and check whether the sender's email is already in that list. If it is, DO NOT recommend unsubscribing again (you may still recommend deleting their existing mail). When the user clicks Unsubscribe in the UI, the dashboard records the sender there automatically — but if you unsubscribe programmatically via \`/actions/unsubscribe\`, also POST the sender to \`/agent/unsubscribed\` so future runs remember.

${rulesBlock(rules)}## Gmail Manager API
Base URL: ${BACKEND}
Auth: include header \`X-Session-Token: ${token}\` on every request.

### Read tools
- \`GET /gmail/overview\` → {email, total_messages}
- \`GET /gmail/top-senders?limit=30\` → top senders by volume (with email IDs and size estimates)
- \`GET /gmail/search?query=<gmail-search-syntax>&limit=200\` → search results
- \`GET /gmail/unsubscribe-candidates?limit=50\` → promotional emails with unsubscribe links

### Action tools
- \`POST /actions/delete\`        body: {"email_ids": ["id1", "id2", ...]}    permanently delete (up to 1000 ids per call) — requires header X-Approved: 1
- \`POST /actions/block\`         body: {"sender_email": "..."}                creates filter + deletes existing — requires header X-Approved: 1
- \`POST /actions/unsubscribe\`   body: {"sender_email": "...", "unsubscribe_link": "..."}

### Memory of past unsubscribes (so you don't recommend the same sender twice)
- \`GET /agent/unsubscribed\` → {"senders": ["addr1@x.com", ...]} — check before recommending unsubscribe
- \`POST /agent/unsubscribed\` body: {"sender_email": "..."} — record after a programmatic unsubscribe

### Live report (display recommendations to the user in the dashboard)
- \`POST /agent/report\`          body: {"runner": "codex", "status": "running", "summary": "...", "starting_total": N, "current_total": N, "deleted_so_far": N, "groups": [{"sender":"...", "count":N, "estimated_size_mb":N, "suggested_action":"delete|block|unsubscribe", "reason":"...", "query":"<gmail search query>"}]}
- This OVERWRITES the current report each time. POST it after every meaningful step so the user sees progress.
- The user can act on each group directly from the dashboard (Download&Delete / Delete / Block / Skip). The report is the PRIMARY way the user reviews your recommendations — keep it complete and current.
- Set \`status: "done"\` on the final report when you're finished.
- Each group should have a \`query\` (e.g. \`from:noreply@example.com\` or \`from:example.com older_than:1y\`) so the dashboard can resolve the email IDs at click time. Or include \`email_ids\` directly if you have them.

## Strategy — ONE PASS PER INVOCATION, THEN EXIT

This process runs inside a wrapper loop that will re-invoke you automatically. Your job is to do ONE productive pass of work and then exit cleanly. DO NOT poll, sleep, or loop at the end — exit so the wrapper can restart you fresh.

**MINIMUM GROUP SIZE: 20.** Do NOT post any group with fewer than 20 emails unless it's a clear block/unsubscribe case for a known spammer. Tiny 1–3 email groups are noise — skip them. The user has tens of thousands of emails left; focus on volume.

A "pass" is:
1. Call \`/gmail/overview\` to get the current message count. POST \`/agent/report\` with status="running" and the current overview numbers.
2. **SWEEP QUERIES FIRST — this is where the volume lives.** Run each of the queries below via \`/gmail/search\` with \`limit=500\`. For each query that returns ≥20 results, add it as a group with the \`query\` field set (the dashboard resolves ids at click time). Re-POST \`/agent/report\` after each sweep so the user sees progress live.
   - \`category:promotions older_than:6m\`
   - \`category:promotions older_than:1y\`
   - \`category:social older_than:6m\`
   - \`category:updates older_than:1y\`
   - \`category:forums older_than:1y\`
   - \`older_than:3y -is:starred -is:important\`
   - \`older_than:5y -is:starred -is:important\`
   - \`has:attachment larger:5M older_than:1y\`
   - \`from:noreply OR from:no-reply OR from:donotreply older_than:6m\`
   - \`subject:(unsubscribe OR newsletter OR "view in browser") older_than:3m\`
   - \`subject:(receipt OR order OR shipped OR delivery) older_than:2y\`
3. THEN call \`/gmail/top-senders?limit=50\`. For each sender with count ≥20, decide a suggested_action (\`delete\` / \`block\` / \`unsubscribe\`). **Skip \`keep\` recommendations entirely — they clutter the report.** Add a \`query\` field like \`from:bare@email.com older_than:30d\` (or whatever your rules allow). Re-POST \`/agent/report\` every ~5 additions.
4. It is FINE and EXPECTED to re-propose senders/queries that already exist in the report — the server merges by (sender, action) and the user may have cleared the report. DO NOT "skip senders already in the report" — that causes the agent to scrape tiny groups from the long tail as runs accumulate. Just propose the best high-volume work every pass.
5. POST one final \`/agent/report\` with an updated \`current_total\` and a short \`summary\` describing what this pass added.
6. **EXIT.** Do not sleep. Do not poll. Do not keep looking. The wrapper script will re-invoke you in 60 seconds.

If the inbox already looks fully cleaned up (report has covered the top 50 senders and all sweep queries return nothing new), post a final report with status="done" and exit — the wrapper will see that and keep looping, but each subsequent pass will just re-confirm "done" quickly and sleep.

## Safety rules
- NEVER delete starred (\`is:starred\`) or important (\`is:important\`) emails.
- NEVER delete from senders that look personal (firstname.lastname@<personaldomain>, individual humans).
- Prefer broad sweeps with \`older_than:\` filters over guessing — old automated mail is almost always safe.
- If unsure about a sender, skip it.

## Curl example
\`\`\`bash
curl -s -H "X-Session-Token: ${token}" "${BACKEND}/gmail/overview"
curl -s -H "X-Session-Token: ${token}" "${BACKEND}/gmail/top-senders?limit=50"
curl -s -H "X-Session-Token: ${token}" --get --data-urlencode "query=category:promotions older_than:6m" --data "limit=500" "${BACKEND}/gmail/search"
curl -s -H "X-Session-Token: ${token}" -H "Content-Type: application/json" -X POST -d '{"email_ids":["1234","5678"]}' "${BACKEND}/actions/delete"
curl -s -H "X-Session-Token: ${token}" -H "Content-Type: application/json" -X POST -d '{"sender_email":"news@example.com"}' "${BACKEND}/actions/block"
\`\`\`

Begin now. Work autonomously through the strategy above and report progress as you go.`;
}

export default function AgentRunnerModal({ runner, totalMessages, onClose }: Props) {
  const [copied, setCopied] = useState(false);
  const [installed, setInstalled] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [started, setStarted] = useState(false);
  const [rules, setRules] = useState<CleanupRules | null>(null);
  const token = getSessionToken() ?? "<NO_SESSION_TOKEN>";

  useEffect(() => {
    getRules().then(setRules).catch(() => setRules(null));
  }, []);

  const prompt = useMemo(
    () => buildPrompt(token, totalMessages, rules),
    [token, totalMessages, rules]
  );

  const cliCommand = runner === "claude-code" ? "claude" : "codex";
  const runnerName = runner === "claude-code" ? "Claude Code" : "Codex";

  const copy = async () => {
    await navigator.clipboard.writeText(prompt);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const downloadPrompt = () => {
    const blob = new Blob([prompt], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "gmail-prompt.txt";
    a.click();
    URL.revokeObjectURL(url);
  };

  const installToHome = async () => {
    try {
      const res = await installCleanupFiles(prompt, runner);
      setInstalled(`Installed: ${res.prompt_path} and ${res.script_path}`);
      setTimeout(() => setInstalled(null), 6000);
    } catch (e) {
      alert(`Failed to install: ${e}`);
    }
  };

  const installAndStart = async () => {
    setStarting(true);
    try {
      await installCleanupFiles(prompt, runner);
      await startAgent(runner);
      setStarted(true);
      setInstalled("Agent started in the background. Watch the Agent Log panel for progress.");
    } catch (e) {
      alert(`Failed: ${e}`);
    } finally {
      setStarting(false);
    }
  };

  const downloadRunner = async () => {
    const res = await fetch(`/agent/runner-script?runner=${runner}`, {
      headers: { "X-Session-Token": token },
    });
    if (!res.ok) {
      alert("Failed to download runner script");
      return;
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `run-cleanup-${runner}.sh`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="flex max-h-[90vh] w-full max-w-3xl flex-col rounded-2xl bg-white shadow-xl">
        <div className="flex items-center justify-between border-b px-6 py-4">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">
              Run cleanup with {runnerName}
            </h2>
            <p className="text-xs text-gray-500">
              Copy the prompt below and paste it into your <code>{cliCommand}</code> session
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-full p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-700"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          <div className="mb-4 rounded-lg border border-blue-200 bg-blue-50 p-3 text-xs text-blue-900">
            <p className="mb-2 font-semibold">Recommended: forever-loop runner</p>
            <p className="mb-2">
              {runnerName} only processes one turn per invocation. Use the loop
              script to keep it running automatically — it sleeps and retries on
              rate-limit errors so you don't have to restart it manually.
            </p>
            <ol className="mb-2 list-decimal space-y-0.5 pl-5">
              <li>Click <strong>Install & Start Agent</strong> — installs files to <code>~/</code> and launches the runner in the background.</li>
              <li>Watch progress in the dashboard's log panel.</li>
              <li>Or install only, then start from a terminal yourself.</li>
            </ol>
            <div className="flex flex-wrap gap-2">
              <button
                onClick={installAndStart}
                disabled={starting || started}
                className="flex items-center gap-1 rounded-md bg-green-600 px-2.5 py-1 text-xs font-semibold text-white shadow hover:bg-green-700 disabled:opacity-50"
              >
                <Play className="h-3 w-3" />
                {starting ? "Starting…" : started ? "Agent running" : "Install & Start Agent"}
              </button>
              <button
                onClick={installToHome}
                className="flex items-center gap-1 rounded-md bg-white px-2.5 py-1 text-xs font-semibold text-green-700 ring-1 ring-green-400 hover:bg-green-50"
              >
                <Download className="h-3 w-3" />
                Install to ~/ only
              </button>
              <button
                onClick={downloadPrompt}
                className="flex items-center gap-1 rounded-md bg-white px-2.5 py-1 text-xs font-semibold text-blue-700 ring-1 ring-blue-300 hover:bg-blue-100"
              >
                <Download className="h-3 w-3" />
                Download prompt
              </button>
              <button
                onClick={downloadRunner}
                className="flex items-center gap-1 rounded-md bg-blue-600 px-2.5 py-1 text-xs font-semibold text-white shadow hover:bg-blue-700"
              >
                <Download className="h-3 w-3" />
                Download runner script
              </button>
            </div>
            {installed && (
              <p className="mt-2 text-xs font-semibold text-green-800">{installed}</p>
            )}
          </div>

          <p className="mb-2 text-xs font-semibold text-gray-700">Or run a single pass manually:</p>
          <ol className="mb-4 list-decimal space-y-1 pl-5 text-sm text-gray-700">
            <li>
              Open a terminal and run <code className="rounded bg-gray-100 px-1.5 py-0.5">{cliCommand}</code>{" "}
              in any directory.
            </li>
            <li>Paste the prompt below.</li>
            <li>
              {runnerName} will run one cleanup pass and exit. (Use the loop
              script above for continuous operation.)
            </li>
            <li>Keep this browser window open — sessions are tied to it.</li>
          </ol>

          <div className="relative">
            <button
              onClick={copy}
              className="absolute right-2 top-2 flex items-center gap-1 rounded-md bg-blue-600 px-2.5 py-1 text-xs font-medium text-white shadow hover:bg-blue-700"
            >
              {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
              {copied ? "Copied" : "Copy"}
            </button>
            <pre className="max-h-[50vh] overflow-auto rounded-lg border border-gray-200 bg-gray-50 p-4 pr-20 text-xs text-gray-800">
              {prompt}
            </pre>
          </div>
        </div>

        <div className="border-t px-6 py-3 text-right">
          <button
            onClick={onClose}
            className="rounded-md border border-gray-300 bg-white px-4 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
