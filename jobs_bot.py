import os
import requests
import sqlite3
import time
import hashlib
import logging
import threading
import json
from datetime import datetime
from bs4 import BeautifulSoup

# ==================== الإعدادات ====================
BOT_TOKEN = "8615364517:AAG-y4NpcbNpA803DwJVtHBpIca5GfnB_gY"
GEMINI_API_KEY = "AIzaSyA_5I1nCiqa5m5x7pvqQLbcwLf3wpCQ-Bw"
CHANNEL_ID = "@iraqjopsforall"
CHECK_INTERVAL = 3600 
DB_FILE = "iraq_jobs.db"

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging

# ==================== قاعدة البيانات ====================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS posted_jobs 
                 (id TEXT PRIMARY KEY, title TEXT, category TEXT, location TEXT, timestamp DATETIME)''')
    conn.commit()
    conn.close()

def is_posted(job_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT 1 FROM posted_jobs WHERE id=?", (job_id,))
    res = c.fetchone()
    conn.close()
    return res is not None

def mark_posted(job_id, title, category, location):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO posted_jobs VALUES (?, ?, ?, ?, ?)", 
              (job_id, title, category, location, datetime.now()))
    conn.commit()
    conn.close()

# ==================== جلب الوظائف (Scraping) ====================
def fetch_real_jobs(province_ar):
    query = f"وظائف-في-{province_ar.replace(' ', '-')}"
    url = f"https://iraq.tanqeeb.com/ar/s/{query}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.content, 'html.parser')
        items = soup.find_all('div', class_='item')
        
        jobs = []
        for it in items[:5]:
            title_el = it.find('h2')
            link_el = it.find('a')
            if title_el and link_el:
                jobs.append({
                    "title": title_el.get_text(strip=True),
                    "link": "https://iraq.tanqeeb.com" + link_el['href'],
                    "location": province_ar
                })
        return jobs
    except Exception as e:
        log.error(f"Error scraping: {e}")
        return []

# ==================== تحسين الصياغة بـ Gemini ====================
def refine_with_gemini(job):
    prompt = f"صغ هذا الإعلان الوظيفي العراقي بشكل جذاب لقناة تليجرام: {job['title']} في {job['location']}. الرابط: {job['link']}"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    try:
        r = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=20)
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except:
        return f"📍 وظيفة في {job['location']}\n💼 {job['title']}\n🔗 للتقديم: {job['link']}"

# ==================== التليجرام ====================
def send_telegram(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if reply_markup: payload["reply_markup"] = reply_markup
    return requests.post(url, json=payload)

def get_main_keyboard():
    return {
        "keyboard": [[{"text": "📍 البصرة"}, {"text": "📍 بغداد"}], 
                     [{"text": "📍 أربيل"}, {"text": "📍 نينوى"}]],
        "resize_keyboard": True
    }

def handle_message(update):
    if "message" not in update: return
    msg = update["message"]
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")

    if text == "/start":
        welcome_text = "أهلاً بك يا حيدر. تم تحديث البوت لجلب وظائف حقيقية."
        send_telegram(chat_id, welcome_text, get_main_keyboard())
    
    elif text.startswith("📍"):
        province = text.replace("📍 ", "")
        send_telegram(chat_id, f"🔎 جاري البحث في {province}...")
        jobs = fetch_real_jobs(province)
        if not jobs:
            send_telegram(chat_id, "لا توجد وظائف جديدة حالياً.")
        else:
            for j in jobs:
                post = refine_with_gemini(j)
                send_telegram(chat_id, post)
                send_telegram(CHANNEL_ID, post)

# ==================== التشغيل ====================
def auto_post_loop():
    while True:
        for prov in ["البصرة", "بغداد", "أربيل", "نينوى"]:
            jobs = fetch_real_jobs(prov)
            for j in jobs:
                job_id = hashlib.md5(j['link'].encode()).hexdigest()
                if not is_posted(job_id):
                    msg = refine_with_gemini(j)
                    send_telegram(CHANNEL_ID, msg)
                    mark_posted(job_id, j['title'], "عام", prov)
                    time.sleep(10)
        time.sleep(CHECK_INTERVAL)

def get_updates(offset):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}&timeout=30"
    try: return requests.get(url).json().get("result", [])
    except: return []

if __name__ == "__main__":
    init_db()
    threading.Thread(target=auto_post_loop, daemon=True).start()
    offset = 0
    while True:
        updates = get_updates(offset)
        for up in updates:
            offset = up["update_id"] + 1
            handle_message(up)
        time.sleep(1)
