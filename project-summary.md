# סיכום פרויקט — מערכת אוטומציה GTM + GA4
### Selected Digital Agency | מאי 2026

---

## רקע — מה הבעיה שפתרנו

עד היום, כל לקוח חדש שנכנס לסוכנות דרש עבודה ידנית של שעות:
- כניסה ידנית ל-GTM ויצירת container
- הקמת GA4 Property חדש
- הוספת תגים אחד אחד — configuration, events, pixels, המרות
- העתקה-הדבקה של קודי ה-script לתוך ה-WordPress

התהליך היה לא עקבי, תלוי בזיכרון האדם שמבצע, ופתוח לשגיאות.

**הפתרון:** תוכנת web שמבצעת את כל התהליך הזה אוטומטית — תוך 30 שניות, עם תוצאה זהה בכל פעם.

---

## מה בנינו — תיאור המערכת

### סוג המוצר
אפליקציית Web פנימית, בנויה על **Streamlit** (Python), מוגנת בסיסמה.
נגישה מכל מחשב, מכל מקום, דרך הדפדפן.

### תשתית ופריסה
- **שפה:** Python 3
- **ממשק:** Streamlit — ספריית Python לבניית ממשקי Web בלי HTML/CSS
- **ניהול קוד:** GitHub — כל הקוד שמור ב-repository פרטי
- **פריסה:** Streamlit Community Cloud — הפלטפורמה קוראת ישירות מ-GitHub ומריצה את האפליקציה בענן
- **אבטחה:** סיסמת כניסה, HTTPS, credentials מאוחסנים בסביבת הענן (לא בקוד)

---

## ההתממשקות ל-API של גוגל

### מה מחובר
האפליקציה מתממשקת לשני שירותי Google בו-זמנית:

| שירות | API | מה עושים איתו |
|---|---|---|
| Google Tag Manager | GTM API v2 | יצירת container, ייבוא תגים, פרסום גרסה |
| Google Analytics | Analytics Admin API | יצירת GA4 Property + Web Data Stream |

### אופן האימות (OAuth)
- בנינו חיבור OAuth עם חשבון ה-Google של הסוכנות
- ה-token מאוחסן כ-secret מוצפן בסביבת Streamlit Cloud
- האפליקציה מרעננת את ה-token אוטומטית בכל פעם שהיא נטענת
- **ה-scopes (הרשאות) שנדרשו:**
  - `tagmanager.edit.containers`
  - `tagmanager.edit.containerversions`
  - `tagmanager.publish`
  - `analytics.edit`

### ל-GTM account יש ID קבוע
כל ה-containers נוצרים תחת ה-GTM Account של הסוכנות (ID: 6352015198).
**הערה:** GTM API לא מאפשר יצירת accounts — רק containers. ה-account נוצר פעם אחת ידנית.

---

## תהליך ההקמה — שלב אחרי שלב

### שלב 1 — פרטי הלקוח
המשתמש ממלא טופס עם:
- שם הלקוח
- דומיין (ללא https)
- כתובת עמוד תודה לאחר שליחת טופס יצירת קשר
- האם זו חנות eCommerce (WooCommerce)?
- אינטגרציות אופציונליות: Google Ads, Facebook Pixel, Maskyoo

### שלב 2 — בחירת GA4 Account
האפליקציה מושכת אוטומטית את רשימת כל חשבונות ה-GA4 של הסוכנות (15 חשבונות).
המשתמש בוחר לאיזה חשבון ישויך ה-property החדש.
(מגבלת גוגל: עד 100 properties לחשבון)

### שלב 3 — אישור והרצה
סיכום פרטים לבדיקה לפני ההרצה. לחיצה על "Run Setup" מפעילה את כל שרשרת האוטומציה.

### שלב 4 — ביצוע + תוצאות
כל הפעולות רצות ב-30-40 שניות, עם לוג חי על המסך. בסיום מוצגים:
- GTM Container ID (GTM-XXXXXXX)
- GA4 Measurement ID (G-XXXXXXXXXX)
- GA4 Property ID (מספר מלא לשימוש ב-CRM)
- רשימת כל התגים שהוקמו
- קוד HEAD להדבקה מעל `</head>`
- קוד BODY להדבקה אחרי `<body>`

---

## מה האפליקציה עושה מאחורי הקלעים

### פעולות אוטומטיות לפי סדר:

1. **יצירת GTM Container** — שם: הדומיין של הלקוח, platform: Web
2. **יצירת GA4 Property** — שם: שם הלקוח, timezone: Jerusalem, מטבע: ILS
3. **יצירת Web Data Stream** — עם כתובת ה-URL של הלקוח
4. **קריאת קובץ התבנית** (`template.json`) — תבנית התגים שלנו עם PLACEHOLDERs
5. **החלפת PLACEHOLDERs** בערכים האמיתיים של הלקוח
6. **סינון תגים** — הסרת תגים שלא רלוונטיים ללקוח (לפי מה שנבחר)
7. **ייבוא תגים, triggers ו-variables** לתוך ה-workspace
8. **פרסום גרסה** עם תיאור: "Initial setup — שם לקוח — תאריך"
9. **יצירת קודי הטמעה** מוכנים להעתקה

---

## המדריך הפנימי — מקור התבנית

`template.json` הוא קידוד של המדריך הידני שלנו — כל תג, trigger ו-variable שהיינו מגדירים ידנית בכל לקוח, עכשיו מקודד אחת ולתמיד בקובץ JSON אחד.

ה-PLACEHOLDERs שמוגדרים בתבנית:

| Placeholder | מה הוא מחליף |
|---|---|
| `PLACEHOLDER_GA4_ID` | GA4 Measurement ID (G-XXXXXXXXXX) |
| `PLACEHOLDER_STREAM_ID` | GA4 Stream ID (מספר) |
| `PLACEHOLDER_ADS_ID` | Google Ads Conversion ID (AW-XXXXXXXXX) |
| `PLACEHOLDER_PIXEL_ID` | Facebook Pixel ID |
| `PLACEHOLDER_DOMAIN` | דומיין הלקוח |
| `PLACEHOLDER_THANKYOU_URL` | עמוד תודה לאחר שליחת טופס |
| `PLACEHOLDER_MASKYOO_NUMBER` | מספר Maskyoo הוירטואלי |

---

## התגים שמוקמים — רשימה מלאה

### תגים קבועים — נוצרים לכל לקוח תמיד

| שם התג | סוג | מתי מופעל |
|---|---|---|
| GA4 - Configuration | Google Tag | כל עמוד |
| GA4 - Stream ID | Google Tag | כל עמוד |
| Conversion Linker | Conversion Linker | כל עמוד |
| GA4 - Event - page_view | GA4 Event | כל עמוד |
| GA4 - Event - contact_form_submission | GA4 Event | לאחר הגעה לעמוד תודה |
| GA4 - Event - phone_clicks | GA4 Event | לחיצה על מספר טלפון |
| GA4 - Event - wa_clicks | GA4 Event | לחיצה על WhatsApp |

**סה"כ: 7 תגים קבועים**

---

### תגים לחנויות eCommerce — נוספים אם נבחר "eCommerce"

| שם התג | האירוע |
|---|---|
| GA4 - Event - purchase | רכישה |
| GA4 - Event - add_to_cart | הוספה לעגלה |
| GA4 - Event - remove_from_cart | הסרה מהעגלה |
| GA4 - Event - begin_checkout | התחלת תשלום |
| GA4 - Event - view_item | צפייה במוצר |

**+5 תגים eCommerce**

---

### תגים אופציונליים לפי בחירה

| אינטגרציה | תגים שנוצרים |
|---|---|
| Google Ads | Google Ads - Remarketing (כל עמוד) |
| Facebook Pixel | Facebook Pixel - Base (כל עמוד) + Facebook Pixel - Event - purchase (לחנויות) |
| Maskyoo | Maskyoo Script (כל עמוד) — כולל חיבור ל-GA4 |

---

### טריגרים שנוצרים אוטומטית

- Event - purchase
- Event - add_to_cart
- Event - remove_from_cart
- Event - begin_checkout
- Event - view_item
- Thank You Page (Page URL contains עמוד-תודה)
- Phone Click (Link Click on tel:)
- WhatsApp Click (Link Click on wa.me)

---

## תוצר הסופי — מה מקבלים

בסיום הרצה אחת (30-40 שניות):

✅ GTM Container חדש מוגדר ומפורסם — מוכן להטמעה  
✅ GA4 Property חדש עם Web Data Stream  
✅ כל התגים, הטריגרים והמשתנים מוכנים  
✅ גרסה 1 מפורסמת ב-GTM  
✅ קוד HEAD + BODY מוכנים להדבקה ב-WordPress  
✅ כל ה-IDs מוצגים (GTM, GA4 Measurement, GA4 Property)  

**מה נותר ידני עדיין:** הדבקת קודי ה-HTML ב-WordPress (Head & Body).
זה בדיוק מה שנפתר בשלב הבא.

---

## שלב הבא — אוטומציה מלאה על האתרים

### מה חסר כדי לסגור את המעגל

שלב א׳ פתר את צד ה-APIs (GTM + GA4). נותר שלב ב׳: **שתילת הסקריפט על האתר עצמו** — אוטומטית, ללא מגע ידני.

### הפתרון המתוכנן

כל אתרי הסוכנות מאוחסנים על **Cloudways** — פלטפורמת WordPress בענן. לכל שרת יש גישת SSH.

התהליך האוטומטי שנוסיף:

```
בסיום ההגדרה הנוכחית
    ↓
האפליקציה מתחברת ל-Cloudways דרך SSH
    ↓
מריצה WP-CLI על ה-WordPress של הלקוח
    ↓
מוסיפה את קוד GTM+GA4 ל-Head וה-Body
    ↓
מדווחת: "הוטמע בהצלחה"
```

### מה כבר קיים בתשתית

- `sites.json` — קובץ עם רשימת כל האתרים, כתובות שרת, נתיבי WordPress, Application Passwords
- SSH config מוגדר על המחשב (`~/.ssh/config`) עם כינויים: `cloudways-server1`, `cloudways-server2` וכו׳
- WP-CLI מותקן על כל שרת Cloudways
- Application Password מוגדר לכל WordPress (גישת REST API)

### מה צריך לפתח

1. **מודול SSH** — חיבור מהאפליקציה לשרת Cloudways
2. **שתילת הקוד** — שימוש ב-WP-CLI או REST API להוספת הסקריפטים ל-WordPress
3. **בחירת שיטה:** WP-CLI (ישיר, אמין) או Application Password API (ללא SSH)
4. **בדיקת הצלחה** — אימות שהסקריפט אכן נטמע ופועל

### אפשרות נוספת — פלאגין WordPress
במקום SSH, להוסיף integration דרך פלאגין WordPress קיים כמו **Insert Headers and Footers** שמאפשר הוספת קוד ל-Head/Body דרך REST API — ללא צורך ב-SSH כלל.

---

## שאלות ותשובות

**ש: האם האפליקציה מחובר לאינטרנט? מי יכול להשתמש בה?**  
ת: כן, היא פרוסה על Streamlit Cloud ונגישה מכל מקום דרך URL קבוע. מוגנת בסיסמה — רק מי שיודע אותה יכול להיכנס.

**ש: מה קורה אם הלקוח לא צריך eCommerce?**  
ת: כל התגים הקשורים לחנות מסוננים אוטומטית. לא נוצרים triggers של purchase/cart ואין צורך לעשות כלום ידנית.

**ש: האם ניתן לשנות את התבנית?**  
ת: כן. `template.json` הוא הלב של המערכת — כל שינוי שם יחול על כל לקוח חדש מהרגע שינשמר.

**ש: מה אם הלקוח צריך תגים שלא בתבנית?**  
ת: כרגע יש להוסיפם ידנית ב-GTM. בשלב הבא ניתן להרחיב את הטופס ולהוסיף תגים נוספים לתבנית.

**ש: איפה הקוד שמור?**  
ת: ב-GitHub, ב-repository פרטי. Streamlit Cloud קורא משם ישירות ומריץ בענן.

**ש: האם יש גיבוי?**  
ת: Git מספק היסטוריה מלאה של כל שינוי בקוד. ה-token שמור ב-Streamlit Cloud Secrets.

**ש: מה עם אבטחה — מי רואה את ה-credentials?**  
ת: ה-token של גוגל מאוחסן כ-secret מוצפן בסביבת Streamlit. לא מופיע בקוד, לא ב-GitHub, ולא גלוי לאף משתמש. מי שיש לו סיסמה לאפליקציה יכול להשתמש בה, אך לא לראות את ה-credentials.

**ש: כמה זמן לקח לבנות את זה?**  
ת: כשבוע של עבודה עם Claude Code — כולל: הגדרת OAuth, בניית הממשק, debugging של GTM API, בניית template.json, ופריסה ב-Streamlit Cloud.

---

## סיכום — מה הושג

| לפני | אחרי |
|---|---|
| 2-4 שעות עבודה ידנית ללקוח | 30 שניות |
| תלות באדם ספציפי שיודע מה לעשות | כל אחד בצוות יכול להריץ |
| שגיאות ידניות אפשריות | אחיד ועקבי בכל פעם |
| אין תיעוד אוטומטי | IDs ותגים מתועדים בסיום |
| ידני: GTM + GA4 + תגים | אוטומטי מלא: הכל בפעולה אחת |

**הפרויקט הושלם בהצלחה. שלב א׳ — GTM + GA4 — פועל בייצור.**  
**שלב ב׳ — הטמעה אוטומטית על WordPress — מוכן לפיתוח.**
