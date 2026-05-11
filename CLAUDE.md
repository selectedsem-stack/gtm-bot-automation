# gtm-bot-automation — מערכת ניהול לקוחות

## מה הפרויקט הזה

מערכת אוטומציה לניהול כמה עשרות אתרי WordPress וחשבונות GTM/GA4 עבור סוכנות שיווק ישראלית.
כל לקוח חדש מקבל GTM container, GA4 property, ותגים מלאים — אוטומטית, דרך שיחה אחת.

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
| `invalid_grant` — token פג | פתח את האפליקציה ב-Streamlit — היא תציג כפתור "Authorize with Google" אוטומטית. אחרי חידוש הטוקן ועדכון Railway env var, האפליקציה ממשיכה כרגיל. (חלופה ידנית: הרצה של `authenticate.py` ועדכון `GOOGLE_TOKEN_JSON` ב-Railway dashboard) |
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
