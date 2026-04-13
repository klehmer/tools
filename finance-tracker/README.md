# Finance Tracker

Local-first personal finance dashboard. Aggregate accounts from **Plaid**
(12,000+ institutions), **SimpleFIN Bridge** (for banks that don't support
Plaid), or **manual entry** with CSV import — then see consolidated net worth,
spending breakdowns, income analysis, and goal-based financial plans, all
running on your own machine.

## Features

- **Multi-source aggregation.** Link accounts via Plaid, SimpleFIN, or add
  them manually. Each source syncs independently and all data is merged into
  a single view.
- **Net worth** with asset/liability breakdown (Cash, Investments, Retirement,
  Crypto, Credit Cards, Student Loans, Mortgages, …).
- **Dynamic spending categories.** User-defined categories (default:
  subscription, bill, work expense, food, vacation & recreation, other) with
  full CRUD — create, rename, reorder, and delete from the UI. Each merchant
  can be assigned to any category.
- **Frequency-based cost projections.** Set per-merchant frequencies (one-time,
  weekly, biweekly, monthly, quarterly, annual) on categories that enable
  frequency tracking. The dashboard and spending panel project monthly,
  quarterly, and annual equivalents.
- **Subscription & bill detection.** A recurring-charge detector groups
  transactions by normalized merchant, checks amount stability and cadence,
  and classifies as subscription or bill.
- **Income analysis** over configurable 30–365 day windows using Plaid's
  Payroll/Deposit categories plus payroll-keyword heuristics. Shows individual
  deposits per income source.
- **Account ignore.** Mark any account as ignored to exclude it from all
  analytics while keeping it visible and synced. Transfers to ignored accounts
  are counted as spending (counterpart-based detection), so shared bill-pay
  accounts work correctly.
- **Dashboard** with net worth, income, spending, and cash flow projections
  (monthly/quarterly/annual) plus per-category spending breakdowns.
- **Goals & financial plan.** Add goals (savings, debt payoff, retirement,
  major purchase). The planner projects where you'll land given your current
  balance, monthly contribution, and an assumed return, then tells you the
  required monthly contribution and whether your cash flow supports all goals.
- **Manual accounts & CSV import.** Add accounts by hand and bulk-import
  transactions from CSV files with auto-detected column mapping.
- **Transaction deduplication.** SimpleFIN can surface the same ACH across
  multiple sub-accounts — deduped by (date, amount, normalized name).

## Architecture

```
finance-tracker/
├── backend/               FastAPI + plaid-python + SimpleFIN client
│   ├── main.py            HTTP endpoints
│   ├── storage.py         JSON-file CRUD (sources, accounts, txns, goals, categories)
│   ├── income.py          Income + spending analytics, transfer detection
│   ├── subscriptions.py   Recurring-charge detector
│   ├── networth.py        Asset/liability bucketing
│   ├── planning.py        Goal projections + feasibility
│   ├── models.py          Pydantic request/response models
│   ├── plaid_client.py    Plaid SDK wrapper
│   ├── simplefin_client.py SimpleFIN Bridge client (90-day history cap)
│   ├── manual.py          Manual account creation + CSV import
│   └── data/              Local JSON cache (created on first run, gitignored)
└── frontend/              React + Vite + Tailwind + TypeScript
    └── src/
        ├── App.tsx        Tab navigation (Dashboard, Accounts, Spending, Income, Goals)
        ├── components/    Dashboard, Accounts, Spending, Income, Goals panels
        ├── services/      Typed API client
        └── types/         Shared TypeScript interfaces
```

**Stack:** FastAPI, plaid-python, React, TypeScript, Tailwind CSS, Vite,
react-plaid-link, lucide-react.

## Setup

### 1. Configure account sources

You can use any combination of Plaid, SimpleFIN, and manual accounts.

**Plaid** (optional):
1. Sign up at [https://dashboard.plaid.com/signup](https://dashboard.plaid.com/signup).
   A free sandbox account gives you test credentials immediately.
2. Copy your `client_id` and secret, then configure via the app's settings UI
   or `backend/.env`.
3. Start in sandbox. For real accounts, request development/production access
   from Plaid.

**SimpleFIN** (optional):
1. Get a setup token from [https://bridge.simplefin.org](https://bridge.simplefin.org).
2. Claim it via the app's "Add source" → SimpleFIN flow.
3. Note: SimpleFIN has a 90-day transaction history cap.

**Manual** (optional):
- Add accounts by hand via "Add source" → Manual.
- Import transactions from CSV files.

### 2. Run

```bash
./start.sh
```

This creates a Python venv, installs `requirements.txt`, installs frontend
`node_modules`, and boots both:

- Backend: http://localhost:8000  (docs at `/docs`)
- Frontend: http://localhost:5175

### Plaid sandbox credentials

In sandbox mode, use:
- Username: `user_good`
- Password: `pass_good`
- 2FA code (if prompted): `1234`

## Security notes

- Everything runs on `localhost`. There is no cloud component and no auth on
  the FastAPI backend — do **not** expose port 8000 to the network.
- Plaid access tokens and SimpleFIN credentials are stored in
  `backend/data/sources.json`. Delete that file (or use the **Remove** button)
  to revoke.
- Transactions, balances, categories, and goals are cached in
  `backend/data/*.json`. Those files are machine-local and gitignored.
- No AI/LLM calls are made by this tool.

## API reference (short version)

| Method | Path | Purpose |
| ------ | ---- | ------- |
| GET | `/status` | Config + source/account counts |
| POST | `/link/token` | Create a Plaid Link token |
| POST | `/link/exchange` | Exchange public_token → access token + sync |
| POST | `/sources/simplefin/claim` | Claim a SimpleFIN setup token |
| POST | `/accounts/manual` | Create a manual account |
| GET | `/sources` | Linked sources |
| DELETE | `/sources/{id}` | Remove source + cached data |
| POST | `/sync` | Refresh all sources |
| POST | `/sync/{id}` | Refresh a single source |
| GET | `/accounts` | All accounts |
| PATCH | `/accounts/{id}/ignore` | Toggle account ignore flag |
| PATCH | `/accounts/{id}/balance` | Update manual account balance |
| POST | `/accounts/{id}/csv` | Import CSV transactions |
| DELETE | `/accounts/{id}` | Delete manual account |
| GET | `/transactions` | Transactions (paginated) |
| GET | `/networth` | Asset + liability breakdown |
| GET | `/subscriptions` | Detected recurring charges |
| GET | `/income` | Income summary (`?window_days=`) |
| GET | `/spending` | Spending breakdown (`?window_days=`) |
| PUT | `/spending/categorize` | Assign merchant to category |
| PUT | `/spending/frequency` | Set merchant frequency |
| GET/POST/PUT/DELETE | `/spending/categories[/{key}]` | Category CRUD |
| GET | `/dashboard` | Net worth, income, spending, cash flow projections |
| GET/POST/DELETE | `/goals[/{id}]` | Goal CRUD |
| POST | `/plan` | Goal projections + feasibility |

Open `http://localhost:8000/docs` for the full interactive schema.
