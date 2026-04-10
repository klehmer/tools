# Calendar & Email Summary

AI-powered summaries of your Gmail inbox and Google Calendar over any time period.
Modeled on the `gmail-manager` app — same OAuth flow, FastAPI backend, React/Vite/Tailwind frontend.

## Features
- Summarize emails from the previous day / week / month / quarter
- Highlight important emails (action-required, personal, time-sensitive)
- Summarize past or upcoming calendar events
- Identify themes and action items via Claude

## Setup

### Google Cloud
1. Create an OAuth 2.0 Web client in Google Cloud Console
2. Enable the **Gmail API** and **Google Calendar API**
3. Add redirect URI: `http://localhost:8001/auth/callback`
4. Copy the client ID and secret

### Backend (port 8001)
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # then fill in your keys
uvicorn main:app --reload --port 8001
```

### Frontend (port 5174)
```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5174, enter your credentials in Settings (or directly in `.env`),
sign in with Google, then pick a mode (Emails or Calendar), a time period, and click
**Generate Summary**.

## Architecture
- **backend/auth.py** — Google OAuth 2.0 + session management
- **backend/google_service.py** — Gmail + Calendar read-only API client
- **backend/summarizer.py** — Claude (`claude-haiku-4-5`) summarization
- **backend/main.py** — FastAPI routes
- **frontend/src/** — React + Vite + Tailwind UI
