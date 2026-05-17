# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# gtm-bot-automation — מערכת ניהול לקוחות

## מה הפרויקט הזה

מערכת אוטומציה לניהול כמה עשרות אתרי WordPress וחשבונות GTM/GA4 עבור סוכנות שיווק ישראלית.
כל לקוח חדש מקבל GTM container, GA4 property, ותגים מלאים — אוטומטית, דרך שיחה אחת.

---

## פקודות נפוצות

```bash
# הרצת ה-Streamlit UI מקומית (ה-entry point הראשי)
streamlit run app.py

# יצירת token.json ראשוני באמצעות Desktop OAuth flow (פותח דפדפן)
python authenticate.py

# גרסת CLI אינטראקטיבית של הקמת לקוח (חלופה ל-Streamlit)
python new_client_setup.py

# כלי debug — רשימת GTM accounts / GA4 accounts זמינים לטוקן הנוכחי
python list_accounts.py
python list_ga_accounts.py

# smoke test לגישת GTM API
python test_gtm_api.py

# עדכון נקודתי של טריגר WhatsApp ב-container קיים
python update_wa_trigger.py <container_name>          # inspect בלבד (ברירת מחדל)
python update_wa_trigger.py <container_name> --apply  # עדכון הטריגר + פרסום גרסה
```

- **אין** test suite או linter מוגדרים בפרויקט.
- **דיפלוי:** push ל-branch `master` ב-`selectedsem-stack/gtm-bot-automation` → Streamlit Community Cloud עושה redeploy אוטומטי (~30 שניות). אין שלב build נפרד.

---

## ארכיטקטורה (כללי)

### שתי נקודות כניסה, גרעין משותף
- **`app.py`** — Streamlit web app (production entry point, רץ ב-Streamlit Cloud)
- **`new_client_setup.py`** — CLI אינטראקטיבי (מקומי בלבד, לא משמש בפרודקשן)
- שניהם קוראים ל-`gtm_core.py` שמרכז את כל הלוגיקה (יצירת GTM container, GA4 property, חיתוך תגים מהתבנית, פרסום).
- `gtm_core.run_client_setup(creds, info, ga4_account_id, log_callback)` — orchestrator יחיד שמבצע את ההקמה מקצה לקצה.

### זרימת credentials (קריטי להבנה)
1. `auth.load_credentials()` קורא טוקן ב-priority הבא: `st.secrets["GOOGLE_TOKEN_JSON"]` → env var `GOOGLE_TOKEN_JSON` → קובץ `token.json` מקומי.
2. מבצע `creds.refresh()` ומחזיר אותו.
3. אם refresh נכשל (טוקן revoked/expired) — מעלה `NeedsReauthError`.
4. `app.py::_ensure_credentials()` תופס את זה ומציג את `_render_reauth_ui()` במקום להתרסק.
5. `_render_reauth_ui()` משתמש ב-`web_oauth.py` להפעיל זרימת OAuth web (PKCE) — המשתמש לוחץ → Google → חוזר ל-`?code=...&state=...` → `_handle_oauth_callback()` מחליף קוד לטוקן ושומר.
6. **PKCE code_verifier** נשמר ב-`.oauth_state.json` יחד עם ה-state כי הוא חייב לשרוד את ה-redirect (Flow חדש בצד ה-callback ייצר verifier אחר וייכשל ב-`invalid_grant: Missing code verifier`).

### שני OAuth clients — לא להתבלבל
- **Desktop client** (`oauth-credentials.json.json`) — בשימוש רק ב-`authenticate.py` (יצירת token.json ראשוני מקומית, `InstalledAppFlow.run_local_server`).
- **Web client** (`oauth-web-credentials.json` או `st.secrets["oauth_web_client"]`) — בשימוש רק ב-`web_oauth.py` עבור reauth UI ב-Streamlit. דורש redirect URIs רשומים ב-Google Cloud Console.

### תבנית GTM
- `gtm-template/template.json` — export מלא של container עם PLACEHOLDERs (`PLACEHOLDER_GA4_ID`, `PLACEHOLDER_ADS_ID`, `PLACEHOLDER_PIXEL_ID`, `PLACEHOLDER_DOMAIN`).
- `gtm_core` משכפל את התבנית, מבצע substitution, ומסיר תגים לא רלוונטיים (לדוגמה תגי eCommerce כשהלקוח לא חנות — לפי `ECOMMERCE_KEYWORDS`).
- שינוי תבנית: לעולם לא לערוך JSON ידנית — לעדכן ב-GTM UI ולייצא מחדש.

---

## קבצים חשובים — קרא לפני כל פעולה

| קובץ | תפקיד |
|---|---|
| `sites.json` | רשימת כל אתרי ה-WordPress — כתובת, שרת Cloudways, נתיב WP, פרטי API |
| `new_client_setup.py` | סקריפט הקמת לקוח חדש — GTM + GA4 + תגים אוטומטי |
| `gtm-template/template.json` | תבנית GTM container עם PLACEHOLDERs |
| `token.json` | OAuth token לגישה ל-GTM API ו-GA4 API (נוצר אוטומטית) |
| `oauth-credentials.json.json` | OAuth Desktop client — לאימות מקומי דרך `authenticate.py` |
| `oauth-web-credentials.json` | OAuth Web Application client — לחידוש טוקן דרך ה-UI (לוקאלית) |
| `auth.py` | טעינת credentials + רענון; מעלה `NeedsReauthError` אם הטוקן נשרף |
| `web_oauth.py` | זרימת OAuth מבוססת-redirect לתוך Streamlit |
| `update_wa_trigger.py` | סקריפט תחזוקה — עדכון טריגר ב-container חי; `inspect` כברירת מחדל, `--apply` משנה ומפרסם גרסה |

**לעולם אל תעלה לשום מקום:** `sites.json`, `token.json`, `oauth-credentials.json.json`, `oauth-web-credentials.json`, `.oauth_state.json`

---

## תשתית טכנית

### WordPress / Cloudways
- כל האתרים מאוחסנים על **Cloudways**
- גישה דרך **SSH** עם מפתח SSH מוגדר ב-`~/.ssh/config`
- כינויי שרת: `cloudways-server1`, `cloudways-server2` וכו׳
- נתיב אתרים: `/home/[master_user]/htdocs/[domain]/public_html/`
- **WP-CLI מותקן** על כל שרת Cloudways — השתמש בו לכל פעולת WordPress
- גישת REST API לכל אתר דרך **Application Passwords**

### GTM
- גישה דרך **GTM API** עם OAuth (token.json)
- לכל לקוח — container נפרד
- תבנית תגים: `gtm-template/template.json`
- PLACEHOLDERs בתבנית: `PLACEHOLDER_GA4_ID`, `PLACEHOLDER_ADS_ID`, `PLACEHOLDER_PIXEL_ID`, `PLACEHOLDER_DOMAIN`
- תגי eCommerce בתבנית מסומנים בשמות: ecommerce, purchase, add_to_cart, begin_checkout, view_item

### מלכודות GTM API — לדעת לפני עבודה עם triggers / tags
- **Casing של enums:** `template.json` (פורמט export) משתמש ב-UPPER_SNAKE_CASE — `LINK_CLICK`, `CONTAINS`, `MATCH_REGEX`, `PAGEVIEW`. ה-API **מחזיר** בקריאה camelCase — `linkClick`, `contains`, `matchRegex`, `pageview`. בכתיבה ה-API מקבל את שתי הצורות. קוד שמשווה שדה `type` חייב לנרמל casing.
- **OR בפילטר trigger:** כמה תנאי `filter` באותו trigger מחוברים ב-AND. ל-OR (למשל URL שמכיל wa.me **או** api.whatsapp) — תנאי `matchRegex` יחיד עם `|`. שני תנאי `contains` נפרדים לעולם לא יירו יחד.
- **עדכון container חי:** שנה entity ב-workspace → `workspaces().create_version()` → `versions().publish()`. לפני פרסום בדוק `workspaces().getStatus()` שאין שינויים תלויים אחרים שייכנסו לגרסה. שמות מתודות ב-googleapiclient הם snake_case (`create_version`) פרט ל-`getStatus` שנשאר camelCase.

### GA4
- גישה דרך **Analytics Admin API** עם אותו OAuth token
- לסוכנות יש **15 GA4 accounts** — המשתמש בוחר בכל הקמה
- לכל לקוח — property נפרד + Web data stream
- **Measurement ID (G-XXXXXXXXXX)** — נכנס ל-GTM כ-Google Tag ראשי
- **Stream ID** — נכנס ל-GTM כ-Google Tag שני (נפרד), ולתיעוד

---

## עקרונות עבודה

### כשמוסיפים אתר WordPress חדש
1. הוסף שורה ל-`sites.json` עם כל הפרטים
2. בדוק חיבור SSH: `ssh cloudways-serverX`
3. בדוק WP-CLI: `wp --path=[נתיב] core version`
4. צור Application Password ב-WordPress → Users → Profile
5. בדוק REST API: `[domain]/wp-json/wp/v2/users/me?context=edit`

### כשמקימים לקוח חדש (GTM + GA4)

**שלב ידני לפני הסקריפט — יצירת GTM Account:**
GTM API לא תומך ביצירת accounts חדשים. לפני הרצת הסקריפט:
1. פתח [tagmanager.google.com](https://tagmanager.google.com)
2. לחץ **Create Account**
3. Account Name: שם הלקוח / דומיין | Country: Israel
4. Container Name: הדומיין | Target platform: Web
5. Save
→ Account החדש יופיע ברשימה כשתריץ את הסקריפט

הרץ תמיד את `new_client_setup.py` — הסקריפט שואל הכל אינטראקטיבית:
- שם לקוח ודומיין
- האם חנות eCommerce?
- כתובת עמוד תודה לטופס יצירת קשר
- האם צריך Google Ads? (ואז שואל Conversion ID)
- האם צריך Facebook Pixel? (ואז שואל Pixel ID)
- האם צריך Maskyoo? (ואז שואל מספר)
- בחירת GTM account מרשימה (בחר את ה-account שיצרת זה עתה)
- בחירת GA4 account מרשימה

### כשמבצעים פעולה על כמה אתרים
- **תמיד** בדוק תחילה על אתר אחד ודווח לפני שממשיכים לשאר
- **תמיד** דווח בסיום: כמה הצליחו, כמה נכשלו, מה הסיבה לכישלון
- **לעולם** אל תעדכן קבצי קוד ראשיים בלי לשאול

---

## פרומפטים שימושיים — הפעל לפי הצורך

### הקמת לקוח חדש
```
הרץ את new_client_setup.py
```

### סטטוס כל האתרים
```
עבור על כל האתרים ב-sites.json.
לכל אתר דווח: גרסת WordPress, מספר פלאגינים פעילים, האם REST API מגיב.
```

### הטמעת סקריפט על כל האתרים
```
עבור על כל האתרים ב-sites.json.
על כל אתר הפעל דרך SSH + WP-CLI את הפלאגין headers-and-footers
ועדכן את הגדרות ה-head וה-body עם הקוד הבא: [קוד]
דווח על כל אתר — הצלחה או שגיאה.
```

### עדכון כל הפלאגינים
```
עדכן את כל הפלאגינים על כל האתרים ב-sites.json.
לפני כל שרת — דווח מה עומד להתעדכן.
```

### הוספת תג חדש לכל containers ב-GTM
```
הוסף לכל ה-GTM containers שמפורטים ב-sites.json
את התג הבא: [תיאור]
פרסם גרסה חדשה עם תיאור: "Added [שם תג] - [תאריך]"
```

### בדיקת סטטוס GTM containers
```
עבור על כל האתרים ב-sites.json.
לכל אתר בדוק ב-GTM: האם יש container פעיל? מה גרסה פעילה? האם יש שינויים שלא פורסמו?
```

---

## טיפול בשגיאות נפוצות

| שגיאה | פתרון |
|---|---|
| `invalid_grant` — token פג/בוטל | פתח את האפליקציה ב-Streamlit — תציג כפתור "Authorize with Google" אוטומטית. אחרי חידוש, עדכן את ה-secret `GOOGLE_TOKEN_JSON` ב-Streamlit Cloud → Settings → Secrets. (חלופה מקומית: מחק `token.json` והרץ `authenticate.py`) |
| `invalid_scope` ברענון טוקן | רשימות ה-SCOPES ב-`auth.py` ו-`authenticate.py` אינן זהות. ודא התאמה מלאה, מחק `token.json`, הרץ `authenticate.py` מחדש |
| `403 GTM` — אין גישה ל-account | בדוק שה-OAuth מחובר לחשבון הנכון |
| `SSH Connection refused` | בדוק IP ב-Cloudways Master Credentials |
| `WP-CLI not found` | בדוק שה-wp_path ב-sites.json נכון |
| `401 REST API` | צור Application Password חדשה |
| `GA4 quota exceeded` | עבור ל-GA4 account אחר (מקסימום 100 properties לחשבון) |

---

## פלטפורמת הרצה: Streamlit Community Cloud

האפליקציה רצה על Streamlit Community Cloud (URL מסתיים ב-`.streamlit.app`).
ניהול האפליקציה והסודות נעשה ב-[share.streamlit.io](https://share.streamlit.io/).

**הערה:** `railway.toml` נשאר בתיקייה כשריד מנסיון פריסה קודם — לא בשימוש.

## הגדרת חידוש טוקן אוטומטי (חד-פעמי)

כדי שהאפליקציה תוכל לחדש את הטוקן לבד דרך הדפדפן, צריך פעם אחת להגדיר:

### 1. פרסום ה-OAuth app (חובה — אחרת הטוקן ימשיך למות כל 7 ימים)
1. [Google Cloud Console → OAuth consent screen](https://console.cloud.google.com/apis/credentials/consent)
2. **Publish App**
3. אזהרת "Unverified app" עבור scopes פנימיים של הסוכנות — אפשר להתעלם. ה-app משמש אותך, לא משתמשים חיצוניים.

### 2. Web OAuth client ב-Google Cloud Console
1. [Google Cloud Console → Credentials](https://console.cloud.google.com/apis/credentials)
2. **Create Credentials → OAuth client ID → Web application**
3. Name: `gtm-bot-web`
4. **Authorized redirect URIs** — הוסף **שניהם** (הסלאש בסוף חובה):
   - `http://localhost:8501/` (לפיתוח מקומי)
   - `https://<your-app-slug>.streamlit.app/` (production)
5. Create → Download JSON

### 3. Streamlit Cloud Secrets
ב-[share.streamlit.io](https://share.streamlit.io/) → האפליקציה → ⋮ → **Settings → Secrets**, הקובץ צריך להיראות:

```toml
APP_PASSWORD = "..."                              # סיסמת הכניסה לאפליקציה
GOOGLE_TOKEN_JSON = "..."                         # JSON של token.json (אם תהיה בעיה ב-TOML, השתמש במרכאות יחידות '...')
OAUTH_REDIRECT_URI = "https://<your-app-slug>.streamlit.app/"

[oauth_web_client]
client_id = "..."
project_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_secret = "..."
redirect_uris = ["http://localhost:8501/", "https://<your-app-slug>.streamlit.app/"]
```

**חשוב — סדר ב-TOML:** כל המפתחות הטופ-לבל (`APP_PASSWORD`, `GOOGLE_TOKEN_JSON`, `OAUTH_REDIRECT_URI`) חייבים להיות **לפני** כל `[section]`. אחרי `[oauth_web_client]` כל מפתח נכנס לתוך הסקציה.

### זרימת חידוש (אחרי שהכל מוגדר)
1. הטוקן נשרף → האפליקציה מציגה "Re-authorize Google Access"
2. לוחץ "Authorize with Google" → Google → מאשר → חוזר ל-app
3. App מציג את ה-`GOOGLE_TOKEN_JSON` החדש
4. מעתיק אותו ל-Streamlit Cloud Secrets ושומר
5. אחרי שמירה Streamlit Cloud עושה restart אוטומטי — האפליקציה חיה עם הטוקן החדש

**חשוב:** ב-Streamlit Community Cloud אין API לעדכון Secrets — חייב לעדכן דרך ה-UI ידנית. עם זאת, ברגע שפרסמת את ה-OAuth app (שלב 1), refresh tokens לא פגים יותר ותצטרך לעבור את הזרימה הזו רק במקרים נדירים (ביטול ידני, אי-שימוש 6 חודשים).

---

## מה לא לעשות

- אל תשנה `template.json` ישירות — עדכן דרך GTM ואז ייצא מחדש
- אל תריץ פעולות מסיביות בלי לאשר קודם על דוגמה אחת
- אל תוסיף credentials ישירות לקוד — תמיד דרך token.json / sites.json
- אל תפרסם container ב-GTM בלי לשאול אם לא ביקשו במפורש
- אל תשנה את רשימת ה-SCOPES בקובץ אחד בלבד — `auth.py` (צרכן הטוקן) ו-`authenticate.py` (מנפיק הטוקן) חייבים רשימת scopes זהה
