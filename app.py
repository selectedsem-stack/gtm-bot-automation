import os
import streamlit as st

from auth import load_credentials
from gtm_core import list_ga4_accounts, run_client_setup

st.set_page_config(page_title="GTM + GA4 Setup", page_icon="🏷️", layout="centered")


def _get_secret(key: str) -> str:
    try:
        return st.secrets.get(key, "") or os.environ.get(key, "")
    except Exception:
        return os.environ.get(key, "")


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


_check_password()

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

    if "ga4_accounts" not in st.session_state:
        with st.spinner("Connecting to Google APIs..."):
            try:
                creds = load_credentials()
                accounts = list_ga4_accounts(creds)
                st.session_state.ga4_accounts = accounts
                st.session_state.creds = creds
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
                    st.session_state.creds,
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
