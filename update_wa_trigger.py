"""
One-off maintenance script.

Updates the WhatsApp click trigger in an EXISTING GTM container so it fires
on both `wa.me` and `api.whatsapp` links (some client sites use one format,
some the other). Changes the trigger filter from CONTAINS "wa.me" to
MATCH_REGEX "wa\\.me|api\\.whatsapp", then publishes a new container version.

Usage:
  python update_wa_trigger.py <container_name>            # inspect only, no changes
  python update_wa_trigger.py <container_name> --apply    # update trigger + publish
"""
import sys, io, json, argparse
from datetime import date

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from googleapiclient.discovery import build
from auth import load_credentials

GTM_ACCOUNT_ID = "6352015198"
NEW_REGEX = r"wa\.me|api\.whatsapp"
NEW_NAME = "Click - WhatsApp"


def find_container(svc, name):
    containers = svc.accounts().containers().list(
        parent=f"accounts/{GTM_ACCOUNT_ID}"
    ).execute().get("container", [])
    matches = [c for c in containers if c["name"].strip().lower() == name.strip().lower()]
    if not matches:
        avail = ", ".join(c["name"] for c in containers)
        raise SystemExit(f"[ERROR] No container named '{name}'.\n  Available: {avail}")
    if len(matches) > 1:
        raise SystemExit(f"[ERROR] {len(matches)} containers named '{name}' - ambiguous.")
    return matches[0]


def find_wa_trigger(triggers):
    """A WhatsApp Link Click trigger that mentions wa.me/whatsapp.

    The GTM API returns enum values in camelCase (e.g. 'linkClick') even
    though the container export format uses UPPER_CASE ('LINK_CLICK'), so
    the type check is normalised.
    """
    out = []
    for t in triggers:
        if t.get("type", "").lower().replace("_", "") != "linkclick":
            continue
        blob = json.dumps(t, ensure_ascii=False).lower()
        if "wa.me" in blob or "whatsapp" in blob:
            out.append(t)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("container", help="GTM container name (e.g. kalima.co.il)")
    ap.add_argument("--apply", action="store_true",
                    help="actually update the trigger and publish a new version")
    args = ap.parse_args()

    creds = load_credentials()
    svc = build("tagmanager", "v2", credentials=creds)

    container = find_container(svc, args.container)
    print(f"Container: {container['name']}  ({container['publicId']})")
    cpath = container["path"]

    workspaces = svc.accounts().containers().workspaces().list(
        parent=cpath
    ).execute().get("workspace", [])
    if not workspaces:
        raise SystemExit("[ERROR] No workspace found in container.")
    ws = workspaces[0]
    ws_path = ws["path"]
    print(f"Workspace: {ws.get('name')}")

    triggers = svc.accounts().containers().workspaces().triggers().list(
        parent=ws_path
    ).execute().get("trigger", [])

    cands = find_wa_trigger(triggers)
    if not cands:
        raise SystemExit("[ERROR] No LINK_CLICK WhatsApp trigger found in this container.")
    if len(cands) > 1:
        print("[WARN] Multiple WhatsApp Link Click triggers found:")
        for t in cands:
            print(f"   - {t.get('name')} (id={t.get('triggerId')})")
        raise SystemExit("Aborting - resolve ambiguity manually.")

    trig = cands[0]
    print(f"\nFound trigger: '{trig.get('name')}' (triggerId={trig.get('triggerId')})")
    print("  BEFORE filter: " + json.dumps(trig.get("filter", []), ensure_ascii=False))

    if "api.whatsapp" in json.dumps(trig.get("filter", []), ensure_ascii=False):
        print("\n[SKIP] Trigger already matches api.whatsapp - nothing to do.")
        return

    # camelCase 'matchRegex' = the GTM API's native format (it returns
    # 'contains' lowercase for existing filters); the export format would
    # spell this 'MATCH_REGEX'.
    new_filter = [{
        "type": "matchRegex",
        "parameter": [
            {"type": "template", "key": "arg0", "value": "{{Click URL}}"},
            {"type": "template", "key": "arg1", "value": NEW_REGEX},
        ],
    }]
    print("  AFTER  filter: " + json.dumps(new_filter, ensure_ascii=False))

    if not args.apply:
        print("\n[DRY RUN] No changes made. Re-run with --apply to update + publish.")
        return

    # Safety: don't bundle unrelated pending changes into the published version.
    try:
        status = svc.accounts().containers().workspaces().getStatus(
            path=ws_path
        ).execute()
        pending = status.get("workspaceChange", [])
        if pending:
            print(f"\n[WARN] Workspace already has {len(pending)} pending change(s):")
            for ch in pending:
                print(f"   - {json.dumps(ch, ensure_ascii=False)}")
            raise SystemExit("Aborting - publishing would include unrelated changes.")
    except SystemExit:
        raise
    except Exception as e:
        print(f"[WARN] Could not verify workspace status ({e}) - continuing.")

    body = dict(trig)
    body["name"] = NEW_NAME
    body["filter"] = new_filter
    body.pop("fingerprint", None)

    updated = svc.accounts().containers().workspaces().triggers().update(
        path=trig["path"], body=body
    ).execute()
    print(f"\n[OK] Trigger updated -> '{updated.get('name')}'")
    print("  " + json.dumps(updated.get("filter", []), ensure_ascii=False))

    today = date.today().strftime("%d/%m/%Y")
    desc = f"WA click trigger: fire on wa.me OR api.whatsapp - {today}"
    ver = svc.accounts().containers().workspaces().create_version(
        path=ws_path, body={"name": desc, "notes": desc}
    ).execute()
    cv = ver.get("containerVersion", {})
    vpath = cv.get("path")
    if not vpath:
        raise SystemExit("[ERROR] No version path returned - not published.")
    svc.accounts().containers().versions().publish(path=vpath).execute()
    print(f"[OK] Published new live version (v{cv.get('containerVersionId')}) - '{desc}'")


if __name__ == "__main__":
    main()
