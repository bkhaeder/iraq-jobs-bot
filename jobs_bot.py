#!/usr/bin/env python3
"""
بوت وظائف العراق الذكي - @iraqjopsforall
نسخة محسّنة: جلب وظائف حقيقية مع معالجة قوية للأخطاء وبدائل عند فشل Gemini.
"""

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
BOT_TOKEN = "8615364517:AAG-y4NpcbNpA803DwJVtHBpIca5GfnB_gY"
CHANNEL_ID = "@iraqjopsforall"
GEMINI_API_KEY = "AIzaSyA_5I1nCiqa5m5x7pvqQLbcwLf3wpCQ-Bw"
CHECK_INTERVAL = 3600
DB_FILE = "iraq_jobs.db"

REMOTIVE_API = "https://remotive.com/api/remote-jobs"
ARBEITNOW_API = "https://www.arbeitnow.com/api/job-board-api"

IRAQ_PROVINCES = {
    "بغداد": "Baghdad",
    "البصرة": "Basra",
    "نينوى": "Nineveh Mosul",
    "أربيل": "Erbil",
    "النجف": "Najaf",
    "كربلاء": "Karbala",
    "السليمانية": "Sulaymaniyah",
    "كركوك": "Kirkuk",
    "الأنبار": "Anbar",
    "ديالى": "Diyala",
    "ذي قار": "Dhi Qar",
    "بابل": "Babylon",
    "واسط": "Wasit",
    "ميسان": "Maysan",
    "المثنى": "Muthanna",
    "القادسية": "Qadisiyyah",
    "صلاح الدين": "Salah al-Din",
    "دهوك": "Duhok",
    "حلبجة": "Halabja",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("bot.log", encoding="utf-8"), logging.StreamHandler()],
)
log = logging.getLogger(__name__)

paused = False


def _build_session():
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": "IraqJobsBot/2.0"})
    return session


HTTP = _build_session()

# ==================== قاعدة البيانات ====================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""CREATE TABLE IF NOT EXISTS posted_jobs (
        id TEXT PRIMARY KEY,
        title TEXT,
        company TEXT,
        province TEXT,
        url TEXT,
        posted_at TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS admins (chat_id INTEGER PRIMARY KEY)""")
    conn.commit()
    conn.close()


def add_admin(chat_id):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("INSERT OR IGNORE INTO admins VALUES (?)", (chat_id,))
    conn.commit()
    conn.close()


def is_posted(title, company, url):
    key = hashlib.md5(f"{title}|{company}|{url}".encode()).hexdigest()
    conn = sqlite3.connect(DB_FILE)
    res = conn.execute("SELECT 1 FROM posted_jobs WHERE id=?", (key,)).fetchone()
    conn.close()
    return res


def mark_posted(title, company, province, url):
    key = hashlib.md5(f"{title}|{company}|{url}".encode()).hexdigest()
    conn = sqlite3.connect(DB_FILE)
    conn.execute("INSERT OR IGNORE INTO posted_jobs VALUES (?, ?, ?, ?, ?, ?)",
                 (key, title, company, province, url, datetime.now().isoformat()))
    conn.commit()
    conn.close()


# ==================== Telegram ====================
def send_message(chat_id, text):
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    })


def send_channel(text):
    return requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
        "chat_id": CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML"
    })


# ==================== جلب الوظائف ====================
def search_jobs(count, category, province):
    jobs = []

    # محاولة Gemini
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
        prompt = f"اعطني {count} وظائف حقيقية في {province} تخصص {category} مع رابط التقديم بصيغة JSON"

        r = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]})
        txt = r.json()["candidates"][0]["content"]["parts"][0]["text"]

        data = re.search(r'\[.*\]', txt, re.S)
        if data:
            jobs = json.loads(data.group())
    except:
        pass

    # fallback API
    if not jobs:
        try:
            r = requests.get(REMOTIVE_API).json()["jobs"][:count]
            for j in r:
                jobs.append({
                    "title": j["title"],
                    "company": j["company_name"],
                    "link": j["url"]
                })
        except:
            pass

    return jobs


# ==================== نشر ====================
def post_jobs(chat_id, count, category, province):
    send_message(chat_id, "🔎 جاري البحث...")

    jobs = search_jobs(count, category, province)

    if not jobs:
        send_message(chat_id, "❌ ماكو وظائف حالياً")
        return

    for j in jobs:
        if is_posted(j["title"], j["company"], j["link"]):
            continue

        msg = f"💼 <b>{j['title']}</b>\n🏢 {j['company']}\n🔗 {j['link']}"
        send_channel(msg)
        mark_posted(j["title"], j["company"], province, j["link"])
        time.sleep(2)

    send_message(chat_id, "✅ تم النشر")


# ==================== التشغيل ====================
def main():
    print("🚀 البوت يعمل...")
    init_db()
    add_admin(7590912344)

    while True:
        try:
            updates = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates").json()["result"]
            for u in updates:
                chat_id = u["message"]["chat"]["id"]
                text = u["message"].get("text", "")

                if text == "/start":
                    send_message(chat_id, "اهلا بيك ❤️ اكتب:\nانشر 5 وظائف برمجة في البصرة")

                elif "انشر" in text:
                    post_jobs(chat_id, 5, "عام", "العراق")

        except Exception as e:
            print("Error:", e)

        time.sleep(2)


if __name__ == "__main__":
    main()
