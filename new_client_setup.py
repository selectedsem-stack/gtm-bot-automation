import sys
import io
import os
import json
import copy
from datetime import date

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8", errors="replace")

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.analytics.admin import AnalyticsAdminServiceClient
from google.analytics.admin_v1alpha.types import (
    Property, DataStream, ListAccountsRequest
)

SCOPES = [
    "https://www.googleapis.com/auth/tagmanager.edit.containers",
    "https://www.googleapis.com/auth/tagmanager.edit.containerversions",
    "https://www.googleapis.com/auth/tagmanager.publish",
    "https://www.googleapis.com/auth/tagmanager.readonly",
    "https://www.googleapis.com/auth/analytics.edit",
]
CREDENTIALS_FILE = "oauth-credentials.json.json"
TOKEN_FILE = "token.json"
TEMPLATE_FILE = "gtm-template/template.json"

GTM_CLAUDE_AUTOMATION_ACCOUNT_ID = "6352015198"


def get_credentials():
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        stored_scopes = set(creds.scopes or [])
        missing = [s for s in SCOPES if s not in stored_scopes]
        if missing:
            print("  Re-authentication required — missing scope: tagmanager.publish")
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            print("  Opening browser for authorization...")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0, open_browser=True)
            with open(TOKEN_FILE, "w") as f:
                f.write(creds.to_json())
            print("  [OK] Token saved")

    return creds


def ask_yn(question):
    while True:
        ans = input(question + " ").strip().lower()
        if ans in ("yes", "no", "y", "n"):
            return ans in ("yes", "y")
        print("  --> Please enter yes/no (y/n)")


def ask_required(question):
    while True:
        ans = input(question + " ").strip()
        if ans:
            return ans
        print("  --> Required field, please enter a value")


def collect_client_info():
    print("\n" + "=" * 55)
    print("  STEP 1 -- Client Details")
    print("=" * 55 + "\n")

    info = {}
    info["client_name"] = ask_required("Client name:")
    domain = ask_required("Domain (without https):")
    domain = domain.replace("https://", "").replace("http://", "").rstrip("/")
    info["domain"] = domain
    info["ecommerce"] = ask_yn("Is this an eCommerce store? [yes/no]:")
    thankyou = ask_required("Contact form thank-you page URL (e.g. /thank-you/):")
    info["thankyou_url"] = thankyou.strip()
    info["google_ads"] = ask_yn("Add Google Ads tracking? [yes/no]:")
    if info["google_ads"]:
        info["ads_id"] = ask_required("Google Ads Conversion ID (AW-XXXXXXXXX):")
    info["facebook_pixel"] = ask_yn("Add Facebook Pixel? [yes/no]:")
    if info["facebook_pixel"]:
        info["pixel_id"] = ask_required("Facebook Pixel ID:")
    info["maskyoo"] = ask_yn("Add Maskyoo virtual number? [yes/no]:")
    if info["maskyoo"]:
        info["maskyoo_number"] = ask_required("Maskyoo number (e.g. 055-1234567):")

    print()
    return info


def pick_from_list(items, label_fn, section_title):
    print("\n" + "=" * 55)
    print(f"  {section_title}")
    print("=" * 55 + "\n")
    for i, item in enumerate(items, 1):
        print(f"  {i:4}. {label_fn(item)}")
    while True:
        raw = input(f"\n  Select number (1-{len(items)}): ").strip()
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(items):
                print(f"  --> Selected: {label_fn(items[idx])}")
                return items[idx]
        except ValueError:
            pass
        print("  --> Invalid number, try again")


def get_gtm_account_id():
    print(f"\n  GTM Account: Claude Automation  (ID: {GTM_CLAUDE_AUTOMATION_ACCOUNT_ID})")


def select_ga4_account(ga4_client):
    print("\n  Fetching GA4 accounts...")
    accounts = list(ga4_client.list_accounts(ListAccountsRequest()))
    if not accounts:
        raise RuntimeError("No GA4 accounts found.")
    return pick_from_list(
        accounts,
        lambda a: f"{a.display_name}  (ID: {a.name.split('/')[-1]})",
        "STEP 2b -- Select GA4 Account"
    )


def create_gtm_container(gtm_service, account_id, name):
    print(f"\n{'=' * 55}")
    print(f"  STEP 3 -- Creating GTM Container: {name}")
    print("=" * 55)

    container = gtm_service.accounts().containers().create(
        parent=f"accounts/{account_id}",
        body={"name": name, "usageContext": ["web"]}
    ).execute()

    gtm_id = container["publicId"]
    container_path = container["path"]
    print(f"  [OK] Created: {gtm_id}  |  path: {container_path}")
    return gtm_id, container_path


def create_ga4_property(ga4_client, account_id, name, domain):
    print(f"\n{'=' * 55}")
    print(f"  STEP 4 -- Creating GA4 Property: {name}")
    print("=" * 55)

    prop = ga4_client.create_property(
        property=Property(
            display_name=name,
            time_zone="Asia/Jerusalem",
            currency_code="ILS",
            parent=f"accounts/{account_id}",
        )
    )
    print(f"  [OK] Property: {prop.name}")

    stream = ga4_client.create_data_stream(
        parent=prop.name,
        data_stream=DataStream(
            web_stream_data=DataStream.WebStreamData(
                default_uri=f"https://{domain}",
            ),
            display_name=name,
            type_=DataStream.DataStreamType.WEB_DATA_STREAM,
        )
    )

    measurement_id = stream.web_stream_data.measurement_id
    stream_id = stream.name.split("/")[-1]
    print(f"  [OK] Measurement ID: {measurement_id}")
    print(f"  [OK] Stream ID:      {stream_id}")
    return measurement_id, stream_id


ECOMMERCE_KEYWORDS = ["ecommerce", "purchase", "add_to_cart", "begin_checkout", "view_item", "remove_from_cart"]

BUILTIN_TRIGGER_ALL_PAGES = "2147479553"

_STRIP_FIELDS = {"accountId", "containerId", "workspaceId", "parentFolderId",
                 "fingerprint", "tagManagerUrl", "path"}

# GTM export uses UPPER_CASE; API create expects camelCase
_BUILTIN_VAR_TYPE_MAP = {
    "PAGE_URL": "pageUrl",
    "PAGE_HOSTNAME": "pageHostname",
    "PAGE_PATH": "pagePath",
    "REFERRER": "referrer",
    "EVENT": "event",
    "CLICK_ELEMENT": "clickElement",
    "CLICK_CLASSES": "clickClasses",
    "CLICK_ID": "clickId",
    "CLICK_TARGET": "clickTarget",
    "CLICK_URL": "clickUrl",
    "CLICK_TEXT": "clickText",
    "FORM_ELEMENT": "formElement",
    "FORM_CLASSES": "formClasses",
    "FORM_ID": "formId",
    "FORM_TARGET": "formTarget",
    "FORM_URL": "formUrl",
    "FORM_TEXT": "formText",
    "RANDOM_NUMBER": "randomNumber",
    "CONTAINER_ID": "containerId",
    "CONTAINER_VERSION": "containerVersion",
    "DEBUG_MODE": "debugMode",
    "HTML_ID": "htmlId",
}

def _clean(entity, id_key):
    return {k: v for k, v in entity.items() if k not in _STRIP_FIELDS and k != id_key}

def _safe_name(name):
    """Remove characters GTM API rejects in names."""
    return name.replace(":", "").replace("  ", " ").strip()


def _filter_by_name(entities, keywords):
    kept, removed = [], []
    for e in entities:
        name = e.get("name", "").lower()
        if any(k in name for k in keywords):
            removed.append(e.get("name", ""))
        else:
            kept.append(e)
    return kept, removed


def process_template(info, measurement_id, stream_id):
    print(f"\n{'=' * 55}")
    print("  STEP 5 -- Processing GTM template")
    print("=" * 55)

    if not os.path.exists(TEMPLATE_FILE):
        raise FileNotFoundError(
            f"Template file not found: {TEMPLATE_FILE}\n"
            "Please create the file before running this script."
        )

    with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)

    version = copy.deepcopy(raw.get("containerVersion", raw))

    s = json.dumps(version, ensure_ascii=False)
    s = s.replace("PLACEHOLDER_GA4_ID", measurement_id)
    s = s.replace("PLACEHOLDER_STREAM_ID", stream_id)
    s = s.replace("PLACEHOLDER_DOMAIN", info["domain"])
    s = s.replace("PLACEHOLDER_THANKYOU_URL", info["thankyou_url"])

    if info.get("google_ads") and info.get("ads_id"):
        s = s.replace("PLACEHOLDER_ADS_ID", info["ads_id"])
    if info.get("facebook_pixel") and info.get("pixel_id"):
        s = s.replace("PLACEHOLDER_PIXEL_ID", info["pixel_id"])
    if info.get("maskyoo") and info.get("maskyoo_number"):
        s = s.replace("PLACEHOLDER_MASKYOO_NUMBER", info["maskyoo_number"])

    version = json.loads(s)

    tags = version.get("tag", [])
    triggers = version.get("trigger", [])
    variables = version.get("variable", [])
    removed_tags = []

    if not info.get("google_ads"):
        kept, removed = [], []
        for tag in tags:
            if "PLACEHOLDER_ADS_ID" in json.dumps(tag):
                removed.append(tag.get("name", ""))
            else:
                kept.append(tag)
        tags, removed_tags = kept, removed_tags + removed

    if not info.get("facebook_pixel"):
        kept, removed = [], []
        for tag in tags:
            if "PLACEHOLDER_PIXEL_ID" in json.dumps(tag):
                removed.append(tag.get("name", ""))
            else:
                kept.append(tag)
        tags, removed_tags = kept, removed_tags + removed

    if not info.get("maskyoo"):
        kept, removed = [], []
        for tag in tags:
            if "PLACEHOLDER_MASKYOO_NUMBER" in json.dumps(tag):
                removed.append(tag.get("name", ""))
            else:
                kept.append(tag)
        tags, removed_tags = kept, removed_tags + removed

    if not info.get("ecommerce"):
        tags, removed_ec = _filter_by_name(tags, ECOMMERCE_KEYWORDS)
        removed_tags += removed_ec
        triggers, _ = _filter_by_name(triggers, ECOMMERCE_KEYWORDS)
        variables, _ = _filter_by_name(variables, ECOMMERCE_KEYWORDS)

    version["tag"] = tags
    version["trigger"] = triggers
    version["variable"] = variables

    kept_names = [t.get("name", "") for t in tags]
    print(f"  Tags imported  ({len(kept_names)}): {', '.join(kept_names)}")
    if removed_tags:
        print(f"  Tags skipped   ({len(removed_tags)}): {', '.join(removed_tags)}")

    return version, kept_names, removed_tags


def import_and_publish(gtm_service, container_path, version, description):
    ws_resp = gtm_service.accounts().containers().workspaces().list(
        parent=container_path
    ).execute()
    workspaces = ws_resp.get("workspace", [])
    if not workspaces:
        raise RuntimeError("No workspace found in the new container.")

    workspace_path = workspaces[0]["path"]
    print(f"\n  Workspace: {workspaces[0].get('name', workspace_path)}")

    # Enable built-in variables (Click vars needed for phone/WA triggers)
    builtin_vars = version.get("builtInVariable", [])
    if builtin_vars:
        types = [_BUILTIN_VAR_TYPE_MAP.get(bv["type"], bv["type"]) for bv in builtin_vars]
        print(f"  Enabling {len(types)} built-in variable(s)...")
        try:
            gtm_service.accounts().containers().workspaces().built_in_variables().create(
                parent=workspace_path,
                type=types
            ).execute()
            print("  [OK] Built-in variables enabled")
        except Exception as e:
            print(f"  [WARN] Built-in variables: {e}")

    # Create triggers — map old template IDs to new API-assigned IDs
    trigger_id_map = {}
    triggers = version.get("trigger", [])
    print(f"  Creating {len(triggers)} trigger(s)...")
    for trigger in triggers:
        old_id = trigger.get("triggerId")
        body = _clean(trigger, "triggerId")
        body["name"] = _safe_name(body.get("name", ""))
        try:
            result = gtm_service.accounts().containers().workspaces().triggers().create(
                parent=workspace_path,
                body=body
            ).execute()
            new_id = result.get("triggerId")
            if old_id:
                trigger_id_map[old_id] = new_id
            print(f"    [OK] {body['name']}  ({old_id} -> {new_id})")
        except Exception as e:
            print(f"    [ERROR] Trigger '{body.get('name')}': {e}")
            raise

    # Create user-defined variables
    variables = version.get("variable", [])
    print(f"  Creating {len(variables)} variable(s)...")
    for variable in variables:
        vname = variable.get("name", "")
        try:
            gtm_service.accounts().containers().workspaces().variables().create(
                parent=workspace_path,
                body=_clean(variable, "variableId")
            ).execute()
            print(f"    [OK] {vname}")
        except Exception as e:
            print(f"    [ERROR] Variable '{vname}': {e}")
            raise

    # Create tags — remap firingTriggerId to new IDs
    tags = version.get("tag", [])
    print(f"  Creating {len(tags)} tag(s)...")
    for tag in tags:
        tname = tag.get("name", "")
        new_firing_ids = []
        for fid in tag.get("firingTriggerId", []):
            if fid == BUILTIN_TRIGGER_ALL_PAGES:
                new_firing_ids.append(fid)
            elif fid in trigger_id_map:
                new_firing_ids.append(trigger_id_map[fid])
            else:
                print(f"    [WARN] Unknown trigger ID '{fid}' for tag '{tname}' — tag may not fire")

        body = _clean(tag, "tagId")
        body["firingTriggerId"] = new_firing_ids

        # GTM export uses "id" for googtag; API create requires "tagId"
        if body.get("type") == "googtag":
            for param in body.get("parameter", []):
                if param.get("key") == "id":
                    param["key"] = "tagId"

        try:
            gtm_service.accounts().containers().workspaces().tags().create(
                parent=workspace_path,
                body=body
            ).execute()
            print(f"    [OK] {tname}")
        except Exception as e:
            print(f"    [ERROR] Tag '{tname}': {e}")
            raise

    # Create version and publish
    print(f"  Creating version: {description}")
    ver_resp = gtm_service.accounts().containers().workspaces().create_version(
        path=workspace_path,
        body={"name": description, "notes": description}
    ).execute()

    version_path = ver_resp.get("containerVersion", {}).get("path")
    if not version_path:
        raise RuntimeError("Could not retrieve version path for publishing.")

    print("  Publishing version...")
    gtm_service.accounts().containers().versions().publish(
        path=version_path
    ).execute()
    print("  [OK] Published successfully")


def print_final_output(info, gtm_id, measurement_id, stream_id, kept_tags, removed_tags):
    sep = "=" * 60

    print(f"\n{sep}")
    print("  [OK]  Client setup completed successfully")
    print(sep)
    print(f"\n  [OK] GTM Container:       {gtm_id}")
    print(f"  [OK] GA4 Measurement ID:  {measurement_id}")
    print(f"  [OK] GA4 Stream ID:       {stream_id}  (for reference)")
    print(f"\n  [OK] Tags imported ({len(kept_tags)}):")
    for name in kept_tags:
        print(f"       - {name}")
    if removed_tags:
        print(f"\n  [OK] Tags skipped ({len(removed_tags)}):")
        for name in removed_tags:
            print(f"       - {name}")

    print(f"\n{sep}")
    print("  === HEAD code -- paste above </head> ===")
    print(sep)
    print(f"""
<!-- Google Tag Manager -->
<script>(function(w,d,s,l,i){{w[l]=w[l]||[];w[l].push({{'gtm.start':
new Date().getTime(),event:'gtm.js'}});var f=d.getElementsByTagName(s)[0],
j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
}})(window,document,'script','dataLayer','{gtm_id}');</script>
<!-- End Google Tag Manager -->

<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id={measurement_id}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', '{measurement_id}');
</script>""")

    print(f"\n{sep}")
    print("  === BODY code -- paste after <body> ===")
    print(sep)
    print(f"""
<!-- Google Tag Manager (noscript) -->
<noscript><iframe src="https://www.googletagmanager.com/ns.html?id={gtm_id}"
height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>
<!-- End Google Tag Manager (noscript) -->
""")


def main():
    print("\n" + "=" * 55)
    print("  GTM + GA4 -- New Client Setup")
    print("=" * 55)

    info = collect_client_info()

    print("\n  Connecting to APIs...")
    creds = get_credentials()
    gtm_service = build("tagmanager", "v2", credentials=creds)
    ga4_client = AnalyticsAdminServiceClient(credentials=creds)
    print("  [OK] Connected")

    get_gtm_account_id()
    ga4_account = select_ga4_account(ga4_client)

    gtm_account_id = GTM_CLAUDE_AUTOMATION_ACCOUNT_ID
    ga4_account_id = ga4_account.name.split("/")[-1]

    gtm_id, container_path = create_gtm_container(
        gtm_service, gtm_account_id, info["domain"]
    )

    measurement_id, stream_id = create_ga4_property(
        ga4_client, ga4_account_id, info["client_name"], info["domain"]
    )

    version, kept_tags, removed_tags = process_template(info, measurement_id, stream_id)

    today_str = date.today().strftime("%d/%m/%Y")
    description = f"Initial setup - {info['client_name']} - {today_str}"
    import_and_publish(gtm_service, container_path, version, description)

    print_final_output(info, gtm_id, measurement_id, stream_id, kept_tags, removed_tags)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  [!] Stopped by user.")
        sys.exit(0)
    except FileNotFoundError as e:
        print(f"\n  [ERROR] File not found: {e}")
        sys.exit(1)
    except RuntimeError as e:
        print(f"\n  [ERROR] {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n  [ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
