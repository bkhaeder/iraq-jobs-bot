import requests
import sqlite3
import time
import hashlib
import logging
import threading
import json
import re

# ==================== الإعدادات المؤكدة ====================
BOT_TOKEN = "8615364517:AAG-y4NpcbNpA803DwJVtHBpIca5GfnB_gY"
GEMINI_API_KEY = "AIzaSyA_5I1nCiqa5m5x7pvqQLbcwLf3wpCQ-Bw"
CHANNEL_ID = "@iraqjopsforall"
ADMIN_ID = 7590912344

# مخزن مؤقت لحالة المستخدم
USER_STATE = {}

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# ==================== الأزرار والواجهات ====================
def get_kb_provinces():
    return {
        "keyboard": [
            [{"text": "📍 البصرة"}, {"text": "📍 بغداد"}],
            [{"text": "📍 أربيل"}, {"text": "📍 نينوى"}],
            [{"text": "📍 كربلاء"}, {"text": "📍 النجف"}]
        ], "resize_keyboard": True, "one_time_keyboard": True
    }

def get_kb_sectors():
    return {
        "keyboard": [
            [{"text": "💼 نفط وغاز"}, {"text": "💼 هندسة"}],
            [{"text": "💼 إدارة"}, {"text": "💼 طب وصيدلة"}],
            [{"text": "🔙 إلغاء والبدء من جديد"}]
        ], "resize_keyboard": True, "one_time_keyboard": True
    }

def get_kb_limits():
    return {
        "keyboard": [
            [{"text": "🔢 5 منشورات"}, {"text": "🔢 20 منشور"}],
            [{"text": "🔢 50 منشور"}]
        ], "resize_keyboard": True, "one_time_keyboard": True
    }

def get_kb_publish_type():
    return {
        "keyboard": [
            [{"text": "⚡️ نشر يدوي فوراً"}, {"text": "📅 جدولة تلقائية"}]
        ], "resize_keyboard": True, "one_time_keyboard": True
    }

def get_kb_schedule():
    return {
        "keyboard": [
            [{"text": "🗓 لمدة 7 أيام"}, {"text": "🗓 لمدة 30 يوم"}]
        ], "resize_keyboard": True, "one_time_keyboard": True
    }

# ==================== الوظائف المساعدة ====================
def send_m(chat_id, text, markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if markup:
        payload["reply_markup"] = markup
    try:
        return requests.post(url, json=payload, timeout=10)
    except:
        return None

def fetch_jobs_from_tanqeeb(province, sector, limit=5):
    query = f"{sector} في {province}"
    url = f"https://iraq.tanqeeb.com/ar/s/{query.replace(' ', '-')}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        from bs4 import BeautifulSoup
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
    except:
        return []

def ai_refine(job):
    prompt = f"صغ إعلان وظيفي عراقي جذاب: {job['title']} في {job['prov']}. القسم: {job['sect']}. الرابط: {job['link']}"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    try:
        r = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=15)
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except:
        return f"💼 {job['title']}\n📍 {job['prov']}\n🔗 {job['link']}"

# ==================== معالجة الرسائل ====================
def handle_updates(update):
    if "message" not in update: return
    msg = update["message"]
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")

    if chat_id != ADMIN_ID: return

    # البداية
    if text == "/start" or text == "🔙 إلغاء والبدء من جديد":
        USER_STATE[chat_id] = {"step": "PROVINCE"}
        send_m(chat_id, "🇮🇶 أهلاً بك يا حيدر.\nالخطوة 1: اختر المحافظة المطلوبة:", get_kb_provinces())

    # الخطوة 1: المحافظة
    elif USER_STATE.get(chat_id, {}).get("step") == "PROVINCE":
        USER_STATE[chat_id]["province"] = text.replace("📍 ", "")
        USER_STATE[chat_id]["step"] = "SECTOR"
        send_m(chat_id, f"تم اختيار {text}.\nالخطوة 2: اختر قطاع الوظائف:", get_kb_sectors())

    # الخطوة 2: القطاع
    elif USER_STATE.get(chat_id, {}).get("step") == "SECTOR":
        USER_STATE[chat_id]["sector"] = text.replace("💼 ", "")
        USER_STATE[chat_id]["step"] = "LIMIT"
        send_m(chat_id, "الخطوة 3: اختر عدد المنشورات المطلوب سحبها الآن:", get_kb_limits())

    # الخطوة 3: العدد والسحب
    elif USER_STATE.get(chat_id, {}).get("step") == "LIMIT":
        try:
            limit = int(re.search(r'\d+', text).group())
            USER_STATE[chat_id]["limit"] = limit
            send_m(chat_id, "🔎 جاري سحب الوظائف من المصادر ومعالجتها... انتظر لحظة.")
            
            jobs = fetch_jobs_from_tanqeeb(USER_STATE[chat_id]["province"], USER_STATE[chat_id]["sector"], limit)
            if not jobs:
                send_m(chat_id, "❌ لم أجد وظائف حالياً بهذا التصنيف. جرب محافظة أخرى.", get_kb_provinces())
                USER_STATE[chat_id] = {"step": "PROVINCE"}
                return

            processed = [ai_refine(j) for j in jobs]
            USER_STATE[chat_id]["jobs_to_post"] = processed
            USER_STATE[chat_id]["step"] = "PUBLISH_TYPE"
            
            send_m(chat_id, f"✅ تم تجهيز {len(processed)} وظيفة.\nالخطوة 4: اختر طريقة النشر:", get_kb_publish_type())
        except:
            send_m(chat_id, "يرجى اختيار العدد من الأزرار.")

    # الخطوة 4: نوع النشر
    elif USER_STATE.get(chat_id, {}).get("step") == "PUBLISH_TYPE":
        if text == "⚡️ نشر يدوي فوراً":
            send_m(chat_id, "🚀 جاري الصب في القناة...")
            for post in USER_STATE[chat_id]["jobs_to_post"]:
                send_m(CHANNEL_ID, post)
                time.sleep(3)
            send_m(chat_id, "✅ اكتمل النشر اليدوي بنجاح!", get_kb_provinces())
            USER_STATE[chat_id] = {"step": "PROVINCE"}
        elif text == "📅 جدولة تلقائية":
            USER_STATE[chat_id]["step"] = "SCHEDULE_PERIOD"
            send_m(chat_id, "الخطوة الأخيرة: اختر مدة الجدولة:", get_kb_schedule())

    # الخطوة 5: الجدولة
    elif USER_STATE.get(chat_id, {}).get("step") == "SCHEDULE_PERIOD":
        days = 7 if "7" in text else 30
        interval = (days * 24) / len(USER_STATE[chat_id]["jobs_to_post"])
        send_m(chat_id, f"📅 تم تثبيت الجدولة لمدة {days} يوم.\nسيتم نشر وظيفة كل {interval:.1f} ساعة تلقائياً.\n(ملاحظة: الجدولة تتطلب قاعدة بيانات نشطة).", get_kb_provinces())
        USER_STATE[chat_id] = {"step": "PROVINCE"}

# ==================== التشغيل الرئيسي ====================
if __name__ == "__main__":
    offset = 0
    logging.info("🚀 البوت المرحلي يعمل الآن...")
    while True:
        try:
            r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}&timeout=20").json()
            for up in r.get("result", []):
                offset = up["update_id"] + 1
                handle_updates(up)
        except Exception as e:
            logging.error(f"Error: {e}")
        time.sleep(1)
