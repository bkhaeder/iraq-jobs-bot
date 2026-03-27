import os
import requests
import sqlite3
import time
import hashlib
import logging
import threading
from datetime import datetime
from bs4 import BeautifulSoup

# ==================== الإعدادات المؤكدة ====================
BOT_TOKEN = "8615364517:AAG-y4NpcbNpA803DwJVtHBpIca5GfnB_gY"
GEMINI_API_KEY = "AIzaSyA_5I1nCiqa5m5x7pvqQLbcwLf3wpCQ-Bw"
CHANNEL_ID = "@iraqjopsforall"
ADMIN_ID = 7590912344  # معرف حسابك للتحكم بالبوت
DB_FILE = "iraq_jobs.db"

# حالة النشر التلقائي (تعمل في الذاكرة)
AUTO_POST_ENABLED = True

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

# ==================== محرك البحث المطور (Google Jobs Logic) ====================
def fetch_real_jobs(province, sector="وظائف"):
    # دمج القطاع مع المحافظة للبحث الدقيق
    search_query = f"{sector} في {province} العراق"
    url = f"https://www.google.com/search?q={search_query}&ibp=htl;jobs"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        # ملاحظة: للحصول على نتائج أدق من مواقع متعددة، سنستخدم تنقيب كمرجع أساسي مع تحسين الكلمات
        tanqeeb_url = f"https://iraq.tanqeeb.com/ar/s/{sector.replace(' ', '-')}-في-{province.replace(' ', '-')}"
        r = requests.get(tanqeeb_url, headers=headers, timeout=20)
        soup = BeautifulSoup(r.content, 'html.parser')
        items = soup.find_all('div', class_='item')
        
        jobs = []
        for it in items[:5]:
            title_el = it.find('h2')
            link_el = it.find('a')
            if title_el and link_el:
                link = link_el['href']
                if not link.startswith('http'): link = "https://iraq.tanqeeb.com" + link
                jobs.append({"title": title_el.get_text(strip=True), "link": link, "location": province, "sector": sector})
        return jobs
    except: return []

# ==================== تحسين الصياغة بـ Gemini ====================
def refine_with_gemini(job):
    prompt = f"صغ إعلان وظيفي جذاب جداً لقناة تليجرام. الوظيفة: {job['title']}، القطاع: {job['sector']}، الموقع: {job['location']}. الرابط: {job['link']}. استخدم لهجة عراقية بيضاء وإيموجي احترافي."
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    try:
        r = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=20)
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except:
        return f"📍 وظيفة جديدة: {job['title']}\n📍 الموقع: {job['location']}\n🔗 التقديم: {job['link']}"

# ==================== الواجهة والأزرار ====================
def get_main_keyboard(is_admin=False):
    keyboard = [
        [{"text": "🏢 اختيار القطاع"}, {"text": "📍 اختيار المحافظة"}],
        [{"text": "🔍 بحث الآن"}]
    ]
    if is_admin:
        status = "🔴 تعطيل النشر التلقائي" if AUTO_POST_ENABLED else "🟢 تفعيل النشر التلقائي"
        keyboard.append([{"text": status}])
    return {"keyboard": keyboard, "resize_keyboard": True}

def get_sectors_keyboard():
    return {
        "keyboard": [
            [{"text": "📁 نفط وغاز"}, {"text": "📁 هندسة"}],
            [{"text": "📁 إدارة ومحاسبة"}, {"text": "📁 تصميم وبرمجة"}],
            [{"text": "📁 طب وصيدلة"}, {"text": "📁 وظائف عامة"}],
            [{"text": "🔙 العودة"}]
        ], "resize_keyboard": True
    }

def get_provinces_keyboard():
    return {
        "keyboard": [
            [{"text": "📍 البصرة"}, {"text": "📍 بغداد"}, {"text": "📍 نينوى"}],
            [{"text": "📍 أربيل"}, {"text": "📍 كربلاء"}, {"text": "📍 النجف"}],
            [{"text": "🔙 العودة"}]
        ], "resize_keyboard": True
    }

# ==================== معالجة الرسائل ====================
user_selection = {} # لحفظ اختيارات المستخدم مؤقتاً

def handle_message(update):
    global AUTO_POST_ENABLED
    if "message" not in update: return
    msg = update["message"]
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")

    if text == "/start":
        user_selection[chat_id] = {"province": "العراق", "sector": "وظائف"}
        send_msg(chat_id, "مرحباً بك في لوحة تحكم وظائف العراق.", get_main_keyboard(chat_id == ADMIN_ID))

    elif text == "🟢 تفعيل النشر التلقائي":
        AUTO_POST_ENABLED = True
        send_msg(chat_id, "تم تفعيل النشر التلقائي في القناة ✅", get_main_keyboard(True))

    elif text == "🔴 تعطيل النشر التلقائي":
        AUTO_POST_ENABLED = False
        send_msg(chat_id, "تم إيقاف النشر التلقائي 🛑", get_main_keyboard(True))

    elif text == "🏢 اختيار القطاع":
        send_msg(chat_id, "اختر القطاع المطلوب:", get_sectors_keyboard())

    elif text.startswith("📁"):
        user_selection[chat_id]["sector"] = text.replace("📁 ", "")
        send_msg(chat_id, f"تم اختيار قطاع: {user_selection[chat_id]['sector']}", get_main_keyboard(chat_id == ADMIN_ID))

    elif text == "📍 اختيار المحافظة":
        send_msg(chat_id, "اختر المحافظة:", get_provinces_keyboard())

    elif text.startswith("📍"):
        user_selection[chat_id]["province"] = text.replace("📍 ", "")
        send_msg(chat_id, f"تم اختيار محافظة: {user_selection[chat_id]['province']}", get_main_keyboard(chat_id == ADMIN_ID))

    elif text == "🔍 بحث الآن":
        prov = user_selection.get(chat_id, {}).get("province", "العراق")
        sect = user_selection.get(chat_id, {}).get("sector", "وظائف")
        send_msg(chat_id, f"🔎 جاري البحث عن {sect} في {prov}...")
        jobs = fetch_real_jobs(prov, sect)
        if not jobs: send_msg(chat_id, "لم أجد نتائج حالياً.")
        else:
            for j in jobs:
                p = refine_with_gemini(j)
                send_msg(chat_id, p)

    elif text == "🔙 العودة":
        send_msg(chat_id, "القائمة الرئيسية:", get_main_keyboard(chat_id == ADMIN_ID))

def send_msg(chat_id, text, markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown", "reply_markup": markup}
    return requests.post(url, json=payload)

# ==================== التشغيل التلقائي ====================
def auto_post_loop():
    while True:
        if AUTO_POST_ENABLED:
            log.info("🔄 فحص تلقائي...")
            for p in ["البصرة", "بغداد"]:
                for s in ["هندسة", "نفط"]:
                    jobs = fetch_real_jobs(p, s)
                    for j in jobs:
                        jid = hashlib.md5(j['link'].encode()).hexdigest()
                        if not is_posted(jid):
                            send_msg(CHANNEL_ID, refine_with_gemini(j))
                            mark_posted(jid, j['title'], s, p)
                            time.sleep(20)
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
        for up in get_updates(offset):
            offset = up["update_id"] + 1
            handle_message(up)
        time.sleep(1)
