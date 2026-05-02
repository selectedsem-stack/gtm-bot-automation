import sys
import io
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SCOPES = [
    "https://www.googleapis.com/auth/tagmanager.edit.containers",
    "https://www.googleapis.com/auth/tagmanager.readonly",
]


def main():
    creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    service = build("tagmanager", "v2", credentials=creds)

    response = service.accounts().list().execute()
    accounts = response.get("account", [])

    if not accounts:
        print("No accounts found.")
        return

    print(f"Found {len(accounts)} account(s):\n")
    for acc in accounts:
        print(f"  Account ID : {acc['accountId']}")
        print(f"  Name       : {acc['name']}")
        print(f"  Path       : {acc['path']}")
        print()


if __name__ == "__main__":
    main()
