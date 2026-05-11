"""Web-based OAuth flow for Streamlit.

Loads a Web Application OAuth client (from `oauth-web-credentials.json` or the
`OAUTH_WEB_CLIENT_JSON` secret) and runs the standard authorization-code flow
with redirect back to the running Streamlit app.

Use:
    flow = build_flow()
    auth_url, state = start_auth(flow)
    # user is redirected; Streamlit re-runs with ?code=...&state=...
    creds = finish_auth(flow, expected_state, code)
"""

from __future__ import annotations

import json
import os
import secrets
from typing import Tuple

from google_auth_oauthlib.flow import Flow

from auth import SCOPES

WEB_CREDENTIALS_FILE = "oauth-web-credentials.json"


def _read_web_client_config() -> dict:
    """Load Web OAuth client config. Accepts (in priority order):

    1. Streamlit secrets `[oauth_web_client]` TOML section (preferred on Streamlit Cloud)
    2. Streamlit secrets `OAUTH_WEB_CLIENT_JSON` JSON string (legacy)
    3. Env var `OAUTH_WEB_CLIENT_JSON` JSON string
    4. `oauth-web-credentials.json` file in working dir
    """
    try:
        import streamlit as st
        if "oauth_web_client" in st.secrets:
            section = st.secrets["oauth_web_client"]
            web = {k: list(v) if isinstance(v, (list, tuple)) else v
                   for k, v in dict(section).items()}
            return {"web": web}
        val = st.secrets.get("OAUTH_WEB_CLIENT_JSON", "")
        if val:
            return json.loads(val)
    except Exception:
        pass
    val = os.environ.get("OAUTH_WEB_CLIENT_JSON", "")
    if val:
        return json.loads(val)
    if os.path.exists(WEB_CREDENTIALS_FILE):
        with open(WEB_CREDENTIALS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    raise RuntimeError(
        "Web OAuth client config not found. Add a [oauth_web_client] section to "
        f"Streamlit Secrets, or place {WEB_CREDENTIALS_FILE} in the working directory."
    )


def detect_redirect_uri() -> str:
    """Return the redirect URI for the current environment.

    Order of preference:
      1. OAUTH_REDIRECT_URI explicit override (Streamlit Cloud: set in Secrets)
      2. http://localhost:8501/ (Streamlit dev default)

    On Streamlit Community Cloud, you MUST set OAUTH_REDIRECT_URI in Secrets
    to the deployed app URL (e.g. https://<slug>.streamlit.app/) and add the
    same value to the Web OAuth client's Authorized redirect URIs in Google
    Cloud Console.
    """
    try:
        import streamlit as st
        override = (st.secrets.get("OAUTH_REDIRECT_URI", "") or "").strip()
        if override:
            return override
    except Exception:
        pass
    override = os.environ.get("OAUTH_REDIRECT_URI", "").strip()
    if override:
        return override
    return "http://localhost:8501/"


def build_flow(redirect_uri: str | None = None) -> Flow:
    config = _read_web_client_config()
    flow = Flow.from_client_config(config, scopes=SCOPES)
    flow.redirect_uri = redirect_uri or detect_redirect_uri()
    return flow


def start_auth(flow: Flow) -> Tuple[str, str, str | None]:
    """Generate auth URL. Returns (auth_url, state, code_verifier).

    The code_verifier MUST be persisted across the redirect — Google's PKCE
    requires it to be presented when exchanging the auth code for tokens.
    """
    state = secrets.token_urlsafe(24)
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state,
    )
    code_verifier = getattr(flow, "code_verifier", None)
    return auth_url, state, code_verifier


def finish_auth(
    flow: Flow,
    expected_state: str,
    received_state: str,
    code: str,
    code_verifier: str | None = None,
):
    if not expected_state or expected_state != received_state:
        raise RuntimeError("OAuth state mismatch — possible CSRF attempt. Please try again.")
    if code_verifier:
        flow.code_verifier = code_verifier
    flow.fetch_token(code=code)
    return flow.credentials


def credentials_to_json(creds) -> str:
    """Serialize credentials in the same shape as InstalledAppFlow's token.json."""
    return creds.to_json()
