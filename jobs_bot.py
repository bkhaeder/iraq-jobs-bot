#!/usr/bin/env python3
"""
بوت وظائف ذكي - @iraqjopsforall
- ينشر وظائف تلقائياً كل ساعة
- يفهم أوامرك بالعربية ويجيب عليها
- مدعوم بـ Google Gemini AI
"""

import feedparser
import requests
import sqlite3
import time
import hashlib
import logging
import threading
import json
import re
from datetime import datetime

# ==================== الإعدادات ====================
BOT_TOKEN = "8615364517:AAG-y4NpcbNpA803DwJVtHBpIca5GfnB_gY"
CHANNEL_ID = "@iraqjopsforall"
GEMINI_API_KEY = "AIzaSyA_5I1nCiqa5m5x7pvqQLbcwLf3wpCQ-Bw"
CHECK_INTERVAL = 3600  # كل ساعة
DB_FILE = "posted_jobs.db"
ADMIN_IDS = []

# ==================== مصادر RSS ====================
RSS_FEEDS = [
    {"name": "Indeed العراق", "url": "https://www.indeed.com/rss?q=&l=Iraq&lang=ar"},
    {"name": "Indeed السعودية", "url": "https://www.indeed.com/rss?q=&l=Saudi+Arabia&lang=ar"},
    {"name": "Wuzzuf", "url": "https://wuzzuf.net/search/jobs/feed?q=&l="},
    {"name": "Bayt العراق", "url": "https://www.bayt.com/ar/iraq/jobs/?via=rss"},
    {"name": "Bayt الخليج", "url": "https://www.bayt.com/ar/uae/jobs/?via=rss"},
]

# ==================== السجلات ====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# ==================== قاعدة البيانات ====================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS posted_jobs (
            id TEXT PRIMARY KEY,
            title TEXT,
            category TEXT,
            location TEXT,
            posted_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            chat_id INTEGER PRIMARY KEY
        )
    """)
    conn.commit()
    conn.close()

def is_posted(job_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.execute("SELECT 1 FROM posted_jobs WHERE id = ?", (job_id,))
    result = cur.fetchone()
    conn.close()
    return result is not None

def mark_posted(job_id, title, category="", location=""):
    conn = sqlite3.connect(DB_FILE)
    conn.execute(
        "INSERT OR IGNORE INTO posted_jobs (id, title, category, location, posted_at) VALUES (?, ?, ?, ?, ?)",
        (job_id, title, category, location, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def add_admin(chat_id):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("INSERT OR IGNORE INTO admins (chat_id) VALUES (?)", (chat_id,))
    conn.commit()
    conn.close()
    if chat_id not in ADMIN_IDS:
        ADMIN_IDS.append(chat_id)

def get_admins():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.execute("SELECT chat_id FROM admins")
    result = [row[0] for row in cur.fetchall()]
    conn.close()
    return result

# ==================== تيليغرام ====================
def send_message(chat_id, text, parse_mode="HTML"):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    try:
        r = requests.post(url, json=payload, timeout=15)
        return r.status_code == 200
    except Exception as e:
        log.error(f"خطأ إرسال: {e}")
        return False

def send_to_channel(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        r = requests.post(url, json=payload, timeout=15)
        return r.status_code == 200
    except Exception as e:
        log.error(f"خطأ قناة: {e}")
        return False

def get_updates(offset=0):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    try:
        r = requests.get(url, params={"offset": offset, "timeout": 30}, timeout=35)
        if r.status_code == 200:
            return r.json().get("result", [])
    except:
        pass
    return []

# ==================== Gemini AI ====================
def ask_gemini(user_message):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

    system_prompt = """أنت مساعد ذكي لإدارة قناة وظائف على تيليغرام اسمها @iraqjopsforall.
مهمتك فهم أوامر المدير والرد عليها.

عندما يطلب نشر وظائف، أجب بـ JSON فقط:
{"action": "post_jobs", "count": 5, "category": "تسويق", "location": "البصرة"}

عندما يسأل عن الإحصائيات:
{"action": "stats"}

عندما يريد إيقاف النشر التلقائي:
{"action": "pause"}

عندما يريد تشغيل النشر التلقائي:
{"action": "resume"}

عندما يسأل سؤالاً عادياً، أجب بنص عربي طبيعي ومختصر وودي.
لا تضف أي شرح إضافي مع JSON."""

    payload = {
        "contents": [
            {"parts": [{"text": system_prompt + "\n\nرسالة المدير: " + user_message}]}
        ]
    }

    try:
        r = requests.post(url, json=payload, timeout=20)
        if r.status_code == 200:
            data = r.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        log.error(f"خطأ Gemini: {e}")
    return None

# ==================== جلب وظائف مفلترة ====================
def fetch_jobs_filtered(count=10, category="", location=""):
    results = []
    category_translations = {
        "تسويق": "marketing", "محاسبة": "accounting", "هندسة": "engineering",
        "تقنية": "technology it", "طب": "medical doctor", "تعليم": "education teacher",
        "مبيعات": "sales", "موارد بشرية": "hr human resources", "تصميم": "design",
        "برمجة": "programming developer software",
    }
    location_translations = {
        "البصرة": "basra", "بغداد": "baghdad", "أربيل": "erbil",
        "الموصل": "mosul", "السليمانية": "sulaymaniyah", "العراق": "iraq",
    }

    for feed_info in RSS_FEEDS:
        if len(results) >= count:
            break
        try:
            feed = feedparser.parse(feed_info["url"])
            for entry in feed.entries:
                if len(results) >= count:
                    break

                title = entry.get("title", "").lower()
                summary = entry.get("summary", "").lower()
                content = title + " " + summary

                # فلترة التخصص
                if category:
                    cat_ar = category.lower()
                    cat_en = category_translations.get(category, "")
                    if cat_ar not in content and not any(w in content for w in cat_en.split()):
                        continue

                # فلترة الموقع
                if location:
                    loc_ar = location.lower()
                    loc_en = location_translations.get(location, "")
                    if loc_ar not in content and loc_en and loc_en not in content:
                        continue

                results.append({
                    "title": entry.get("title", "وظيفة جديدة"),
                    "link": entry.get("link", ""),
                    "summary": entry.get("summary", ""),
                    "source": feed_info["name"],
                })
        except Exception as e:
            log.error(f"خطأ RSS {feed_info['name']}: {e}")

    return results[:count]

def format_job(job, category="", location=""):
    title = job["title"].strip()
    link = job["link"].strip()
    summary = re.sub(r"<[^>]+>", "", job.get("summary", "")).strip()
    if len(summary) > 250:
        summary = summary[:250] + "..."

    tags = ""
    if category:
        tags += f"#{category.replace(' ', '_')} "
    if location:
        tags += f"#{location.replace(' ', '_')}"

    msg = f"💼 <b>{title}</b>\n\n📌 <b>المصدر:</b> {job['source']}"
    if summary:
        msg += f"\n📝 {summary}"
    if tags:
        msg += f"\n\n🏷 {tags}"
    msg += f"\n\n🔗 <a href=\"{link}\">اضغط للتقديم</a>\n\n━━━━━━━━━━━━━━━\n📢 @iraqjopsforall"
    return msg

# ==================== تنفيذ الأوامر ====================
paused = False

def handle_action(action_data, chat_id):
    global paused
    action = action_data.get("action")

    if action == "post_jobs":
        count = int(action_data.get("count", 5))
        category = action_data.get("category", "")
        location = action_data.get("location", "")

        send_message(chat_id, f"⏳ جاري البحث عن {count} وظيفة {category} {location}...")
        jobs = fetch_jobs_filtered(count, category, location)

        if not jobs:
            send_message(chat_id, "❌ لم أجد وظائف تطابق طلبك. جرب تخصص أو موقع مختلف.")
            return

        send_message(chat_id, f"✅ وجدت {len(jobs)} وظيفة، جاري النشر...")
        posted = 0
        for job in jobs:
            msg = format_job(job, category, location)
            if send_to_channel(msg):
                job_id = hashlib.md5((job["link"] + job["title"]).encode()).hexdigest()
                mark_posted(job_id, job["title"], category, location)
                posted += 1
                time.sleep(2)

        send_message(chat_id, f"🎉 تم نشر {posted} وظيفة على @iraqjopsforall!")

    elif action == "stats":
        conn = sqlite3.connect(DB_FILE)
        total = conn.execute("SELECT COUNT(*) FROM posted_jobs").fetchone()[0]
        today = conn.execute("SELECT COUNT(*) FROM posted_jobs WHERE posted_at >= date('now')").fetchone()[0]
        conn.close()
        send_message(chat_id, f"""📊 <b>إحصائيات القناة</b>

📌 إجمالي الوظائف المنشورة: <b>{total}</b>
📅 منشورة اليوم: <b>{today}</b>
⏰ التحديث: كل ساعة تلقائياً
📢 @iraqjopsforall""")

    elif action == "pause":
        paused = True
        send_message(chat_id, "⏸ تم إيقاف النشر التلقائي مؤقتاً.")

    elif action == "resume":
        paused = False
        send_message(chat_id, "▶️ تم استئناف النشر التلقائي!")

# ==================== معالجة الرسائل ====================
def handle_message(update):
    msg = update.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    text = msg.get("text", "").strip()

    if not chat_id or not text:
        return

    add_admin(chat_id)
    log.info(f"رسالة من {chat_id}: {text}")

    if text == "/start":
        send_message(chat_id, """👋 <b>أهلاً! أنا بوت وظائف @iraqjopsforall الذكي 🤖</b>

يمكنك أن تطلب مني:
• "انشر 10 وظائف تسويق في البصرة"
• "انشر 5 وظائف هندسة في بغداد"
• "كم وظيفة نشرنا اليوم؟"
• "أوقف النشر التلقائي"
• "شغّل النشر التلقائي"

أو اسألني أي شيء! 😊""")
        return

    send_message(chat_id, "🤔 جاري التفكير...")
    response = ask_gemini(text)

    if not response:
        send_message(chat_id, "❌ حدث خطأ، حاول مرة أخرى.")
        return

    # هل الرد JSON أمر؟
    try:
        clean = response.strip().replace("```json", "").replace("```", "").strip()
        action_data = json.loads(clean)
        if "action" in action_data:
            handle_action(action_data, chat_id)
            return
    except:
        pass

    send_message(chat_id, response)

# ==================== النشر التلقائي ====================
def auto_post_loop():
    global paused
    while True:
        time.sleep(CHECK_INTERVAL)
        if paused:
            continue

        log.info("🔄 دورة نشر تلقائي...")
        total = 0
        for feed_info in RSS_FEEDS:
            try:
                feed = feedparser.parse(feed_info["url"])
                for entry in feed.entries[:5]:
                    title = entry.get("title", "")
                    link = entry.get("link", "")
                    job_id = hashlib.md5((link + title).encode()).hexdigest()
                    if is_posted(job_id):
                        continue
                    job = {"title": title, "link": link, "summary": entry.get("summary", ""), "source": feed_info["name"]}
                    if send_to_channel(format_job(job)):
                        mark_posted(job_id, title)
                        total += 1
                        time.sleep(3)
            except Exception as e:
                log.error(f"خطأ {feed_info['name']}: {e}")

        log.info(f"✅ نُشرت {total} وظيفة تلقائياً")
        for admin in get_admins():
            send_message(admin, f"📢 النشر التلقائي: {total} وظيفة جديدة على @iraqjopsforall")

# ==================== الحلقة الرئيسية ====================
def polling_loop():
    offset = 0
    log.info("👂 بدء الاستماع...")
    while True:
        updates = get_updates(offset)
        for update in updates:
            offset = update["update_id"] + 1
            try:
                handle_message(update)
            except Exception as e:
                log.error(f"خطأ: {e}")
        time.sleep(1)

def main():
    log.info("🚀 تشغيل البوت الذكي...")
    init_db()
    send_to_channel("🤖 <b>البوت الذكي يعمل الآن!</b>\nأرسل لي رسالة خاصة لإدارة القناة 💼")
    threading.Thread(target=auto_post_loop, daemon=True).start()
    polling_loop()

if __name__ == "__main__":
    main()
