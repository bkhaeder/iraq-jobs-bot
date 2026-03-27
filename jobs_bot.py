import requests
import sqlite3
import time
import hashlib
import logging
import threading
import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# ==================== الإعدادات المؤكدة ====================
BOT_TOKEN = "8615364517:AAG-y4NpcbNpA803DwJVtHBpIca5GfnB_gY"
GEMINI_API_KEY = "AIzaSyA_5I1nCiqa5m5x7pvqQLbcwLf3wpCQ-Bw"
CHANNEL_ID = "@iraqjopsforall"
ADMIN_ID = 7590912344

# مخزن مؤقت لحالات المستخدم (State Machine)
USER_STATE = {}

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# ==================== قاعدة البيانات ====================
def init_db():
    conn = sqlite3.connect("iraq_jobs.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS posted_jobs (id TEXT PRIMARY KEY, title TEXT, timestamp DATETIME)''')
    c.execute('''CREATE TABLE IF NOT EXISTS schedule (id INTEGER PRIMARY KEY AUTO_INCREMENT, content TEXT, publish_time DATETIME, status TEXT DEFAULT 'pending')''')
    conn.commit()
    conn.close()

def is_posted(job_id):
    conn = sqlite3.connect("iraq_jobs.db")
    c = conn.cursor()
    c.execute("SELECT 1 FROM posted_jobs WHERE id=?", (job_id,))
    res = c.fetchone()
    conn.close()
    return res is not None

# ==================== جلب البيانات الذكي ====================
def fetch_jobs(province, sector, limit=5):
    query = f"{sector} في {province}"
    url = f"https://iraq.tanqeeb.com/ar/s/{query.replace(' ', '-')}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.content, 'html.parser')
        items = soup.find_all('div', class_='item')
        results = []
        for it in items[:limit]:
            title = it.find('h2').get_text(strip=True) if it.find('h2') else ""
            link = it.find('a')['href'] if it.find('a') else ""
            if title and link:
                if not link.startswith('http'): link = "https://iraq.tanqeeb.com" + link
                results.append({"title": title, "link": link, "prov": province, "sect": sector})
        return results
    except: return []

def ai_refine(job):
    prompt = f"صغ إعلان وظيفي عراقي جذاب: {job['title']} في {job['prov']}. القسم: {job['sect']}. الرابط: {job['link']}"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    try:
        r = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=15)
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except: return f"💼 {job['title']}\n📍 {job['prov']}\n🔗 {job['link']}"

# ==================== الأزرار المرحلية ====================
def send_m(chat_id, text, markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown", "reply_markup": markup}
    return requests.post(url, json=payload)

def kb_provinces():
    return {"keyboard": [[{"text": "📍 البصرة"}, {"text": "📍 بغداد"}], [{"text": "📍 أربيل"}, {"text": "📍 نينوى"}]], "resize_keyboard": True}

def kb_sectors():
    return {"keyboard": [[{"text": "💼 نفط وغاز"}, {"text": "💼 هندسة"}], [{"text": "💼 إدارة"}, {"text": "💼 طب"}], [{"text": "🔙 إلغاء"}]], "resize_keyboard": True}

def kb_limits():
    return {"keyboard": [[{"text": "🔢 5 منشورات"}, {"text": "🔢 20 منشور"}, {"text": "🔢 50 منشور"}]], "resize_keyboard": True}

def kb_publish_type():
    return {"keyboard": [[{"text": "⚡️ نشر يدوي (الآن)"}, {"text": "📅 جدولة تلقائية"}]], "resize_keyboard": True}

def kb_schedule_period():
    return {"keyboard": [[{"text": "🗓 لمدة 7 أيام"}, {"text": "🗓 لمدة 30 يوم"}]], "resize_keyboard": True}

# ==================== معالجة المراحل ====================
def handle_step(up):
    msg = up.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    text = msg.get("text", "")

    if chat_id != ADMIN_ID: return

    # البداية
    if text == "/start" or text == "🔙 إلغاء":
        USER_STATE[chat_id] = {"step": "PROVINCE"}
        send_m(chat_id, "مرحباً حيدر. الخطوة 1: اختر المحافظة:", kb_provinces())

    # الخطوة 1: اختيار المحافظة
    elif USER_STATE.get(chat_id, {}).get("step") == "PROVINCE":
        USER_STATE[chat_id]["province"] = text.replace("📍 ", "")
        USER_STATE[chat_id]["step"] = "SECTOR"
        send_m(chat_id, f"تم اختيار {text}. الخطوة 2: اختر القطاع:", kb_sectors())

    # الخطوة 2: اختيار القطاع
    elif USER_STATE.get(chat_id, {}).get("step") == "SECTOR":
        USER_STATE[chat_id]["sector"] = text.replace("💼 ", "")
        USER_STATE[chat_id]["step"] = "LIMIT"
        send_m(chat_id, "الخطوة 3: اختر عدد المنشورات المطلوب سحبها:", kb_limits())

    # الخطوة 3: سحب البيانات والعرض
    elif USER_STATE.get(chat_id, {}).get("step") == "LIMIT":
        limit = int(re.search(r'\d+', text).group())
        USER_STATE[chat_id]["limit"] = limit
        send_m(chat_id, "🔎 جاري سحب الوظائف ومعالجتها بـ Gemini... انتظر ثواني.")
        
        jobs = fetch_jobs(USER_STATE[chat_id]["province"], USER_STATE[chat_id]["sector"], limit)
        processed_jobs = [ai_refine(j) for j in jobs]
        USER_STATE[chat_id]["jobs"] = processed_jobs
        USER_STATE[chat_id]["step"] = "CONFIRM"
        
        preview = "\n---\n".join(processed_jobs[:3]) # عرض عينة
        send_m(chat_id, f"✅ تم العثور على {len(processed_jobs)} وظيفة. إليك عينة:\n\n{preview}\n\nالخطوة 4: كيف تود النشر؟", kb_publish_type())

    # الخطوة 4: نوع النشر
    elif USER_STATE.get(chat_id, {}).get("step") == "CONFIRM":
        if text == "⚡️ نشر يدوي (الآن)":
            for post in USER_STATE[chat_id]["jobs"]:
                send_m(CHANNEL_ID, post)
                time.sleep(5)
            send_m(chat_id, "✅ تم النشر اليدوي بنجاح!", kb_provinces())
