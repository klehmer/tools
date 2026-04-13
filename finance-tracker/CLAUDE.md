# Finance Tracker - Development Guide

## Architecture

FastAPI backend + React/Vite/Tailwind/TypeScript frontend. JSON-file storage (no database). All data lives in `backend/data/` (gitignored).

### Backend (`backend/`)

- **main.py** — FastAPI app with all HTTP endpoints
- **storage.py** — JSON file CRUD for sources, accounts, transactions, goals, category/frequency rules, spending categories
- **income.py** — Income detection (payroll keywords + Plaid categories), spending breakdown with dynamic categories, counterpart-based transfer detection
- **subscriptions.py** — Recurring charge detection, subscription vs bill classification
- **networth.py** — Asset/liability bucketing from account balances
- **planning.py** — Goal projections and feasibility ratings
- **models.py** — Pydantic request/response models
- **plaid_client.py** — Plaid SDK wrapper
- **simplefin_client.py** — SimpleFIN Bridge client (90-day history cap)
- **manual.py** — Manual account creation + CSV import

### Frontend (`frontend/src/`)

- **App.tsx** — Tab navigation (Dashboard, Accounts, Spending, Income, Goals)
- **components/DashboardPanel.tsx** — Net worth, income, spending, cash flow projections with per-category breakdowns
- **components/AccountsPanel.tsx** — Source/account management with ignore toggle
- **components/SpendingPanel.tsx** — Dynamic category buckets, category manager, frequency selectors, per-merchant categorization
- **components/IncomePanel.tsx** — Income sources with individual deposit history
- **services/api.ts** — Typed API client
- **types/index.ts** — All shared TypeScript interfaces

## Key Concepts

### Multi-source aggregation
Three source kinds: `plaid`, `simplefin`, `manual`. Each source has accounts and transactions. SimpleFIN uses inflow-positive sign convention (normalized to Plaid's outflow-positive on import). SimpleFIN has a 90-day history cap.

### Account ignore
Accounts can be marked `ignored` to exclude from all analytics while remaining visible and synced. Transfer detection uses counterpart matching: transfers to ignored accounts count as spending (no matching inflow in active accounts), while transfers between active accounts are correctly filtered.

### Dynamic spending categories
Categories are user-defined and stored in `spending_categories.json`. Default categories: subscription, bill, work_expense, food, vacation, other. Users can create/rename/delete categories. Each category can optionally enable frequency tracking (weekly through annual) for cost projections.

### Transfer detection
Uses counterpart matching instead of keyword-only filtering. An outflow is only filtered as an internal transfer if a matching inflow (same amount, ±1 day) exists in a different active account. This prevents double-counting while correctly treating transfers to ignored accounts as spending.

### Transaction deduplication
SimpleFIN can report the same ACH on multiple sub-accounts. Dedup key: `(date, amount, normalized_name)`.

## Running

```bash
./start.sh  # Backend on :8000, frontend on :5175
```

## Common tasks

- **Add a new spending category**: POST `/spending/categories` or use the "Manage categories" UI
- **Categorize a merchant**: PUT `/spending/categorize` with merchant_name + category key
- **Set frequency**: PUT `/spending/frequency` with merchant_name + frequency
- **Ignore an account**: PATCH `/accounts/{id}/ignore` with `{"ignored": true}`

## Testing

```bash
cd frontend && npx tsc --noEmit  # TypeScript check
cd backend && python3 -c "import ast; ast.parse(open('main.py').read())"  # Syntax check
```

No test suite currently — verify manually via the UI and `http://localhost:8000/docs`.
