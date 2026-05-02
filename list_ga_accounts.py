import sys
import io
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.analytics.admin import AnalyticsAdminServiceClient
from google.analytics.admin_v1alpha.types import ListAccountsRequest

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SCOPES = [
    "https://www.googleapis.com/auth/tagmanager.edit.containers",
    "https://www.googleapis.com/auth/tagmanager.readonly",
    "https://www.googleapis.com/auth/analytics.edit",
]


def main():
    creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    client = AnalyticsAdminServiceClient(credentials=creds)

    accounts = list(client.list_accounts(ListAccountsRequest()))

    if not accounts:
        print("No GA4 accounts found.")
        return

    print(f"Found {len(accounts)} GA4 account(s):\n")
    for acc in accounts:
        account_id = acc.name.split("/")[-1]
        print(f"  Account ID : {account_id}")
        print(f"  Name       : {acc.display_name}")
        print()


if __name__ == "__main__":
    main()
