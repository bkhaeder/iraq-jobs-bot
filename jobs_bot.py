#!/usr/bin/env python3
"""
بوت قناة نصائح للشباب الباحثين عن عمل - @iraq_job_tips
نسخة محسّنة: نشر تلقائي مستمر، مواضيع متعددة، Gemini API
"""

import os
import json
import time
import hashlib
import logging
import sqlite3
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ==================== إعدادات المستخدم ====================
BOT_TOKEN = "8615364517:AAG-y4NpcbNpA803DwJVtHBpIca5GfnB_gY  # ضع توكن البوت هنا
CHANNEL_ID = "@iraq_job_tips"          # قناة التليغرام
GEMINI_API_KEY = "AIzaSyA_5I1nCiqa5m5x7pvqQLbcwLf3wpCQ-Bw"  # Gemini API
DB_FILE = "iraq_tips.db"

# أوقات النشر بالدقائق
POST_INTERVALS = [1, 5, 10, 15, 30]

# المواضيع المتاحة
TOPICS = [
    "سيفي",
    "نصائح مقابلات",
    "معلومات تقنية",
    "نصائح تعليم AI",
    "تحفيز وإيجابية",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("bot.log", encoding="utf-8"), logging.StreamHandler()],
)
log = logging.getLogger(__name__)

paused = False
auto_thread: Optional[threading.Thread] = None

# ==================== إعداد جلسة HTTP ====================
def _build_session() -> requests.Session:
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": "IraqJobTipsBot/2.0"})
    return session

HTTP = _build_session()

# ==================== قاعدة البيانات ====================
def init_db() -> None:
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS posted_content (
            id TEXT PRIMARY KEY,
            topic TEXT,
            posted_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def is_posted(text_id: str) -> bool:
    conn = sqlite3.connect(DB_FILE)
    cur = conn.execute("SELECT 1 FROM posted_content WHERE id=?", (text_id,))
    result = cur.fetchone()
    conn.close()
    return result is not None

def mark_posted(text_id: str, topic: str) -> None:
    conn = sqlite3.connect(DB_FILE)
    conn.execute(
        "INSERT OR IGNORE INTO posted_content VALUES (?, ?, ?)",
        (text_id, topic, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

# ==================== Telegram API ====================
def tg_api(method: str, payload: Dict[str, Any], timeout: int = 20) -> Optional[Dict[str, Any]]:
    if not BOT_TOKEN:
        log.error("BOT_TOKEN غير مضبوط")
        return None
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    try:
        r = HTTP.post(url, json=payload, timeout=timeout)
        if r.status_code == 200:
            return r.json()
        log.error("Telegram %s failed: %s - %s", method, r.status_code, r.text[:200])
    except Exception as e:
        log.error("Telegram %s exception: %s", method, e)
    return None

def send_message(chat_id: int, text: str) -> None:
    tg_api("sendMessage", {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True})

def send_to_channel(text: str) -> bool:
    resp = tg_api("sendMessage", {"chat_id": CHANNEL_ID, "text": text, "parse_mode": "HTML"})
    return bool(resp and resp.get("ok"))

# ==================== Gemini API ====================
def generate_content(topic: str) -> str:
    prompt = f"اكتب نصائح قصيرة وبسيطة باللهجة العراقية حول الموضوع: {topic}. اجعله مشوق، مفيد، غير مكرر."
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2}
    }
    try:
        r = HTTP.post(url, json=payload, timeout=25)
        if r.status_code == 200:
            text = r.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return text.strip()
        log.error("Gemini failed: %s %s", r.status_code, r.text[:200])
    except Exception as e:
        log.error("Gemini exception: %s", e)
    return f"⚠️ لم أتمكن من توليد محتوى لـ {topic} حالياً."

# ==================== تنسيق الرسالة ====================
def format_post(topic: str) -> str:
    content = generate_content(topic)
    text_id = hashlib.md5(content.encode("utf-8")).hexdigest()
    if is_posted(text_id):
        return ""  # تم النشر سابقًا
    mark_posted(text_id, topic)
    hashtags = f"#نصائح_شباب #البحث_عن_عمل #{topic.replace(' ', '_')}"
    return f"💡 <b>{topic}</b>\n\n{content}\n\n{hashtags}\n━━━━━━━━━━━━\n📢 {CHANNEL_ID}"

# ==================== نشر تلقائي ====================
def auto_post(interval: int, days: int, selected_topics: List[str]):
    global paused
    end_time = datetime.now() + timedelta(days=days)
    while datetime.now() < end_time:
        if not paused:
            for topic in selected_topics:
                msg = format_post(topic)
                if msg:
                    send_to_channel(msg)
        time.sleep(interval * 60)

# ==================== أوامر التحكم ====================
def start_auto(interval: int = 5, days: int = 1, topics: Optional[List[str]] = None):
    global auto_thread
    if topics is None:
        topics = TOPICS
    thread = threading.Thread(target=auto_post, args=(interval, days, topics))
    thread.daemon = True
    thread.start()
    auto_thread = thread
    send_message(123456789, f"✅ بدء النشر التلقائي كل {interval} دقيقة/دقائق لمدة {days} يوم/أيام.")

def pause_auto():
    global paused
    paused = True
    send_message(123456789, "⏸️ تم إيقاف النشر التلقائي مؤقتًا.")

def resume_auto():
    global paused
    paused = False
    send_message(123456789, "▶️ تم استئناف النشر التلقائي.")

# ==================== MAIN ====================
if __name__ == "__main__":
    init_db()
    # مثال: تشغيل النشر التلقائي كل 5 دقائق لمدة 2 يوم لجميع المواضيع
    start_auto(interval=5, days=2, topics=TOPICS)
    while True:
        time.sleep(60)
