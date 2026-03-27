#!/usr/bin/env python3
"""
بوت وظائف تلكرام - Iraq Jobs For All
يجمع وظائف من مواقع عربية عبر RSS وينشرها تلقائياً
"""

import feedparser
import requests
import sqlite3
import time
import hashlib
import logging
from datetime import datetime

# ==================== الإعدادات ====================
BOT_TOKEN = "8615364517:AAG-y4NpcbNpA803DwJVtHBpIca5GfnB_gY"
CHANNEL_ID = "@iraqjopsforall"
CHECK_INTERVAL = 3600  # كل ساعة (بالثواني)
DB_FILE = "posted_jobs.db"

# ==================== مصادر RSS ====================
RSS_FEEDS = [
    {
        "name": "Indeed العربية - العراق",
        "url": "https://www.indeed.com/rss?q=&l=Iraq&lang=ar",
    },
    {
        "name": "Indeed العربية - السعودية",
        "url": "https://www.indeed.com/rss?q=&l=Saudi+Arabia&lang=ar",
    },
    {
        "name": "Wuzzuf",
        "url": "https://wuzzuf.net/search/jobs/feed?q=&l=",
    },
    {
        "name": "Bayt - العراق",
        "url": "https://www.bayt.com/ar/iraq/jobs/?via=rss",
    },
    {
        "name": "Bayt - الخليج",
        "url": "https://www.bayt.com/ar/uae/jobs/?via=rss",
    },
]

# ==================== تهيئة السجلات ====================
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
            posted_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def is_posted(job_id: str) -> bool:
    conn = sqlite3.connect(DB_FILE)
    cur = conn.execute("SELECT 1 FROM posted_jobs WHERE id = ?", (job_id,))
    result = cur.fetchone()
    conn.close()
    return result is not None

def mark_posted(job_id: str, title: str):
    conn = sqlite3.connect(DB_FILE)
    conn.execute(
        "INSERT OR IGNORE INTO posted_jobs (id, title, posted_at) VALUES (?, ?, ?)",
        (job_id, title, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

# ==================== إرسال تيليغرام ====================
def send_telegram(text: str) -> bool:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        r = requests.post(url, json=payload, timeout=15)
        if r.status_code == 200:
            return True
        else:
            log.error(f"خطأ تيليغرام: {r.status_code} - {r.text}")
            return False
    except Exception as e:
        log.error(f"فشل الإرسال: {e}")
        return False

# ==================== تنسيق الرسالة ====================
def format_job(entry, source_name: str) -> str:
    title = entry.get("title", "وظيفة جديدة").strip()
    link = entry.get("link", "").strip()
    summary = entry.get("summary", "").strip()

    # تنظيف الملخص
    if summary:
        # حذف HTML tags بسيط
        import re
        summary = re.sub(r"<[^>]+>", "", summary)
        summary = summary[:300] + "..." if len(summary) > 300 else summary

    msg = f"""💼 <b>{title}</b>

📌 <b>المصدر:</b> {source_name}
"""
    if summary:
        msg += f"\n📝 {summary}\n"

    msg += f"""
🔗 <a href="{link}">اضغط للتقديم</a>

━━━━━━━━━━━━━━━
📢 @iraqjopsforall
"""
    return msg

# ==================== معالجة الـ RSS ====================
def process_feed(feed_info: dict) -> int:
    name = feed_info["name"]
    url = feed_info["url"]
    count = 0

    log.info(f"🔍 جاري فحص: {name}")
    try:
        feed = feedparser.parse(url)
        if not feed.entries:
            log.warning(f"لا توجد وظائف في: {name}")
            return 0

        for entry in feed.entries[:10]:  # أقصى 10 وظائف لكل مصدر
            link = entry.get("link", "")
            title = entry.get("title", "")

            # توليد معرف فريد
            job_id = hashlib.md5((link + title).encode()).hexdigest()

            if is_posted(job_id):
                continue

            msg = format_job(entry, name)
            if send_telegram(msg):
                mark_posted(job_id, title)
                count += 1
                log.info(f"✅ نُشرت: {title[:50]}")
                time.sleep(3)  # تأخير بين المنشورات
            else:
                log.warning(f"❌ فشل نشر: {title[:50]}")

    except Exception as e:
        log.error(f"خطأ في {name}: {e}")

    return count

# ==================== الحلقة الرئيسية ====================
def main():
    log.info("🚀 بدء تشغيل بوت الوظائف...")
    init_db()

    # رسالة بدء التشغيل
    send_telegram("🤖 <b>البوت يعمل الآن!</b>\nسيتم نشر الوظائف الجديدة تلقائياً كل ساعة ⏰")

    while True:
        log.info("=" * 40)
        log.info(f"🕐 دورة جديدة: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        total = 0
        for feed in RSS_FEEDS:
            total += process_feed(feed)
            time.sleep(2)

        log.info(f"✨ انتهت الدورة - نُشرت {total} وظيفة جديدة")
        log.info(f"💤 انتظار {CHECK_INTERVAL//60} دقيقة...")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
