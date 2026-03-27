#!/usr/bin/env python3
"""
بوت وظائف العراق الذكي - @iraqjopsforall
يبحث عن وظائف حقيقية من الإنترنت عبر Gemini
"""

import requests
import sqlite3
import time
import hashlib
import logging
import threading
import json
from datetime import datetime

# ==================== الإعدادات ====================
BOT_TOKEN = "8615364517:AAG-y4NpcbNpA803DwJVtHBpIca5GfnB_gY"
CHANNEL_ID = "@iraqjopsforall"
GEMINI_API_KEY = "AIzaSyA_5I1nCiqa5m5x7pvqQLbcwLf3wpCQ-Bw"
CHECK_INTERVAL = 3600
DB_FILE = "iraq_jobs.db"

# ==================== محافظات العراق ====================
IRAQ_PROVINCES = {
    "بغداد": "Baghdad", "البصرة": "Basra", "نينوى": "Nineveh Mosul",
    "أربيل": "Erbil", "النجف": "Najaf", "كربلاء": "Karbala",
    "السليمانية": "Sulaymaniyah", "كركوك": "Kirkuk", "الأنبار": "Anbar",
    "ديالى": "Diyala", "ذي قار": "Dhi Qar", "بابل": "Babylon",
    "واسط": "Wasit", "ميسان": "Maysan", "المثنى": "Muthanna",
    "القادسية": "Qadisiyyah", "صلاح الدين": "Salah al-Din",
    "دهوك": "Duhok", "حلبجة": "Halabja",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("bot.log", encoding="utf-8"), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

# ==================== قاعدة البيانات ====================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""CREATE TABLE IF NOT EXISTS posted_jobs (
        id TEXT PRIMARY KEY, title TEXT, province TEXT, posted_at TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS admins (chat_id INTEGER PRIMARY KEY)""")
    conn.commit()
    conn.close()

def is_posted(job_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.execute("SELECT 1 FROM posted_jobs WHERE id = ?", (job_id,))
    result = cur.fetchone()
    conn.close()
    return result is not None

def mark_posted(job_id, title, province=""):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("INSERT OR IGNORE INTO posted_jobs VALUES (?, ?, ?, ?)",
                 (job_id, title, province, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def add_admin(chat_id):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("INSERT OR IGNORE INTO admins VALUES (?)", (chat_id,))
    conn.commit()
    conn.close()

def get_admins():
    conn = sqlite3.connect(DB_FILE)
    result = [r[0] for r in conn.execute("SELECT chat_id FROM admins").fetchall()]
    conn.close()
    return result

# ==================== تيليغرام ====================
def send_message(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json=payload, timeout=15)
    except Exception as e:
        log.error(f"خطأ إرسال: {e}")

def send_to_channel(text):
    payload = {"chat_id": CHANNEL_ID, "text": text, "parse_mode": "HTML"}
    try:
        r = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json=payload, timeout=15)
        return r.status_code == 200
    except:
        return False

def answer_callback(cb_id):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery",
                      json={"callback_query_id": cb_id}, timeout=10)
    except:
        pass

def get_updates(offset=0):
    try:
        r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
                         params={"offset": offset, "timeout": 30}, timeout=35)
        if r.status_code == 200:
            return r.json().get("result", [])
    except:
        pass
    return []

# ==================== لوحات الأزرار ====================
def provinces_keyboard():
    provinces = list(IRAQ_PROVINCES.keys())
    keyboard = []
    for i in range(0, len(provinces), 3):
        keyboard.append([{"text": p, "callback_data": f"prov:{p}"} for p in provinces[i:i+3]])
    keyboard.append([{"text": "🇮🇶 كل العراق", "callback_data": "prov:كل العراق"}])
    return {"inline_keyboard": keyboard}

def categories_keyboard(province):
    cats = ["هندسة", "تقنية", "محاسبة", "تسويق", "مبيعات", "طب",
            "تعليم", "إدارة", "برمجة", "تصميم", "موارد بشرية", "قانون"]
    keyboard = []
    for i in range(0, len(cats), 3):
        keyboard.append([{"text": c, "callback_data": f"cat:{province}:{c}"} for c in cats[i:i+3]])
    keyboard.append([{"text": "📋 كل التخصصات", "callback_data": f"cat:{province}:كل التخصصات"}])
    return {"inline_keyboard": keyboard}

def count_keyboard(province, category):
    return {"inline_keyboard": [[
        {"text": str(c), "callback_data": f"cnt:{province}:{category}:{c}"}
        for c in [3, 5, 10, 15, 20]
    ]]}

# ==================== Gemini - بحث وظائف حقيقية ====================
def search_real_jobs(count, category, province):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    
    province_en = IRAQ_PROVINCES.get(province, "Iraq") if province != "كل العراق" else "Iraq"
    cat_text = category if category != "كل التخصصات" else "مختلف التخصصات"

    prompt = f"""ابحث في الإنترنت الآن عن {count} وظيفة شاغرة حقيقية ومنشورة حديثاً في {province} العراق.
التخصص المطلوب: {cat_text}

ابحث في هذه المصادر:
- مواقع التوظيف العراقية مثل Mihnati.com
- LinkedIn وظائف العراق
- مجموعات تيليغرام وظائف العراق
- المواقع الحكومية العراقية
- الشركات العراقية والدولية العاملة في العراق

أجب بـ JSON فقط بدون أي نص إضافي:
{{
  "jobs": [
    {{
      "title": "المسمى الوظيفي",
      "company": "اسم الشركة الحقيقي",
      "location": "{province}",
      "description": "وصف الوظيفة الحقيقي",
      "requirements": "المتطلبات الحقيقية",
      "salary": "الراتب إن وُجد",
      "source": "اسم الموقع أو المصدر",
      "link": "رابط الوظيفة الحقيقي إن وُجد"
    }}
  ]
}}"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}]
    }

    try:
        r = requests.post(url, json=payload, timeout=30)
        if r.status_code == 200:
            data = r.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            clean = text.strip().replace("```json", "").replace("```", "").strip()
            result = json.loads(clean)
            return result.get("jobs", [])
        else:
            log.error(f"Gemini error: {r.status_code} {r.text[:200]}")
    except Exception as e:
        log.error(f"خطأ جلب وظائف: {e}")
    return []

def ask_gemini(text):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    provinces_list = "، ".join(IRAQ_PROVINCES.keys())
    prompt = f"""أنت مساعد ذكي لإدارة قناة وظائف عراقية @iraqjopsforall.
محافظات العراق: {provinces_list}

عند طلب نشر وظائف أجب بـ JSON فقط:
{{"action":"post_jobs","count":5,"category":"تسويق","province":"البصرة"}}

عند طلب إحصائيات: {{"action":"stats"}}
عند إيقاف النشر: {{"action":"pause"}}
عند تشغيل النشر: {{"action":"resume"}}
عند طلب اختيار محافظة: {{"action":"choose_province"}}
للأسئلة العادية أجب بالعربية فقط بدون JSON.

رسالة المدير: {text}"""

    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        r = requests.post(url, json=payload, timeout=20)
        if r.status_code == 200:
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        log.error(f"خطأ Gemini: {e}")
    return None

# ==================== تنسيق الوظيفة ====================
def format_job(job, province="", category=""):
    title = job.get("title", "وظيفة شاغرة")
    company = job.get("company", "")
    location = job.get("location", province)
    description = job.get("description", "")
    requirements = job.get("requirements", "")
    salary = job.get("salary", "")
    source = job.get("source", "")
    link = job.get("link", "")

    tags = "#وظائف_العراق #العراق"
    if province and province != "كل العراق":
        tags += f" #{province.replace(' ', '_')}"
    if category and category != "كل التخصصات":
        tags += f" #{category}"

    msg = f"💼 <b>{title}</b>\n"
    if company:
        msg += f"🏢 {company}\n"
    msg += f"📍 {location}\n"
    if description:
        msg += f"\n📝 {description}\n"
    if requirements:
        msg += f"\n✅ <b>المتطلبات:</b> {requirements}\n"
    if salary:
        msg += f"💰 <b>الراتب:</b> {salary}\n"
    if source:
        msg += f"🌐 <b>المصدر:</b> {source}\n"
    if link and link.startswith("http"):
        msg += f"🔗 <a href='{link}'>اضغط للتقديم</a>\n"
    msg += f"\n{tags}\n━━━━━━━━━━━━━━━\n📢 @iraqjopsforall"
    return msg

# ==================== نشر الوظائف ====================
paused = False

def post_jobs(chat_id, count, category, province):
    send_message(chat_id, f"🔍 جاري البحث عن {count} وظيفة {category} في {province}...\nقد يستغرق هذا 30 ثانية ⏳")
    jobs = search_real_jobs(count, category, province)

    if not jobs:
        send_message(chat_id, "❌ لم أجد وظائف، حاول مرة أخرى أو غيّر التخصص.")
        return

    send_message(chat_id, f"✅ وجدت {len(jobs)} وظيفة، جاري النشر...")
    posted = 0
    for job in jobs:
        msg = format_job(job, province, category)
        if send_to_channel(msg):
            job_id = hashlib.md5((job.get("title","") + job.get("company","") + province + datetime.now().isoformat()).encode()).hexdigest()
            mark_posted(job_id, job.get("title",""), province)
            posted += 1
            time.sleep(2)

    send_message(chat_id, f"🎉 تم نشر {posted} وظيفة في {province} على @iraqjopsforall!")

def handle_action(action_data, chat_id):
    global paused
    action = action_data.get("action")

    if action == "post_jobs":
        threading.Thread(target=post_jobs, args=(
            chat_id,
            int(action_data.get("count", 5)),
            action_data.get("category", "كل التخصصات"),
            action_data.get("province", "كل العراق")
        ), daemon=True).start()

    elif action == "choose_province":
        send_message(chat_id, "🗺 اختر المحافظة:", reply_markup=provinces_keyboard())

    elif action == "stats":
        conn = sqlite3.connect(DB_FILE)
        total = conn.execute("SELECT COUNT(*) FROM posted_jobs").fetchone()[0]
        today = conn.execute("SELECT COUNT(*) FROM posted_jobs WHERE posted_at >= date('now')").fetchone()[0]
        top = conn.execute("SELECT province, COUNT(*) c FROM posted_jobs GROUP BY province ORDER BY c DESC LIMIT 5").fetchall()
        conn.close()
        stats = "\n".join([f"  • {p[0]}: {p[1]}" for p in top]) or "  لا توجد بيانات"
        send_message(chat_id, f"""📊 <b>إحصائيات @iraqjopsforall</b>

📌 إجمالي الوظائف: <b>{total}</b>
📅 اليوم: <b>{today}</b>
🗺 أكثر المحافظات:
{stats}
⏰ النشر التلقائي: {'⏸ موقوف' if paused else '✅ يعمل'}""")

    elif action == "pause":
        paused = True
        send_message(chat_id, "⏸ تم إيقاف النشر التلقائي.")

    elif action == "resume":
        paused = False
        send_message(chat_id, "▶️ تم تشغيل النشر التلقائي!")

# ==================== معالجة الرسائل ====================
def handle_message(update):
    if "callback_query" in update:
        cb = update["callback_query"]
        chat_id = cb["message"]["chat"]["id"]
        data = cb.get("data", "")
        answer_callback(cb["id"])
        parts = data.split(":")

        if parts[0] == "prov":
            province = ":".join(parts[1:])
            send_message(chat_id, f"✅ اخترت: <b>{province}</b>\n\nاختر التخصص:",
                        reply_markup=categories_keyboard(province))
        elif parts[0] == "cat":
            province, category = parts[1], parts[2]
            send_message(chat_id, f"✅ المحافظة: <b>{province}</b>\nالتخصص: <b>{category}</b>\n\nكم وظيفة؟",
                        reply_markup=count_keyboard(province, category))
        elif parts[0] == "cnt":
            province, category, count = parts[1], parts[2], int(parts[3])
            threading.Thread(target=post_jobs, args=(chat_id, count, category, province), daemon=True).start()
        return

    msg = update.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    text = msg.get("text", "").strip()
    if not chat_id or not text:
        return

    add_admin(chat_id)

    if text == "/start":
        send_message(chat_id, """👋 <b>أهلاً! بوت وظائف العراق الذكي 🇮🇶</b>

يبحث عن وظائف <b>حقيقية</b> من الإنترنت!

اختر من القائمة أو اكتب مباشرة:
- "انشر 5 وظائف هندسة في البصرة"
- "انشر 10 وظائف تسويق في بغداد"
- "الإحصائيات" """,
        reply_markup={"keyboard": [
            [{"text": "🗺 اختر محافظة وانشر"}, {"text": "📊 الإحصائيات"}],
            [{"text": "⏸ إيقاف التلقائي"}, {"text": "▶️ تشغيل التلقائي"}]
        ], "resize_keyboard": True})
        return

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

    send_message(chat_id, "🤔 جاري التفكير...")
    response = ask_gemini(text)
    if not response:
        send_message(chat_id, "❌ حدث خطأ، حاول مرة أخرى.")
        return

    try:
        clean = response.strip().replace("```json","").replace("```","").strip()
        action_data = json.loads(clean)
        if "action" in action_data:
            handle_action(action_data, chat_id)
            return
    except:
        pass

    send_message(chat_id, response)

# ==================== النشر التلقائي ====================
def auto_post_loop():
    time.sleep(300)
    while True:
        if not paused:
            log.info("🔄 نشر تلقائي...")
            for province in ["بغداد", "البصرة", "أربيل"]:
                try:
                    jobs = search_real_jobs(2, "كل التخصصات", province)
                    for job in jobs:
                        msg = format_job(job, province)
                        if send_to_channel(msg):
                            job_id = hashlib.md5((job.get("title","") + province + datetime.now().isoformat()).encode()).hexdigest()
                            mark_posted(job_id, job.get("title",""), province)
                            time.sleep(3)
                except Exception as e:
                    log.error(f"خطأ: {e}")
            for admin in get_admins():
                send_message(admin, "📢 تم النشر التلقائي ✅")
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
    log.info("🚀 تشغيل البوت...")
    init_db()
    send_to_channel("🇮🇶 <b>بوت وظائف العراق الذكي يعمل!</b>\nيبحث عن وظائف حقيقية من الإنترنت 🔍")
    threading.Thread(target=auto_post_loop, daemon=True).start()
    polling_loop()

if __name__ == "__main__":
    main()
