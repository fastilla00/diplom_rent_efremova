# EcomProfit Guard — Google OAuth and user profile
import json
import os
import tempfile
import time
from datetime import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from app.config import get_settings

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]
MONTH_NAMES_RU = (
    "янв", "февр", "март", "апр", "май", "июнь", "июль", "авг", "сент", "окт", "нояб", "дек"
)

# PKCE: сохраняем code_verifier на диск и в память (память — на случай того же процесса)
_OAUTH_CACHE_TTL = 600  # 10 мин
_flow_cache: dict[str, Flow] = {}


def _oauth_cache_path(state: str) -> str:
    import hashlib
    safe = hashlib.sha256(state.encode()).hexdigest()[:32]
    d = os.path.join(tempfile.gettempdir(), "ecomprofit_oauth")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{safe}.json")


def _get_code_verifier(flow: Flow) -> str | None:
    return getattr(flow, "code_verifier", None)


def auth_url(state: str) -> str:
    settings = get_settings()
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [settings.redirect_uri],
            }
        },
        scopes=SCOPES,
        redirect_uri=settings.redirect_uri,
    )
    url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        state=state,
        prompt="consent",
    )
    code_verifier = _get_code_verifier(flow)
    _flow_cache[state] = flow
    if code_verifier:
        try:
            path = _oauth_cache_path(state)
            with open(path, "w") as f:
                json.dump({"code_verifier": code_verifier, "created": time.time()}, f)
        except Exception:
            pass
    return url


def credentials_from_code(
    code: str, state: str | None = None
) -> tuple[Credentials, str | None, str | None, str | None]:
    if not state:
        raise ValueError("Invalid or expired state; try logging in again")
    flow = _flow_cache.pop(state, None)
    code_verifier = None
    if flow:
        code_verifier = _get_code_verifier(flow)
    if not code_verifier:
        path = _oauth_cache_path(state)
        try:
            with open(path) as f:
                data = json.load(f)
            os.remove(path)
        except (FileNotFoundError, json.JSONDecodeError):
            raise ValueError("Invalid or expired state; try logging in again")
        if time.time() - data.get("created", 0) > _OAUTH_CACHE_TTL:
            raise ValueError("Invalid or expired state; try logging in again")
        code_verifier = data.get("code_verifier")
    if not code_verifier:
        raise ValueError("Invalid or expired state; try logging in again")
    if flow:
        flow.fetch_token(code=code)
        creds = flow.credentials
    else:
        settings = get_settings()
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [settings.redirect_uri],
                }
            },
            scopes=SCOPES,
            redirect_uri=settings.redirect_uri,
        )
        flow.fetch_token(code=code, code_verifier=code_verifier)
        creds = flow.credentials
    email, name, google_id = get_user_info(creds)
    return creds, email, name, google_id


def get_user_info(creds: Credentials) -> tuple[str | None, str | None, str | None]:
    import httpx
    try:
        resp = httpx.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {creds.token}"},
            timeout=10,
        )
        if resp.status_code != 200:
            return None, None, None
        data = resp.json()
        return data.get("email"), data.get("name"), data.get("id")
    except Exception:
        return None, None, None


def credentials_for_user(access_token: str, refresh_token: str | None, expires_at: datetime | None) -> Credentials:
    settings = get_settings()
    return Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scopes=SCOPES,
    )
