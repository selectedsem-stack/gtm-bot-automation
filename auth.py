import os
import json

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

SCOPES = [
    "https://www.googleapis.com/auth/tagmanager.edit.containers",
    "https://www.googleapis.com/auth/tagmanager.publish",
    "https://www.googleapis.com/auth/tagmanager.readonly",
    "https://www.googleapis.com/auth/analytics.edit",
]


def load_credentials() -> Credentials:
    token_json = os.environ.get("GOOGLE_TOKEN_JSON")
    if token_json:
        creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
    elif os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    else:
        raise RuntimeError(
            "No Google credentials found. "
            "Set the GOOGLE_TOKEN_JSON environment variable or place token.json in the working directory."
        )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return creds
