"""
GTM API Diagnostic — tests trigger + each tag type individually.
Run against the most recent demo container.
"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

TOKEN_FILE        = "token.json"
GTM_ACCOUNT_ID    = "6352015198"
SCOPES = [
    "https://www.googleapis.com/auth/tagmanager.edit.containers",
    "https://www.googleapis.com/auth/tagmanager.publish",
    "https://www.googleapis.com/auth/tagmanager.readonly",
]

# ── auth ──────────────────────────────────────────────────────────────────────
creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
if creds.expired and creds.refresh_token:
    creds.refresh(Request())
svc = build("tagmanager", "v2", credentials=creds)

# ── pick container ─────────────────────────────────────────────────────────────
print("\n=== Containers in Claude Automation ===")
containers = svc.accounts().containers().list(
    parent=f"accounts/{GTM_ACCOUNT_ID}"
).execute().get("container", [])

for i, c in enumerate(containers):
    print(f"  {i+1}. {c['name']}  ({c['publicId']})  path={c['path']}")

idx = int(input("\nSelect container number to test: ").strip()) - 1
container_path = containers[idx]["path"]
print(f"  --> Using: {containers[idx]['name']}")

# ── pick workspace ─────────────────────────────────────────────────────────────
workspaces = svc.accounts().containers().workspaces().list(
    parent=container_path
).execute().get("workspace", [])
ws_path = workspaces[0]["path"]
print(f"  Workspace: {workspaces[0].get('name')}  path={ws_path}\n")

ALL_PAGES = "2147479553"
results   = {}

def try_create(label, resource_fn, body):
    print(f"--- {label} ---")
    print(f"  BODY: {json.dumps(body, ensure_ascii=False)}")
    try:
        r = resource_fn().create(parent=ws_path, body=body).execute()
        tid = r.get("tagId") or r.get("triggerId") or r.get("variableId") or "?"
        print(f"  [OK]  ID={tid}\n")
        results[label] = ("OK", tid)
        return r
    except Exception as e:
        print(f"  [FAIL] {e}\n")
        results[label] = ("FAIL", str(e))
        return None

tags_res  = lambda: svc.accounts().containers().workspaces().tags()
trigs_res = lambda: svc.accounts().containers().workspaces().triggers()

# ── Test 1: create a trigger (Page View - some pages) ─────────────────────────
trig_result = try_create(
    "Trigger: Page View (Thank You)",
    trigs_res,
    {
        "name": "DIAG - Thank You Page",
        "type": "PAGEVIEW",
        "filter": [{
            "type": "CONTAINS",
            "parameter": [
                {"type": "template", "key": "arg0", "value": "{{Page URL}}"},
                {"type": "template", "key": "arg1", "value": "/thank-you/"}
            ]
        }]
    }
)
thank_you_id = trig_result.get("triggerId") if trig_result else ALL_PAGES

# ── Test 2: Conversion Linker (gclidw) ────────────────────────────────────────
try_create(
    "Tag: Conversion Linker (gclidw)",
    tags_res,
    {
        "name": "DIAG - Conversion Linker",
        "type": "gclidw",
        "parameter": [
            {"type": "boolean", "key": "enableCrossDomainFeature", "value": "false"}
        ],
        "firingTriggerId": [ALL_PAGES]
    }
)

# ── Test 3: Google Tag / googtag — with "tagId" key ───────────────────────────
try_create(
    "Tag: Google Tag googtag (key=tagId)",
    tags_res,
    {
        "name": "DIAG - GA4 Config (tagId key)",
        "type": "googtag",
        "parameter": [
            {"type": "template", "key": "tagId", "value": "G-TESTDIAG01"}
        ],
        "firingTriggerId": [ALL_PAGES]
    }
)

# ── Test 4: Google Tag — with "id" key (original export format) ───────────────
try_create(
    "Tag: Google Tag googtag (key=id)",
    tags_res,
    {
        "name": "DIAG - GA4 Config (id key)",
        "type": "googtag",
        "parameter": [
            {"type": "template", "key": "id", "value": "G-TESTDIAG02"}
        ],
        "firingTriggerId": [ALL_PAGES]
    }
)

# ── Test 5: GA4 Event (gaawe) — no measurementId ─────────────────────────────
try_create(
    "Tag: GA4 Event gaawe (no measurementId)",
    tags_res,
    {
        "name": "DIAG - GA4 Event page_view (bare)",
        "type": "gaawe",
        "parameter": [
            {"type": "template", "key": "eventName", "value": "page_view"},
            {"type": "boolean",  "key": "sendEcommerceData", "value": "false"}
        ],
        "firingTriggerId": [ALL_PAGES]
    }
)

# ── Test 6: GA4 Event with contact_form_submission + event parameters ─────────
try_create(
    "Tag: GA4 Event gaawe (with eventParameters list)",
    tags_res,
    {
        "name": "DIAG - GA4 Event contact_form",
        "type": "gaawe",
        "parameter": [
            {"type": "template", "key": "eventName", "value": "contact_form_submission"},
            {
                "type": "list",
                "key": "eventParameters",
                "list": [{
                    "type": "map",
                    "map": [
                        {"type": "template", "key": "name",  "value": "contact_form_submission"},
                        {"type": "template", "key": "value", "value": "1"}
                    ]
                }]
            }
        ],
        "firingTriggerId": [thank_you_id]
    }
)

# ── Test 7: Custom HTML (html) — Maskyoo-style ────────────────────────────────
try_create(
    "Tag: Custom HTML (html)",
    tags_res,
    {
        "name": "DIAG - Custom HTML",
        "type": "html",
        "parameter": [
            {"type": "template", "key": "html",
             "value": "<script>console.log('diag');</script>"},
            {"type": "boolean",  "key": "supportDocumentWrite", "value": "false"}
        ],
        "firingTriggerId": [ALL_PAGES]
    }
)

# ── Test 8: GA4 Event phone_clicks on Link Click trigger ─────────────────────
link_trig = try_create(
    "Trigger: Link Click (tel:)",
    trigs_res,
    {
        "name": "DIAG - Click Phone",
        "type": "LINK_CLICK",
        "filter": [{
            "type": "CONTAINS",
            "parameter": [
                {"type": "template", "key": "arg0", "value": "{{Click URL}}"},
                {"type": "template", "key": "arg1", "value": "tel"}
            ]
        }]
    }
)
phone_trig_id = link_trig.get("triggerId") if link_trig else ALL_PAGES

try_create(
    "Tag: GA4 Event phone_clicks",
    tags_res,
    {
        "name": "DIAG - phone_clicks",
        "type": "gaawe",
        "parameter": [
            {"type": "template", "key": "eventName", "value": "phone_clicks"},
            {
                "type": "list",
                "key": "eventParameters",
                "list": [{
                    "type": "map",
                    "map": [
                        {"type": "template", "key": "name",  "value": "phone_clicks"},
                        {"type": "template", "key": "value", "value": "1"}
                    ]
                }]
            }
        ],
        "firingTriggerId": [phone_trig_id]
    }
)

# ── Summary ────────────────────────────────────────────────────────────────────
print("\n" + "=" * 55)
print("  RESULTS SUMMARY")
print("=" * 55)
for label, (status, detail) in results.items():
    icon = "[OK]  " if status == "OK" else "[FAIL]"
    print(f"  {icon} {label}")
    if status == "FAIL":
        print(f"         {detail[:120]}")
print()
