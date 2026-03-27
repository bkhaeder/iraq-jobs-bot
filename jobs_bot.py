#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Iraq Jobs & Career Tips Bot - نسخة تعليمية ومعلوماتية للشباب الباحثين عن عمل
- نشر نصائح كتابة CV
- نصائح مقابلات
- معلومات تقنية
- تعليم AI
- تحفيز وإيجابية
- أخبار تقنية طريفة
"""

import os
import re
import json
import time
import hashlib
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ==================== الإعدادات ====================
TOKEN = "AIzaSyA_5I1nCiqa5m5x7pvqQLbcwLf3wpCQ-Bw"  # توكن بوتك
CHANNEL_ID = "@iraq_career_tips"  # عدل باسم قناتك
GEMINI_API_KEY = "AIzaSyA_5I1nCiqa5m5x7pvqQLbcwLf3wpCQ-Bw"  # Gemini API
CHECK_INTERVALS = [60, 300, 600, 900, 1800]  # ثانية: 1د،5د،10د،15د،30د
DB_FILE = "career_bot.db"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("bot.log", encoding="utf-8"), logging.StreamHandler()],
)
log = logging.getLogger(__name__)
paused = False
current_interval = 900  # 15 دقيقة افتراضي
days_to_run = 30  # عدد أيام النشر التلقائي

TOPICS = [
    "سيفي",
    "نصائح مقابلات",
    "معلومات تقنية",
    "نصائح تعليم ai",
    "نصائح تحفيز وايجابية"
]

# ==================== الجلسة ====================
def _build_session() -> requests.Session:
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"]
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": "IraqCareerBot/1.0"})
    return session

HTTP = _build_session()

# ==================== قاعدة البيانات ====================
def init_db() -> None:
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""CREATE TABLE IF NOT EXISTS posted_posts (
        id TEXT PRIMARY KEY,
        topic TEXT,
        content TEXT,
        posted_at TEXT
    )""")
    conn.commit()
    conn.close()

def is_posted(content: str) -> bool:
    key = hashlib.md5(content.encode("utf-8")).hexdigest()
    conn = sqlite3.connect(DB_FILE)
    cur = conn.execute("SELECT 1 FROM posted_posts WHERE id=?", (key,))
    result = cur.fetchone()
    conn.close()
    return result is not None

def mark_posted(content: str, topic: str) -> None:
    key = hashlib.md5(content.encode("utf-8")).hexdigest()
    conn = sqlite3.connect(DB_FILE)
    conn.execute("INSERT OR IGNORE INTO posted_posts VALUES (?, ?, ?, ?)",
                 (key, topic, content, datetime.now(timezone.utc).isoformat()))
    conn.commit()
    conn.close()

# ==================== تيليغرام ====================
def tg_api(method: str, payload: Dict[str, Any], timeout: int = 20) -> Optional[Dict[str, Any]]:
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    try:
        r = HTTP.post(url, json=payload, timeout=timeout)
        if r.status_code == 200:
            return r.json()
        log.error("Telegram %s failed: %s", method, r.text[:200])
    except Exception as e:
        log.error("Telegram %s exception: %s", method, e)
    return None

def send_message(chat_id: int, text: str, reply_markup: Optional[Dict[str, Any]] = None) -> None:
    payload: Dict[str, Any] = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    tg_api("sendMessage", payload)

def send_to_channel(text: str) -> bool:
    payload = {"chat_id": CHANNEL_ID, "text": text, "parse_mode": "HTML"}
    resp = tg_api("sendMessage", payload)
    return bool(resp and resp.get("ok"))

# ==================== أزرار التحكم ====================
def topics_keyboard() -> Dict[str, Any]:
    keyboard = [[{"text": t, "callback_data": f"topic:{t}"}] for t in TOPICS]
    keyboard.append([{"text": "📝 نشر جميع المواضيع", "callback_data": "topic:all"}])
    keyboard.append([{"text": "⏱ دقيقة", "callback_data": "interval:60"},
                     {"text": "⏱ 5 دقائق", "callback_data": "interval:300"},
                     {"text": "⏱ 10 دقائق", "callback_data": "interval:600"},
                     {"text": "⏱ 15 دقائق", "callback_data": "interval:900"},
                     {"text": "⏱ 30 دقائق", "callback_data": "interval:1800"}])
    return {"inline_keyboard": keyboard}

# ==================== توليد المحتوى عبر Gemini ====================
def generate_content(topic: str) -> str:
    prompt = f"اكتب نصيحة قصيرة ولطيفة للشباب العراقي حول: {topic}. باللهجة العراقية، مختصرة، مشوقة، غير مملة."
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.3}}
    try:
        r = HTTP.post(url, json=payload, timeout=20)
        if r.status_code == 200:
            text = r.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return text.strip()
    except Exception as e:
        log.error("Gemini error: %s", e)
    return ""

# ==================== نشر تلقائي ====================
def auto_post():
    global paused
    posts_today = 0
    max_posts = days_to_run * (24*60*60 // current_interval)
    while posts_today < max_posts:
        if not paused:
            topic = TOPICS[posts_today % len(TOPICS)]
            if topic == "all":
                for t in TOPICS:
                    content = generate_content(t)
                    if content and not is_posted(content):
                        send_to_channel(content)
                        mark_posted(content, t)
            else:
                content = generate_content(topic)
                if content and not is_posted(content):
                    send_to_channel(content)
                    mark_posted(content, topic)
            posts_today += 1
        time.sleep(current_interval)

# ==================== تشغيل البوت ====================
if __name__ == "__main__":
    init_db()
    threading.Thread(target=auto_post, daemon=True).start()
    log.info("Bot is running... استخدم لوحة التحكم لإيقاف/تشغيل النشر.")
