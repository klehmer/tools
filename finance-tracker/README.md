# Finance Tracker

Local-first personal finance dashboard. Link multiple institutions (Robinhood,
PNC, Vanguard, Fidelity, and 12,000+ others) via **Plaid** in read-only mode,
then see consolidated net worth, asset breakdown, recurring subscriptions,
income, and goal-based financial plans — all running on your own machine.

## Features

- **Read-only account linking** via Plaid Link. No credentials are stored
  locally; only Plaid access tokens (in `backend/data/items.json`, chmod 600).
- **Multi-institution aggregation.** Link as many banks, brokerages, credit
  cards, and loans as you want.
- **Net worth** with asset/liability breakdown (Cash, Investments, Retirement,
  Crypto, Credit Cards, Student Loans, Mortgages, …).
- **Subscription detection.** A custom recurring-charge detector groups
  transactions by normalized merchant, checks amount stability and cadence,
  and flags weekly/bi-weekly/monthly/quarterly/annual subscriptions with
  annualized cost.
- **Income analysis** over configurable 30–365 day windows using Plaid's
  Payroll/Deposit categories plus payroll-keyword heuristics.
- **Goals & financial plan.** Add goals (savings, debt payoff, retirement,
  major purchase). The planner projects where you'll land given your current
  balance, monthly contribution, and an assumed return, then tells you the
  required monthly contribution to hit each target — and whether your cash
  flow actually supports all goals combined.

## Architecture

```
finance-tracker/
├── backend/               FastAPI + plaid-python
│   ├── main.py            HTTP endpoints
│   ├── plaid_client.py    Plaid SDK wrapper (link, exchange, sync)
│   ├── storage.py         JSON-file storage (items, accounts, txns, goals)
│   ├── subscriptions.py   Recurring-charge detector
│   ├── networth.py        Asset/liability bucketing
│   ├── income.py          Income + spending summaries
│   ├── planning.py        Goal projections + feasibility
│   ├── models.py          Pydantic request/response models
│   └── data/              Local JSON cache (created on first run)
└── frontend/              React + Vite + Tailwind + react-plaid-link
    └── src/components/    Dashboard, Accounts, Subscriptions, Income, Goals
```

**Stack:** FastAPI, plaid-python, React, TypeScript, Tailwind CSS, Vite,
react-plaid-link, lucide-react.

## Setup

### 1. Get Plaid API keys

1. Sign up at [https://dashboard.plaid.com/signup](https://dashboard.plaid.com/signup)
   — a free **sandbox** account gives you test credentials and fake
   institutions so you can try the app end-to-end immediately.
2. In the dashboard, go to **Team Settings → Keys** and copy your
   `client_id` and `sandbox secret`.
3. Copy `backend/.env.example` to `backend/.env` and paste them in:

```bash
cp backend/.env.example backend/.env
$EDITOR backend/.env
```

Start in `PLAID_ENV=sandbox`. When you're ready to link real accounts,
request development/production access from Plaid (takes a day or two), then
change `PLAID_ENV` and swap the secret.

### 2. Run

```bash
./start.sh
```

This creates a Python venv, installs `requirements.txt`, installs frontend
`node_modules`, and boots both:

- Backend: http://localhost:8000  (docs at `/docs`)
- Frontend: http://localhost:5175

Click **Link an account** and authenticate. In sandbox the credentials are:

- Username: `user_good`
- Password: `pass_good`
- 2FA code (if prompted): `1234`

The app will fetch accounts, transactions, investments, and liabilities and
populate every panel.

## Linking specific brokerages

All of the institutions you asked about are supported by Plaid:

| Institution | Notes                                          |
| ----------- | ---------------------------------------------- |
| Robinhood   | OAuth flow inside Plaid Link                   |
| PNC Bank    | Standard bank credentials (+ 2FA)              |
| Vanguard    | OAuth — may require re-auth every ~90 days    |
| Fidelity    | OAuth                                          |
| Chase, Bank of America, Schwab, Coinbase, etc. | Search inside the Plaid Link modal |

Plaid periodically rotates OAuth sessions. When a link breaks the item row
will show an error banner — delete and re-link from the **Accounts** tab.

## Security notes

- Everything runs on `localhost`. There is no cloud component and no auth on
  the FastAPI backend — do **not** expose port 8000 to the network.
- Plaid access tokens grant read-only permission to the accounts you chose in
  the Link modal. They are stored in `backend/data/items.json` with 0600
  permissions. Delete that file (or use the **Unlink** button) to revoke.
- Transactions, balances, and goals are cached in `backend/data/*.json`.
  Those files are machine-local and gitignored.
- No AI/LLM calls are made by this tool.

## API reference (short version)

| Method | Path                    | Purpose                                        |
| ------ | ----------------------- | ---------------------------------------------- |
| GET    | `/status`               | Plaid config + link counts                     |
| POST   | `/link/token`           | Create a Plaid Link token for the frontend     |
| POST   | `/link/exchange`        | Exchange `public_token` → access token + sync  |
| GET    | `/items`                | Linked institutions                            |
| DELETE | `/items/{item_id}`      | Unlink & remove cached data                    |
| POST   | `/sync`                 | Refresh all items                              |
| POST   | `/sync/{item_id}`       | Refresh a single item                          |
| GET    | `/accounts`             | Cached accounts                                |
| GET    | `/transactions`         | Cached transactions (paginated)                |
| GET    | `/networth`             | Asset + liability breakdown                    |
| GET    | `/subscriptions`        | Detected recurring charges                     |
| GET    | `/income`               | Income summary (`?window_days=`)               |
| GET    | `/dashboard`            | Headline stats for the overview                |
| GET/POST/DELETE | `/goals[/{id}]` | Goal CRUD                                      |
| POST   | `/plan`                 | Goal projections + feasibility                 |

Open `http://localhost:8000/docs` for the full interactive schema.
