# Gmail Manager

Local-only tool for burning down a bloated Gmail inbox. Combines a FastAPI backend (Gmail + Drive APIs) with a React dashboard and a long-lived CLI cleanup agent (Claude Code or Codex) that posts recommendations back to the dashboard for one-click review.

## Architecture

```
backend/    FastAPI + Google Gmail/Drive APIs, agent report store, runner script generator
frontend/   React + TypeScript + Vite + Tailwind dashboard
```

Two execution models:

1. **Dashboard-driven** — log in, view top senders / storage / candidates, click Delete / Block / Unsubscribe directly.
2. **Agent-driven** (recommended for large inboxes) — a CLI agent (`codex` or `claude`) runs in a forever-loop wrapper, proposes groups via `POST /agent/report`, and you approve them from the dashboard.

## Setup

### 1. Google Cloud credentials

1. [Google Cloud Console](https://console.cloud.google.com/) → create a project.
2. Enable the **Gmail API** and **Drive API** (Drive is used for storage quota).
3. Create OAuth 2.0 credentials (Web application).
4. Authorized redirect URI: `http://localhost:8000/auth/callback`.

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, ANTHROPIC_API_KEY
uvicorn main:app --reload
```

API at `http://localhost:8000`.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Dashboard at `http://localhost:5173`.

## Running the cleanup agent

Either Claude Code (`claude`) or Codex (`codex`) CLI must be installed and authenticated.

1. In the dashboard, open **Run cleanup with …** → click **Install to ~/ (prompt + runner)**. This writes `~/gmail-prompt.txt` and `~/run-cleanup-<runner>.sh` (chmod +x) directly.
2. Start the loop:
   ```bash
   nohup ~/run-cleanup-codex.sh > /tmp/gmail-runner.out 2>&1 &
   ```
3. Watch the **Agent log** panel at the bottom of the dashboard. Recommendations appear in the **Agent report** panel as the agent discovers them.
4. Act on groups from the dashboard: **Download & Delete**, **Delete**, **Block**, **Unsubscribe**, **Skip**, or **Keep all** to bulk-dismiss.

The runner script survives rate limits (exponential backoff 15m → 6h) and retries quickly on manual kills (SIGINT/SIGKILL/SIGTERM).

### Agent strategy (one pass per invocation)

The bundled prompt tells the agent to:

- Run **sweep queries first** (`category:promotions older_than:6m`, `older_than:3y -is:starred -is:important`, etc.) — this is where the volume lives.
- Then walk `/gmail/top-senders?limit=50` for any remaining high-volume senders.
- Enforce a **minimum group size of 20** — no tiny 1–3 email groups.
- Never propose `keep` groups (they clutter the report).
- Re-propose senders across runs — the server merges by `(sender, action)`, so duplicates are free.
- Honor rules from the Rules panel (protected senders/keywords, min age, approval requirement, etc.).
- **Exit after one pass.** The wrapper restarts it every 60 s.

## Runtime controls (dashboard)

Agent log header:

- **Show processes** — `GET /agent/processes` lists running `run-cleanup-*.sh`, `codex exec`, and `claude -p` with PID + elapsed time.
- **Kill all agents** — `POST /agent/kill-all` (`pkill -9 -f` on the three patterns above).
- **Clear** — empties `/tmp/gmail_manager_agent.log`.

Agent report header:

- **Keep all (N)** — bulk-dismiss every `keep` recommendation.
- **Clear report** — wipes the accumulated report so the next agent pass can re-propose senders. Use this if recommendations start degrading (long-tail scraping).
- **×** — same as Clear, without the confirm.

## Key endpoints

| Method | Path | Purpose |
|---|---|---|
| GET  | `/gmail/overview`            | email + message count |
| GET  | `/gmail/top-senders`         | top senders by volume |
| GET  | `/gmail/search`              | Gmail search passthrough |
| GET  | `/gmail/unsubscribe-candidates` | promotional mail with unsubscribe links |
| POST | `/actions/delete`            | batch delete (requires `X-Approved: 1`) |
| POST | `/actions/block`             | filter + delete sender (requires `X-Approved: 1`) |
| POST | `/actions/unsubscribe`       | fetch + follow unsubscribe link |
| POST | `/emails/download-bulk`      | parallel ZIP of `.eml` + attachments |
| GET/POST/DELETE | `/agent/report`   | live recommendations store |
| POST | `/agent/report/action`       | mark a group actioned |
| GET/POST/DELETE | `/agent/logs`     | tail / clear `/tmp/gmail_manager_agent.log` |
| GET  | `/agent/processes`           | list running runner/CLI processes |
| POST | `/agent/kill-all`            | kill runner + CLI agents |
| POST | `/agent/install-files`       | write `~/gmail-prompt.txt` + runner script |
| GET  | `/agent/runner-script`       | download runner wrapper |
| GET/POST | `/agent/unsubscribed`    | persistent unsubscribed-sender memory |
| GET/POST | `/rules`                 | cleanup rules (protected senders/keywords, approval, etc.) |

## Notes & gotchas

- **Local-only tool** — CORS is wide open, sessions are in-memory, and `/agent/kill-all` runs `pkill` on the host. Do not expose to the network.
- Scope `https://mail.google.com/` is required for `batchDelete`.
- Drive API `about.get` is used for storage quota in the header.
- Downloads and deletes run in parallel (backend `ThreadPoolExecutor`, frontend 4-worker queue) and don't block each other.
- `/agent/report` writes are serialized via a `threading.Lock` to prevent race conditions when concurrent workers mark groups actioned.
- The log file lives at `/tmp/gmail_manager_agent.log` (hardcoded — `tempfile.gettempdir()` on macOS resolves to `/var/folders/...` which caused a silent bug).
- Claude Code statusline: see `~/.claude/statusline.sh` for the ccusage wrapper that shows % remaining in the current 5-hour block right after the model name.
