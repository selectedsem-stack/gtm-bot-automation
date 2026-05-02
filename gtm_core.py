import os
import json
import copy
from datetime import date

from googleapiclient.discovery import build
from google.analytics.admin import AnalyticsAdminServiceClient
from google.analytics.admin_v1alpha.types import (
    Property, DataStream, ListAccountsRequest
)

TEMPLATE_FILE = os.path.join(os.path.dirname(__file__), "gtm-template", "template.json")
GTM_ACCOUNT_ID = "6352015198"
BUILTIN_TRIGGER_ALL_PAGES = "2147479553"
ECOMMERCE_KEYWORDS = ["ecommerce", "purchase", "add_to_cart", "begin_checkout", "view_item", "remove_from_cart"]

_STRIP_FIELDS = {"accountId", "containerId", "workspaceId", "parentFolderId",
                 "fingerprint", "tagManagerUrl", "path"}

_BUILTIN_VAR_TYPE_MAP = {
    "PAGE_URL": "pageUrl", "PAGE_HOSTNAME": "pageHostname", "PAGE_PATH": "pagePath",
    "REFERRER": "referrer", "EVENT": "event", "CLICK_ELEMENT": "clickElement",
    "CLICK_CLASSES": "clickClasses", "CLICK_ID": "clickId", "CLICK_TARGET": "clickTarget",
    "CLICK_URL": "clickUrl", "CLICK_TEXT": "clickText", "FORM_ELEMENT": "formElement",
    "FORM_CLASSES": "formClasses", "FORM_ID": "formId", "FORM_TARGET": "formTarget",
    "FORM_URL": "formUrl", "FORM_TEXT": "formText", "RANDOM_NUMBER": "randomNumber",
    "CONTAINER_ID": "containerId", "CONTAINER_VERSION": "containerVersion",
    "DEBUG_MODE": "debugMode", "HTML_ID": "htmlId",
}


def _clean(entity, id_key):
    return {k: v for k, v in entity.items() if k not in _STRIP_FIELDS and k != id_key}


def _safe_name(name):
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


def list_ga4_accounts(creds):
    client = AnalyticsAdminServiceClient(credentials=creds)
    accounts = list(client.list_accounts(ListAccountsRequest()))
    return [{"id": a.name.split("/")[-1], "name": a.display_name} for a in accounts]


def run_client_setup(creds, info: dict, ga4_account_id: str, log_callback=None):
    def log(msg):
        if log_callback:
            log_callback(msg)

    gtm_service = build("tagmanager", "v2", credentials=creds)
    ga4_client = AnalyticsAdminServiceClient(credentials=creds)

    log(f"Creating GTM container for {info['domain']}...")
    container = gtm_service.accounts().containers().create(
        parent=f"accounts/{GTM_ACCOUNT_ID}",
        body={"name": info["domain"], "usageContext": ["web"]}
    ).execute()
    gtm_id = container["publicId"]
    container_path = container["path"]
    log(f"[OK] GTM Container: {gtm_id}")

    log(f"Creating GA4 property for {info['client_name']}...")
    prop = ga4_client.create_property(
        property=Property(
            display_name=info["client_name"],
            time_zone="Asia/Jerusalem",
            currency_code="ILS",
            parent=f"accounts/{ga4_account_id}",
        )
    )
    stream = ga4_client.create_data_stream(
        parent=prop.name,
        data_stream=DataStream(
            web_stream_data=DataStream.WebStreamData(
                default_uri=f"https://{info['domain']}",
            ),
            display_name=info["client_name"],
            type_=DataStream.DataStreamType.WEB_DATA_STREAM,
        )
    )
    measurement_id = stream.web_stream_data.measurement_id
    stream_id = stream.name.split("/")[-1]
    log(f"[OK] GA4 Measurement ID: {measurement_id}")
    log(f"[OK] GA4 Stream ID: {stream_id}")

    log("Processing GTM template...")
    version, kept_tags, removed_tags = _process_template(info, measurement_id, stream_id)
    log(f"  Tags: {len(kept_tags)} included, {len(removed_tags)} skipped")

    log("Importing tags to GTM workspace...")
    today_str = date.today().strftime("%d/%m/%Y")
    description = f"Initial setup - {info['client_name']} - {today_str}"
    _import_and_publish(gtm_service, container_path, version, description, log)
    log("[OK] GTM container published")

    head_code, body_code = _generate_embed_codes(gtm_id, measurement_id)

    return {
        "gtm_id": gtm_id,
        "measurement_id": measurement_id,
        "stream_id": stream_id,
        "kept_tags": kept_tags,
        "removed_tags": removed_tags,
        "head_code": head_code,
        "body_code": body_code,
    }


def _process_template(info, measurement_id, stream_id):
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
    return version, kept_names, removed_tags


def _import_and_publish(gtm_service, container_path, version, description, log):
    ws_resp = gtm_service.accounts().containers().workspaces().list(
        parent=container_path
    ).execute()
    workspaces = ws_resp.get("workspace", [])
    if not workspaces:
        raise RuntimeError("No workspace found in the new container.")

    workspace_path = workspaces[0]["path"]

    builtin_vars = version.get("builtInVariable", [])
    if builtin_vars:
        types = [_BUILTIN_VAR_TYPE_MAP.get(bv["type"], bv["type"]) for bv in builtin_vars]
        try:
            gtm_service.accounts().containers().workspaces().built_in_variables().create(
                parent=workspace_path, type=types
            ).execute()
        except Exception as e:
            log(f"  [WARN] Built-in variables: {e}")

    trigger_id_map = {}
    for trigger in version.get("trigger", []):
        old_id = trigger.get("triggerId")
        body = _clean(trigger, "triggerId")
        body["name"] = _safe_name(body.get("name", ""))
        result = gtm_service.accounts().containers().workspaces().triggers().create(
            parent=workspace_path, body=body
        ).execute()
        new_id = result.get("triggerId")
        if old_id:
            trigger_id_map[old_id] = new_id
        log(f"  Trigger: {body['name']}")

    for variable in version.get("variable", []):
        gtm_service.accounts().containers().workspaces().variables().create(
            parent=workspace_path, body=_clean(variable, "variableId")
        ).execute()
        log(f"  Variable: {variable.get('name', '')}")

    for tag in version.get("tag", []):
        tname = tag.get("name", "")
        new_firing_ids = []
        for fid in tag.get("firingTriggerId", []):
            if fid == BUILTIN_TRIGGER_ALL_PAGES:
                new_firing_ids.append(fid)
            elif fid in trigger_id_map:
                new_firing_ids.append(trigger_id_map[fid])

        body = _clean(tag, "tagId")
        body["firingTriggerId"] = new_firing_ids
        if body.get("type") == "googtag":
            for param in body.get("parameter", []):
                if param.get("key") == "id":
                    param["key"] = "tagId"

        gtm_service.accounts().containers().workspaces().tags().create(
            parent=workspace_path, body=body
        ).execute()
        log(f"  Tag: {tname}")

    ver_resp = gtm_service.accounts().containers().workspaces().create_version(
        path=workspace_path,
        body={"name": description, "notes": description}
    ).execute()
    version_path = ver_resp.get("containerVersion", {}).get("path")
    if not version_path:
        raise RuntimeError("Could not retrieve version path for publishing.")
    gtm_service.accounts().containers().versions().publish(path=version_path).execute()


def _generate_embed_codes(gtm_id, measurement_id):
    head_code = (
        f"<!-- Google Tag Manager -->\n"
        f"<script>(function(w,d,s,l,i){{w[l]=w[l]||[];w[l].push({{'gtm.start':\n"
        f"new Date().getTime(),event:'gtm.js'}});var f=d.getElementsByTagName(s)[0],\n"
        f"j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=\n"
        f"'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);\n"
        f"}})(window,document,'script','dataLayer','{gtm_id}');</script>\n"
        f"<!-- End Google Tag Manager -->\n\n"
        f"<!-- Google tag (gtag.js) -->\n"
        f'<script async src="https://www.googletagmanager.com/gtag/js?id={measurement_id}"></script>\n'
        f"<script>\n"
        f"  window.dataLayer = window.dataLayer || [];\n"
        f"  function gtag(){{dataLayer.push(arguments);}}\n"
        f"  gtag('js', new Date());\n"
        f"  gtag('config', '{measurement_id}');\n"
        f"</script>"
    )
    body_code = (
        f"<!-- Google Tag Manager (noscript) -->\n"
        f'<noscript><iframe src="https://www.googletagmanager.com/ns.html?id={gtm_id}"\n'
        f'height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>\n'
        f"<!-- End Google Tag Manager (noscript) -->"
    )
    return head_code, body_code
