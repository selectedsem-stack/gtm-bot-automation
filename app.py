import json
import os
import time

import streamlit as st

from auth import NeedsReauthError, load_credentials
from gtm_core import list_ga4_accounts, run_client_setup
from web_oauth import build_flow, detect_redirect_uri, finish_auth, start_auth

st.set_page_config(page_title="GTM + GA4 Setup", page_icon="🏷️", layout="centered")

OAUTH_STATE_FILE = ".oauth_state.json"
OAUTH_STATE_TTL_SEC = 600  # 10 minutes


def _get_secret(key: str) -> str:
    try:
        return st.secrets.get(key, "") or os.environ.get(key, "")
    except Exception:
        return os.environ.get(key, "")


# ── OAuth state persistence (survives the Google redirect) ─────────────────────
def _save_oauth_state(state: str, redirect_uri: str, code_verifier: str | None) -> None:
    with open(OAUTH_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "state": state,
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
            "ts": time.time(),
        }, f)


def _load_oauth_state() -> dict | None:
    if not os.path.exists(OAUTH_STATE_FILE):
        return None
    try:
        with open(OAUTH_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None
    if time.time() - data.get("ts", 0) > OAUTH_STATE_TTL_SEC:
        _clear_oauth_state()
        return None
    return data


def _clear_oauth_state() -> None:
    try:
        os.remove(OAUTH_STATE_FILE)
    except FileNotFoundError:
        pass


# ── Token persistence ─────────────────────────────────────────────────────────
def _persist_new_token(token_json: str) -> None:
    """Persist refreshed token to working dir for the current session.

    Streamlit Community Cloud has no public API for updating secrets, so the
    new token must be copied to the Streamlit Cloud Secrets UI manually to
    survive container restarts. The caller surfaces the JSON to the user.
    """
    with open("token.json", "w", encoding="utf-8") as f:
        f.write(token_json)


# ── OAuth callback handler ────────────────────────────────────────────────────
def _handle_oauth_callback() -> None:
    """If URL has ?code=...&state=... or ?error=..., handle the OAuth response."""
    params = st.query_params

    if "error" in params:
        err = params.get("error", "unknown_error")
        desc = params.get("error_description", "")
        st.session_state["oauth_error"] = f"{err}: {desc}" if desc else err
        _clear_oauth_state()
        st.query_params.clear()
        return

    if "code" not in params or "state" not in params:
        return

    code = params["code"]
    received_state = params["state"]

    saved = _load_oauth_state()
    if not saved:
        st.error("OAuth session expired or not found. Please start re-authorization again.")
        st.query_params.clear()
        if st.button("Start over"):
            st.rerun()
        st.stop()

    try:
        flow = build_flow(redirect_uri=saved["redirect_uri"])
        creds = finish_auth(
            flow,
            saved["state"],
            received_state,
            code,
            code_verifier=saved.get("code_verifier"),
        )
    except Exception as e:
        st.error(f"Authorization failed: {e}")
        _clear_oauth_state()
        st.query_params.clear()
        if st.button("Try again"):
            st.rerun()
        st.stop()

    token_json = creds.to_json()
    _persist_new_token(token_json)

    _clear_oauth_state()
    st.session_state.pop("oauth_auth_url", None)
    st.session_state["creds"] = creds
    st.session_state["reauth_message"] = "Token refreshed. The session is now active."
    st.session_state["reauth_manual_token"] = token_json
    st.query_params.clear()
    st.rerun()


# ── Reauth UI ─────────────────────────────────────────────────────────────────
def _render_reauth_ui(reason: str | None = None) -> None:
    st.title("Re-authorize Google Access")
    if reason:
        st.warning(reason)

    if err := st.session_state.pop("oauth_error", None):
        st.error(f"Last attempt returned an error from Google: **{err}**")

    redirect_uri = detect_redirect_uri()
    st.caption(f"Redirect URI in use: `{redirect_uri}` — must be registered in Google Cloud Console.")

    auth_url = st.session_state.get("oauth_auth_url")

    if not auth_url:
        st.markdown("Step 1 — generate the Google authorization link:")
        if st.button("Generate authorization link", type="primary"):
            try:
                flow = build_flow(redirect_uri=redirect_uri)
                new_auth_url, state, code_verifier = start_auth(flow)
                _save_oauth_state(state, redirect_uri, code_verifier)
                st.session_state["oauth_auth_url"] = new_auth_url
                st.rerun()
            except Exception as e:
                st.error(f"Could not start OAuth flow: {e}")
                st.stop()
        st.stop()

    st.markdown("Step 2 — open the Google authorization page (same tab) and complete the consent:")
    st.link_button("Open Google authorization page →", auth_url, type="primary")

    with st.expander("Trouble with the button? Copy this URL into your browser address bar"):
        st.code(auth_url)

    st.markdown("---")
    if st.button("Reset and start over"):
        st.session_state.pop("oauth_auth_url", None)
        _clear_oauth_state()
        st.rerun()

    st.stop()


# ── Credentials gate (eager-load + cache in session) ─────────────────────────
def _ensure_credentials():
    if "creds" in st.session_state:
        return st.session_state["creds"]
    try:
        creds = load_credentials()
    except NeedsReauthError as e:
        _render_reauth_ui(reason=str(e))
        return None  # unreachable
    st.session_state["creds"] = creds
    return creds


# ── Password gate ─────────────────────────────────────────────────────────────
def _check_password():
    app_password = _get_secret("APP_PASSWORD")
    if not app_password or st.session_state.get("authenticated"):
        return
    st.title("GTM + GA4 Setup")
    st.markdown("Enter your password to continue.")
    pwd = st.text_input("Password", type="password")
    if st.button("Login", type="primary"):
        if pwd == app_password:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password")
    st.stop()


# ── Boot sequence ─────────────────────────────────────────────────────────────
_check_password()
_handle_oauth_callback()

# Show post-reauth banner if we just finished
if msg := st.session_state.pop("reauth_message", None):
    st.success(msg)
    manual = st.session_state.pop("reauth_manual_token", None)
    if manual:
        st.warning(
            "**Important — save this token to Streamlit Cloud Secrets so it survives the next restart.**\n\n"
            "1. Open [share.streamlit.io](https://share.streamlit.io/) → find this app → ⋮ → Settings → Secrets\n"
            "2. Replace the `GOOGLE_TOKEN_JSON` line. Use **single quotes** (TOML literal string) so the inner double quotes are preserved:\n"
            "   ```toml\n"
            "   GOOGLE_TOKEN_JSON = '<paste the JSON below here, all on one line>'\n"
            "   ```\n"
            "3. Save — Streamlit Cloud will restart the app with the new token.\n\n"
            "Until then, this session works, but a restart will require re-authorizing again."
        )
        st.code(manual, language="json")

# Sidebar: manual re-authorize trigger (for proactive use)
with st.sidebar:
    st.caption("Account")
    if st.button("Re-authorize Google"):
        st.session_state.pop("creds", None)
        st.session_state.pop("ga4_accounts", None)
        _render_reauth_ui(reason="Manual re-authorization requested.")

# Eager credentials check — triggers reauth UI if token is dead
_ensure_credentials()

if "step" not in st.session_state:
    st.session_state.step = 1

step = st.session_state.step

# ── Step 1: Client info ────────────────────────────────────────────────────────
if step == 1:
    st.title("New Client Setup")
    st.subheader("Step 1 of 3 — Client Details")

    with st.form("client_form"):
        client_name = st.text_input("Client name *")
        domain = st.text_input("Domain (without https) *", placeholder="example.com")
        ecommerce = st.checkbox("eCommerce store (WooCommerce / shop)")
        thankyou_url = st.text_input(
            "Contact form thank-you page URL *",
            placeholder="/thank-you/",
            help="The URL fragment that appears in the address bar after a successful form submission"
        )

        st.divider()
        st.markdown("**Optional integrations**")

        google_ads = st.checkbox("Google Ads tracking")
        ads_id = st.text_input("Google Ads Conversion ID", placeholder="AW-XXXXXXXXX")

        facebook_pixel = st.checkbox("Facebook Pixel")
        pixel_id = st.text_input("Facebook Pixel ID")

        maskyoo = st.checkbox("Maskyoo virtual number")
        maskyoo_number = st.text_input("Maskyoo number", placeholder="055-1234567")

        submitted = st.form_submit_button("Next →", type="primary")

    if submitted:
        errors = []
        if not client_name.strip():
            errors.append("Client name is required")
        if not domain.strip():
            errors.append("Domain is required")
        if not thankyou_url.strip():
            errors.append("Thank-you URL is required")
        if google_ads and not ads_id.strip():
            errors.append("Google Ads Conversion ID is required when Google Ads is selected")
        if facebook_pixel and not pixel_id.strip():
            errors.append("Facebook Pixel ID is required when Facebook Pixel is selected")
        if maskyoo and not maskyoo_number.strip():
            errors.append("Maskyoo number is required when Maskyoo is selected")

        if errors:
            for e in errors:
                st.error(e)
        else:
            domain_clean = domain.strip().replace("https://", "").replace("http://", "").rstrip("/")
            st.session_state.info = {
                "client_name": client_name.strip(),
                "domain": domain_clean,
                "ecommerce": ecommerce,
                "thankyou_url": thankyou_url.strip(),
                "google_ads": google_ads,
                "ads_id": ads_id.strip() if google_ads else "",
                "facebook_pixel": facebook_pixel,
                "pixel_id": pixel_id.strip() if facebook_pixel else "",
                "maskyoo": maskyoo,
                "maskyoo_number": maskyoo_number.strip() if maskyoo else "",
            }
            st.session_state.step = 2
            st.rerun()

# ── Step 2: GA4 account selection ─────────────────────────────────────────────
elif step == 2:
    st.title("New Client Setup")
    st.subheader("Step 2 of 3 — Select GA4 Account")

    creds = _ensure_credentials()

    if "ga4_accounts" not in st.session_state:
        with st.spinner("Connecting to Google APIs..."):
            try:
                accounts = list_ga4_accounts(creds)
                st.session_state.ga4_accounts = accounts
            except Exception as e:
                st.error(f"Failed to connect to Google APIs: {e}")
                st.stop()

    accounts = st.session_state.ga4_accounts
    options = {f"{a['name']}  (ID: {a['id']})": a for a in accounts}
    selected_label = st.selectbox("GA4 account:", list(options.keys()))

    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("← Back"):
            st.session_state.step = 1
            st.rerun()
    with col2:
        if st.button("Next →", type="primary"):
            st.session_state.selected_ga4 = options[selected_label]
            st.session_state.step = 3
            st.rerun()

# ── Step 3: Confirm ────────────────────────────────────────────────────────────
elif step == 3:
    st.title("New Client Setup")
    st.subheader("Step 3 of 3 — Confirm & Run")

    info = st.session_state.info
    ga4 = st.session_state.selected_ga4

    st.markdown("Review the details before running:")

    rows = [
        ("Client name", info["client_name"]),
        ("Domain", info["domain"]),
        ("eCommerce", "Yes" if info["ecommerce"] else "No"),
        ("Thank-you URL", info["thankyou_url"]),
        ("Google Ads", f"Yes — {info['ads_id']}" if info["google_ads"] else "No"),
        ("Facebook Pixel", f"Yes — {info['pixel_id']}" if info["facebook_pixel"] else "No"),
        ("Maskyoo", f"Yes — {info['maskyoo_number']}" if info["maskyoo"] else "No"),
        ("GTM Account", "Claude Automation"),
        ("GA4 Account", f"{ga4['name']}  (ID: {ga4['id']})"),
    ]

    table_md = "| Field | Value |\n|---|---|\n" + "\n".join(f"| {k} | {v} |" for k, v in rows)
    st.markdown(table_md)

    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("← Back"):
            st.session_state.step = 2
            st.rerun()
    with col2:
        if st.button("Run Setup", type="primary"):
            st.session_state.pop("result", None)
            st.session_state.pop("setup_logs", None)
            st.session_state.step = 4
            st.rerun()

# ── Step 4: Run + Results ──────────────────────────────────────────────────────
elif step == 4:
    st.title("New Client Setup")

    creds = _ensure_credentials()

    if "result" not in st.session_state:
        st.subheader("Running setup...")
        logs: list[str] = []
        log_area = st.empty()

        def on_log(msg):
            logs.append(msg)
            log_area.text("\n".join(logs))

        try:
            with st.spinner("This takes about 20-30 seconds..."):
                result = run_client_setup(
                    creds,
                    st.session_state.info,
                    st.session_state.selected_ga4["id"],
                    log_callback=on_log,
                )
            st.session_state.result = result
            st.session_state.setup_logs = logs
            st.rerun()
        except Exception as e:
            st.error(f"Setup failed: {e}")
            with st.expander("Log"):
                st.text("\n".join(logs))
            if st.button("← Start Over"):
                for k in ["step", "info", "ga4_accounts", "selected_ga4", "result", "setup_logs", "creds"]:
                    st.session_state.pop(k, None)
                st.rerun()
    else:
        result = st.session_state.result
        info = st.session_state.info

        # Logo
        logo_col, _ = st.columns([1, 5])
        with logo_col:
            if os.path.exists("assets/selected_logo.png"):
                st.image("assets/selected_logo.png", width=160)

        st.subheader("Setup Complete!")
        st.success(f"**{info['client_name']}** created successfully")

        # IDs — full values, no truncation
        st.divider()
        id1, id2, id3 = st.columns(3)
        with id1:
            st.caption("GTM Container")
            st.markdown(f"### `{result['gtm_id']}`")
        with id2:
            st.caption("GA4 Measurement ID")
            st.markdown(f"### `{result['measurement_id']}`")
        with id3:
            st.caption("GA4 Property ID")
            st.markdown(f"### `{result['property_id']}`")
            st.markdown("[use at selected crm](https://www.selected-crm.com/seo-full.php)")

        # Tags log with green checkmarks
        st.divider()
        st.subheader(f"Tags Created ({len(result['kept_tags'])})")
        for tag in result["kept_tags"]:
            st.markdown(f"✅ &nbsp; {tag}")

        if result["removed_tags"]:
            st.divider()
            with st.expander(f"Tags Skipped ({len(result['removed_tags'])})"):
                for tag in result["removed_tags"]:
                    st.markdown(f"⏭️ &nbsp; {tag}")

        st.divider()
        st.subheader("HEAD code — paste above `</head>`")
        st.code(result["head_code"], language="html")

        st.subheader("BODY code — paste after `<body>`")
        st.code(result["body_code"], language="html")

        with st.expander("Setup log"):
            st.text("\n".join(st.session_state.get("setup_logs", [])))

        st.divider()
        if st.button("Setup Another Client", type="primary"):
            for k in ["step", "info", "selected_ga4", "result", "setup_logs"]:
                st.session_state.pop(k, None)
            st.rerun()
