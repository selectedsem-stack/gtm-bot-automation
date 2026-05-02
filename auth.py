import os
import json

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

SCOPES = [
    "https://www.googleapis.com/auth/tagmanager.edit.containers",
    "https://www.googleapis.com/auth/tagmanager.edit.containerversions",
    "https://www.googleapis.com/auth/tagmanager.publish",
    "https://www.googleapis.com/auth/tagmanager.readonly",
    "https://www.googleapis.com/auth/analytics.edit",
]


def _read_token_json() -> str | None:
    # Try Streamlit secrets first (works on Streamlit Cloud)
    try:
        import streamlit as st
        val = st.secrets.get("GOOGLE_TOKEN_JSON", "")
        if val:
            return val.strip().replace("\r", "").replace("\n", "")
    except Exception:
        pass
    # Fall back to environment variable (local dev / Railway)
    val = os.environ.get("GOOGLE_TOKEN_JSON", "")
    return val.strip().replace("\r", "").replace("\n", "") if val else None


def load_credentials() -> Credentials:
    token_json = _read_token_json()
    if token_json:
        creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
    elif os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    else:
        raise RuntimeError(
            "No Google credentials found. "
            "Set the GOOGLE_TOKEN_JSON environment variable or place token.json in the working directory."
        )
    # The stored access token is always expired on Streamlit Cloud — always refresh
    if creds.refresh_token:
        creds.refresh(Request())
    elif not creds.valid:
        raise RuntimeError("Token is invalid and cannot be refreshed. Re-authenticate locally and update GOOGLE_TOKEN_JSON.")
    return creds
