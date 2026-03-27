import requests
import sqlite3
import time
import hashlib
import logging
import threading
from bs4 import BeautifulSoup

# ==================== الإعدادات المؤكدة ====================
BOT_TOKEN = "8615364517:AAG-y4NpcbNpA803DwJVtHBpIca5GfnB_gY"
GEMINI_API_KEY = "AIzaSyA_5I1nCiqa5m5x7pvqQLbcwLf3wpCQ-Bw"
CHANNEL_ID = "@iraqjopsforall"
ADMIN_ID = 7590912344  # معرف حساب حيدر

# متغيرات التحكم (Control Variables)
CONFIG = {
    "auto_post": True,
    "post_limit": 5,      # عدد المنشورات المطلوب نشرها في الدورة الواحدة
    "post_delay": 60,     # التأخير بين منشور وآخر (بالثواني)
    "current_province": "البصرة",
    "current_sector": "وظائف"
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# ==================== قاعدة البيانات ====================
def init_db():
    conn = sqlite3.connect("iraq_jobs.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS posted_jobs 
                 (id TEXT PRIMARY KEY, title TEXT, timestamp DATETIME)''')
    conn.commit()
    conn.close()

def is_posted(job_id):
    conn = sqlite3.connect("iraq_jobs.db")
    c = conn.cursor()
    c.execute("SELECT 1 FROM posted_jobs WHERE id=?", (job_id,))
    res = c.fetchone()
    conn.close()
    return res is not None

def mark_posted(job_id, title):
    conn = sqlite3.connect("iraq_jobs.db")
    c = conn.cursor()
    c.execute("INSERT INTO posted_jobs (id, title, timestamp) VALUES (?, ?, CURRENT_TIMESTAMP)", (job_id, title))
    conn.commit()
    conn.close()

# ==================== صائد الوظائف المطور ====================
def fetch_jobs(province, sector):
    # محاكاة بحث متقدم لضمان جلب نتائج حقيقية
    search_term = f"{sector} في {province}"
    url = f"https://iraq.tanqeeb.com/ar/s/{search_term.replace(' ', '-')}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    try:
        r = requests.get(url, headers=headers, timeout=20)
        soup = BeautifulSoup(r.content, 'html.parser')
        items = soup.find_all('div', class_='item')
        
        results = []
        for it in items:
            title = it.find('h2').get_text(strip=True) if it.find('h2') else ""
            link = it.find('a')['href'] if it.find('a') else ""
            if title and link:
                if not link.startswith('http'): link = "https://iraq.tanqeeb.com" + link
                results.append({"title": title, "link": link, "prov": province, "sect": sector})
        return results
    except: return []

# ==================== ذكاء Gemini في الصياغة ====================
def ai_format(job):
    prompt = f"صغ إعلان وظيفي عراقي احترافي جداً لقناة تليجرام. الوظيفة: {job['title']} في {job['prov']}. القسم: {job['sect']}. الرابط: {job['link']}. استخدم إيموجي مناسب ولهجة بيضاء."
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    try:
        r = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=20)
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except: return f"📍 وظيفة جديدة: {job['title']}\n🔗 التقديم: {job['link']}"

# ==================== لوحة التحكم والأزرار ====================
def send_m(chat_id, text, markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown", "reply_markup": markup}
    return requests.post(url, json=payload)

def main_kb():
    return {"keyboard": [
        [{"text": "⚙️ الإعدادات"}, {"text": "🔍 بحث ونشر الآن"}],
        [{"text": "📍 المحافظات"}, {"text": "📁 القطاعات"}],
        [{"text": "🔄 تفعيل/تعطيل النشر التلقائي"}]
    ], "resize_keyboard": True}

def settings_kb():
    return {"keyboard": [
        [{"text": "🔢 عدد المنشورات (5)"}, {"text": "🔢 عدد المنشورات (20)"}, {"text": "🔢 عدد المنشورات (50)"}],
        [{"text": "⏱ فاصل دقيقة"}, {"text": "⏱ فاصل 5 دقائق"}, {"text": "⏱ فاصل ساعة"}],
        [{"text": "🔙 العودة"}]
    ], "resize_keyboard": True}

def sectors_kb():
    return {"keyboard": [
        [{"text": "💼 نفط وغاز"}, {"text": "💼 هندسة"}, {"text": "💼 طب وصيدلة"}],
        [{"text": "💼 إدارية ومالية"}, {"text": "💼 تعليم وتدريس"}, {"text": "💼 برمجة وتصميم"}],
        [{"text": "💼 مبيعات وتسويق"}, {"text": "💼 حرفيين وعمال"}, {"text": "💼 فندقة وطبخ"}],
        [{"text": "🔙 العودة"}]
    ], "resize_keyboard": True}

# ==================== معالجة الأوامر ====================
def handle_msg(up):
    global CONFIG
    msg = up.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    text = msg.get("text", "")

    if chat_id != ADMIN_ID: return # التحكم لحيدر فقط

    if text == "/start" or text == "🔙 العودة":
        send_m(chat_id, "أهلاً بك حيدر في لوحة التحكم المطورة.", main_kb())

    elif text == "⚙️ الإعدادات":
        send_m(chat_id, "اختر إعدادات النشر:", settings_kb())

    elif "عدد المنشورات" in text:
        CONFIG["post_limit"] = int(re.search(r'\d+', text).group())
        send_m(chat_id, f"✅ سيتم جلب {CONFIG['post_limit']} وظيفة في كل دورة.")

    elif "فاصل" in text:
        if "دقيقة" in text: CONFIG["post_delay"] = 60
        if "5 دقائق" in text: CONFIG["post_delay"] = 300
        if "ساعة" in text: CONFIG["post_delay"] = 3600
        send_m(chat_id, "✅ تم تحديث وقت الفاصل الزمني.")

    elif text == "📁 القطاعات":
        send_m(chat_id, "اختر القطاع المستهدف:", sectors_kb())

    elif text.startswith("💼"):
        CONFIG["current_sector"] = text.replace("💼 ", "")
        send_m(chat_id, f"✅ تم تحديد القطاع: {CONFIG['current_sector']}")

    elif text == "🔄 تفعيل/تعطيل النشر التلقائي":
        CONFIG["auto_post"] = not CONFIG["auto_post"]
        status = "شغال ✅" if CONFIG["auto_post"] else "متوقف 🛑"
        send_m(chat_id, f"النشر التلقائي الآن: {status}")

    elif text == "🔍 بحث ونشر الآن":
        send_m(chat_id, "🚀 جاري سحب الوظائف ونشرها...")
        run_publish_cycle()

import re

# ==================== دورة النشر ====================
def run_publish_cycle():
    jobs = fetch_jobs(CONFIG["current_province"], CONFIG["current_sector"])
    count = 0
    for j in jobs:
        if count >= CONFIG["post_limit"]: break
        jid = hashlib.md5(j['link'].encode()).hexdigest()
        if not is_posted(jid):
            formatted = ai_format(j)
            send_m(CHANNEL_ID, formatted)
            mark_posted(jid, j['title'])
            count += 1
            time.sleep(CONFIG["post_delay"])

def auto_loop():
    while True:
        if CONFIG["auto_post"]:
            run_publish_cycle()
        time.sleep(3600) # فحص كل ساعة

if __name__ == "__main__":
    init_db()
    threading.Thread(target=auto_loop, daemon=True).start()
    offset = 0
    while True:
        r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}&timeout=30").json()
        for up in r.get("result", []):
            offset = up["update_id"] + 1
            handle_msg(up)
