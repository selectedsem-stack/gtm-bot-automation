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
| `oauth-credentials.json` | פרטי OAuth מ-Google Cloud (סודי) |

**לעולם אל תעלה לשום מקום:** `sites.json`, `token.json`, `oauth-credentials.json`

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
| `invalid_grant` — token פג | מחק token.json ← הרץ סקריפט אימות מחדש |
| `403 GTM` — אין גישה ל-account | בדוק שה-OAuth מחובר לחשבון הנכון |
| `SSH Connection refused` | בדוק IP ב-Cloudways Master Credentials |
| `WP-CLI not found` | בדוק שה-wp_path ב-sites.json נכון |
| `401 REST API` | צור Application Password חדשה |
| `GA4 quota exceeded` | עבור ל-GA4 account אחר (מקסימום 100 properties לחשבון) |

---

## מה לא לעשות

- אל תשנה `template.json` ישירות — עדכן דרך GTM ואז ייצא מחדש
- אל תריץ פעולות מסיביות בלי לאשר קודם על דוגמה אחת
- אל תוסיף credentials ישירות לקוד — תמיד דרך token.json / sites.json
- אל תפרסם container ב-GTM בלי לשאול אם לא ביקשו במפורש
