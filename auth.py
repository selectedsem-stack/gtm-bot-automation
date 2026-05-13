import os
import json

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError

SCOPES = [
    "https://www.googleapis.com/auth/tagmanager.edit.containers",
    "https://www.googleapis.com/auth/tagmanager.edit.containerversions",
    "https://www.googleapis.com/auth/tagmanager.publish",
    "https://www.googleapis.com/auth/tagmanager.readonly",
    "https://www.googleapis.com/auth/analytics.edit",
]


class NeedsReauthError(RuntimeError):
    """Refresh token is missing, expired, or revoked — user must re-authorize."""


def _read_token_json() -> str | None:
    try:
        import streamlit as st
        val = st.secrets.get("GOOGLE_TOKEN_JSON", "")
        if val:
            return val.strip().replace("\r", "").replace("\n", "")
    except Exception:
        pass
    val = os.environ.get("GOOGLE_TOKEN_JSON", "")
    return val.strip().replace("\r", "").replace("\n", "") if val else None


def load_credentials() -> Credentials:
    token_json = _read_token_json()
    if token_json:
        try:
            info = json.loads(token_json)
        except json.JSONDecodeError as e:
            raise NeedsReauthError(
                f"ה-secret של GOOGLE_TOKEN_JSON לא JSON תקין ({e.msg}). דרושה הרשאה מחדש."
            ) from e
        if not isinstance(info, dict) or "refresh_token" not in info:
            raise NeedsReauthError(
                "ה-secret של GOOGLE_TOKEN_JSON חסר refresh_token (נראה שהדבקת רק access token, לא את ה-JSON המלא). דרושה הרשאה מחדש."
            )
        creds = Credentials.from_authorized_user_info(info, SCOPES)
    elif os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    else:
        raise NeedsReauthError("No Google credentials found — initial authorization required.")

    if not creds.refresh_token:
        raise NeedsReauthError("Stored credentials have no refresh token — re-authorization required.")

    try:
        creds.refresh(Request())
    except RefreshError as e:
        raise NeedsReauthError(f"Refresh token rejected by Google: {e}") from e

    return creds
