import json
import os
import uuid
from pathlib import Path
from typing import Optional

os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow

_DATA_DIR = Path(__file__).parent / "data"
_DATA_DIR.mkdir(exist_ok=True)
_FLOWS_FILE = _DATA_DIR / "ces_pending_flows.json"
_SESSIONS_FILE = _DATA_DIR / "ces_sessions.json"


def _load_sessions() -> dict[str, Credentials]:
    try:
        if _SESSIONS_FILE.exists():
            raw = json.loads(_SESSIONS_FILE.read_text())
            return {
                tok: Credentials.from_authorized_user_info(info, scopes=info.get("scopes"))
                for tok, info in raw.items()
            }
    except Exception:
        pass
    return {}


def _save_sessions() -> None:
    try:
        data = {tok: json.loads(creds.to_json()) for tok, creds in _sessions.items()}
        _SESSIONS_FILE.write_text(json.dumps(data))
    except Exception:
        pass


_sessions: dict[str, Credentials] = {}
_sessions.update(_load_sessions())

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]


def _get_redirect_uri() -> str:
    return os.getenv("BACKEND_URL", "http://localhost:8001") + "/auth/callback"


def _build_flow() -> Flow:
    client_config = {
        "web": {
            "client_id": os.getenv("GOOGLE_CLIENT_ID"),
            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [_get_redirect_uri()],
        }
    }
    return Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=_get_redirect_uri(),
    )


def _save_verifier(state: str, code_verifier: Optional[str]) -> None:
    try:
        data = _load_verifiers()
        data[state] = code_verifier
        _FLOWS_FILE.write_text(json.dumps(data))
    except Exception:
        pass


def _pop_verifier(state: str) -> Optional[str]:
    try:
        data = _load_verifiers()
        verifier = data.pop(state, None)
        _FLOWS_FILE.write_text(json.dumps(data))
        return verifier
    except Exception:
        return None


def _load_verifiers() -> dict:
    try:
        if _FLOWS_FILE.exists():
            return json.loads(_FLOWS_FILE.read_text())
    except Exception:
        pass
    return {}


def get_auth_url() -> str:
    flow = _build_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent",
    )
    _save_verifier(state, flow.code_verifier)
    return auth_url


def exchange_code(code: str, state: str) -> str:
    flow = _build_flow()
    code_verifier = _pop_verifier(state)
    fetch_kwargs: dict = {"code": code}
    if code_verifier:
        fetch_kwargs["code_verifier"] = code_verifier
    flow.fetch_token(**fetch_kwargs)
    credentials = flow.credentials
    session_token = str(uuid.uuid4())
    _sessions[session_token] = credentials
    _save_sessions()
    return session_token


def get_credentials(session_token: str) -> Optional[Credentials]:
    creds = _sessions.get(session_token)
    if creds is None:
        return None
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _sessions[session_token] = creds
            _save_sessions()
        except Exception:
            del _sessions[session_token]
            _save_sessions()
            return None
    return creds


def delete_session(session_token: str) -> None:
    _sessions.pop(session_token, None)
    _save_sessions()
