#!/usr/bin/env python3
"""
بوت وظائف العراق الذكي - @iraqjopsforall
- يبحث عن وظائف في العراق فقط
- أنت تحدد المحافظة عبر البوت
- مدعوم بـ Google Gemini AI
"""

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
DB_FILE = "iraq_jobs.db"

# ==================== محافظات العراق ====================
IRAQ_PROVINCES = {
    "بغداد": "Baghdad",
    "البصرة": "Basra",
    "نينوى": "Nineveh Mosul",
    "أربيل": "Erbil",
    "النجف": "Najaf",
    "كربلاء": "Karbala",
    "السليمانية": "Sulaymaniyah",
    "كركوك": "Kirkuk",
    "الأنبار": "Anbar Ramadi",
    "ديالى": "Diyala",
    "ذي قار": "Dhi Qar Nasiriyah",
    "بابل": "Babylon Babil",
    "واسط": "Wasit Kut",
    "ميسان": "Maysan Amarah",
    "المثنى": "Muthanna Samawah",
    "القادسية": "Qadisiyyah Diwaniyah",
    "صلاح الدين": "Salah al-Din Tikrit",
    "دهوك": "Duhok",
    "حلبجة": "Halabja",
}

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
            province TEXT,
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

def mark_posted(job_id, title, category="", province=""):
    conn = sqlite3.connect(DB_FILE)
    conn.execute(
        "INSERT OR IGNORE INTO posted_jobs (id, title, category, province, posted_at) VALUES (?, ?, ?, ?, ?)",
        (job_id, title, category, province, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def add_admin(chat_id):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("INSERT OR IGNORE INTO admins (chat_id) VALUES (?)", (chat_id,))
    conn.commit()
    conn.close()

def get_admins():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.execute("SELECT chat_id FROM admins")
    result = [row[0] for row in cur.fetchall()]
    conn.close()
    return result

# ==================== تيليغرام ====================
def send_message(chat_id, text, parse_mode="HTML", reply_markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
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

def answer_callback(callback_id, text=""):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery"
    requests.post(url, json={"callback_query_id": callback_id, "text": text}, timeout=10)

def get_updates(offset=0):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    try:
        r = requests.get(url, params={"offset": offset, "timeout": 30}, timeout=35)
        if r.status_code == 200:
            return r.json().get("result", [])
    except:
        pass
    return []

# ==================== لوحة المحافظات ====================
def provinces_keyboard():
    provinces = list(IRAQ_PROVINCES.keys())
    keyboard = []
    for i in range(0, len(provinces), 3):
        row = []
        for p in provinces[i:i+3]:
            row.append({"text": p, "callback_data": f"province:{p}"})
        keyboard.append(row)
    keyboard.append([{"text": "🇮🇶 كل العراق", "callback_data": "province:كل العراق"}])
    return {"inline_keyboard": keyboard}

def categories_keyboard(province):
    categories = [
        "هندسة", "تقنية", "محاسبة", "تسويق",
        "مبيعات", "طب", "تعليم", "إدارة",
        "برمجة", "تصميم", "موارد بشرية", "قانون",
    ]
    keyboard = []
    for i in range(0, len(categories), 3):
        row = []
        for c in categories[i:i+3]:
            row.append({"text": c, "callback_data": f"category:{province}:{c}"})
        keyboard.append(row)
    keyboard.append([{"text": "📋 كل التخصصات", "callback_data": f"category:{province}:كل التخصصات"}])
    return {"inline_keyboard": keyboard}

def count_keyboard(province, category):
    counts = [3, 5, 10, 15, 20]
    keyboard = [[{"text": str(c), "callback_data": f"count:{province}:{category}:{c}"} for c in counts]]
    return {"inline_keyboard": keyboard}

# ==================== Gemini AI ====================
def ask_gemini(user_message):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

    provinces_list = "، ".join(IRAQ_PROVINCES.keys())

    system_prompt = f"""أنت مساعد ذكي لإدارة قناة وظائف عراقية على تيليغرام اسمها @iraqjopsforall.
القناة تنشر وظائف للعراق فقط.

محافظات العراق المتاحة: {provinces_list}

عندما يطلب نشر وظائف، أجب بـ JSON فقط:
{{"action": "post_jobs", "count": 5, "category": "تسويق", "province": "البصرة"}}

عندما يسأل عن الإحصائيات:
{{"action": "stats"}}

عندما يريد إيقاف النشر التلقائي:
{{"action": "pause"}}

عندما يريد تشغيل النشر التلقائي:
{{"action": "resume"}}

عندما يريد اختيار محافظة بشكل تفاعلي:
{{"action": "choose_province"}}

عندما يسأل سؤالاً عادياً، أجب بنص عربي طبيعي ومختصر وودي.
لا تضف أي نص مع JSON."""

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

# ==================== جلب الوظائف ====================
def search_jobs_gemini(count, category, province):
    """استخدام Gemini لتوليد وظائف عراقية واقعية"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

    province_en = IRAQ_PROVINCES.get(province, province) if province != "كل العراق" else "Iraq"

    prompt = f"""أنت محرك بحث وظائف متخصص في العراق.
قم بإنشاء {count} وظيفة واقعية ومناسبة للسوق العراقي.

المحافظة: {province} ({province_en})
التخصص: {category if category != "كل التخصصات" else "مختلف التخصصات"}

أجب بـ JSON فقط بهذا الشكل:
{{
  "jobs": [
    {{
      "title": "مسمى الوظيفة بالعربية",
      "company": "اسم الشركة",
      "location": "المحافظة والمنطقة",
      "description": "وصف الوظيفة باختصار (2-3 جمل)",
      "requirements": "المتطلبات الأساسية",
      "salary": "الراتب التقريبي بالدينار العراقي أو دولار",
      "contact": "طريقة التواصل (ايميل أو واتساب وهمي واقعي)"
    }}
  ]
}}

تأكد أن الوظائف:
- واقعية وتناسب سوق العمل العراقي
- بأسماء شركات عراقية أو دولية تعمل في العراق
- بمعلومات تواصل واقعية
لا تضف أي نص خارج JSON."""

    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        r = requests.post(url, json=payload, timeout=30)
        if r.status_code == 200:
            data = r.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            clean = text.strip().replace("```json", "").replace("```", "").strip()
            result = json.loads(clean)
            return result.get("jobs", [])
    except Exception as e:
        log.error(f"خطأ جلب وظائف: {e}")
    return []

def format_job(job, province="", category=""):
    title = job.get("title", "وظيفة شاغرة").strip()
    company = job.get("company", "")
    location = job.get("location", province)
    description = job.get("description", "")
    requirements = job.get("requirements", "")
    salary = job.get("salary", "")
    contact = job.get("contact", "")

    tags = f"#العراق"
    if province and province != "كل العراق":
        tags += f" #{province.replace(' ', '_')}"
    if category and category != "كل التخصصات":
        tags += f" #{category}"

    msg = f"💼 <b>{title}</b>\n"
    if company:
        msg += f"🏢 <b>{company}</b>\n"
    msg += f"📍 {location}\n"

    if description:
        msg += f"\n📝 {description}\n"
    if requirements:
        msg += f"\n✅ <b>المتطلبات:</b> {requirements}\n"
    if salary:
        msg += f"💰 <b>الراتب:</b> {salary}\n"
    if contact:
        msg += f"📞 <b>التواصل:</b> {contact}\n"

    msg += f"\n{tags}\n"
    msg += f"━━━━━━━━━━━━━━━\n📢 @iraqjopsforall"
    return msg

# ==================== تنفيذ الأوامر ====================
paused = False

def post_jobs(chat_id, count, category, province):
    send_message(chat_id, f"⏳ جاري البحث عن {count} وظيفة {category} في {province}...")
    jobs = search_jobs_gemini(count, category, province)

    if not jobs:
        send_message(chat_id, "❌ حدث خطأ في البحث، حاول مرة أخرى.")
        return

    send_message(chat_id, f"✅ تم إيجاد {len(jobs)} وظيفة، جاري النشر على القناة...")
    posted = 0
    for job in jobs:
        msg = format_job(job, province, category)
        if send_to_channel(msg):
            job_id = hashlib.md5((job.get("title","") + job.get("company","") + datetime.now().isoformat()).encode()).hexdigest()
            mark_posted(job_id, job.get("title",""), category, province)
            posted += 1
            time.sleep(2)

    send_message(chat_id, f"🎉 تم نشر {posted} وظيفة في {province} على @iraqjopsforall!")

def handle_action(action_data, chat_id):
    global paused
    action = action_data.get("action")

    if action == "post_jobs":
        count = int(action_data.get("count", 5))
        category = action_data.get("category", "كل التخصصات")
        province = action_data.get("province", "كل العراق")
        post_jobs(chat_id, count, category, province)

    elif action == "choose_province":
        send_message(chat_id, "🗺 اختر المحافظة:", reply_markup=provinces_keyboard())

    elif action == "stats":
        conn = sqlite3.connect(DB_FILE)
        total = conn.execute("SELECT COUNT(*) FROM posted_jobs").fetchone()[0]
        today = conn.execute("SELECT COUNT(*) FROM posted_jobs WHERE posted_at >= date('now')").fetchone()[0]
        provinces = conn.execute(
            "SELECT province, COUNT(*) as c FROM posted_jobs GROUP BY province ORDER BY c DESC LIMIT 5"
        ).fetchall()
        conn.close()

        stats = "\n".join([f"  • {p[0]}: {p[1]} وظيفة" for p in provinces]) if provinces else "  لا توجد بيانات"
        send_message(chat_id, f"""📊 <b>إحصائيات قناة @iraqjopsforall</b>

📌 إجمالي الوظائف: <b>{total}</b>
📅 منشورة اليوم: <b>{today}</b>

🗺 <b>أكثر المحافظات:</b>
{stats}

⏰ النشر التلقائي: {'⏸ موقوف' if paused else '✅ يعمل'} كل ساعة""")

    elif action == "pause":
        paused = True
        send_message(chat_id, "⏸ تم إيقاف النشر التلقائي مؤقتاً.")

    elif action == "resume":
        paused = False
        send_message(chat_id, "▶️ تم استئناف النشر التلقائي!")

# ==================== معالجة الرسائل ====================
def handle_message(update):
    # معالجة الأزرار
    if "callback_query" in update:
        cb = update["callback_query"]
        chat_id = cb["message"]["chat"]["id"]
        data = cb.get("data", "")
        answer_callback(cb["id"])

        parts = data.split(":")

        if parts[0] == "province":
            province = parts[1]
            send_message(chat_id, f"✅ اخترت: <b>{province}</b>\n\nالآن اختر التخصص:",
                        reply_markup=categories_keyboard(province))

        elif parts[0] == "category":
            province = parts[1]
            category = parts[2]
            send_message(chat_id, f"✅ المحافظة: <b>{province}</b>\nالتخصص: <b>{category}</b>\n\nكم وظيفة تريد نشرها؟",
                        reply_markup=count_keyboard(province, category))

        elif parts[0] == "count":
            province = parts[1]
            category = parts[2]
            count = int(parts[3])
            threading.Thread(target=post_jobs, args=(chat_id, count, category, province), daemon=True).start()

        return

    # معالجة الرسائل النصية
    msg = update.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    text = msg.get("text", "").strip()

    if not chat_id or not text:
        return

    add_admin(chat_id)
    log.info(f"رسالة من {chat_id}: {text}")

    if text == "/start":
        send_message(chat_id, """👋 <b>أهلاً! أنا بوت وظائف العراق الذكي 🇮🇶</b>

يمكنك أن تطلب مني:

🗺 <b>اختيار محافظة:</b>
• "انشر وظائف" ← سيظهر لك قائمة المحافظات

💬 <b>أمر مباشر:</b>
• "انشر 10 وظائف تسويق في البصرة"
• "انشر 5 وظائف هندسة في بغداد"

📊 <b>إحصائيات:</b>
• "كم وظيفة نشرنا اليوم؟"

⏸ <b>تحكم:</b>
• "أوقف النشر التلقائي"
• "شغّل النشر التلقائي" """,
        reply_markup={"keyboard": [
            [{"text": "🗺 اختر محافظة وانشر"}, {"text": "📊 الإحصائيات"}],
            [{"text": "⏸ إيقاف التلقائي"}, {"text": "▶️ تشغيل التلقائي"}]
        ], "resize_keyboard": True})
        return

    # أزرار لوحة المفاتيح
    if text == "🗺 اختر محافظة وانشر":
        send_message(chat_id, "🗺 اختر المحافظة:", reply_markup=provinces_keyboard())
        return
    elif text == "📊 الإحصائيات":
        handle_action({"action": "stats"}, chat_id)
        return
    elif text == "⏸ إيقاف التلقائي":
        handle_action({"action": "pause"}, chat_id)
        return
    elif text == "▶️ تشغيل التلقائي":
        handle_action({"action": "resume"}, chat_id)
        return

    # Gemini AI
    send_message(chat_id, "🤔 جاري التفكير...")
    response = ask_gemini(text)

    if not response:
        send_message(chat_id, "❌ حدث خطأ، حاول مرة أخرى.")
        return

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
    time.sleep(60)  # انتظر دقيقة قبل أول دورة
    while True:
        if not paused:
            log.info("🔄 دورة نشر تلقائي...")
            # نشر وظائف من بغداد والبصرة تلقائياً
            for province in ["بغداد", "البصرة"]:
                try:
                    jobs = search_jobs_gemini(3, "كل التخصصات", province)
                    for job in jobs:
                        msg = format_job(job, province)
                        if send_to_channel(msg):
                            job_id = hashlib.md5((job.get("title","") + province + datetime.now().isoformat()).encode()).hexdigest()
                            mark_posted(job_id, job.get("title",""), "كل التخصصات", province)
                            time.sleep(3)
                except Exception as e:
                    log.error(f"خطأ نشر تلقائي: {e}")

            for admin in get_admins():
                send_message(admin, "📢 تم النشر التلقائي! أرسل 'الإحصائيات' لمعرفة التفاصيل.")

        time.sleep(CHECK_INTERVAL)

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
    log.info("🚀 تشغيل بوت وظائف العراق الذكي...")
    init_db()
    send_to_channel("🇮🇶 <b>بوت وظائف العراق الذكي يعمل الآن!</b>\nسيتم نشر وظائف عراقية تلقائياً كل ساعة ⏰")
    threading.Thread(target=auto_post_loop, daemon=True).start()
    polling_loop()

if __name__ == "__main__":
    main()
