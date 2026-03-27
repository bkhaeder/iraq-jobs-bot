#!/usr/bin/env python3
import time, hashlib, logging, sqlite3, random, json, threading
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ==================== الإعدادات الثابتة ====================
BOT_TOKEN = "8615364517:AAG-y4NpcbNpA803DwJVtHBpIca5GfnB_gY" 
CHANNEL_ID = "@iraqjopsforall"
GEMINI_API_KEY = "AIzaSyA_5I1nCiqa5m5x7pvqQLbcwLf3wpCQ-Bw"
DB_FILE = "iraq_bot_step_system.db"

# حالة النظام (التحكم بالمراحل)
state = {
    "active": False,
    "interval": 60,
    "remaining": 0,
    "current_topic": None,
    "step": "START" # START -> TOPIC -> SIZE -> TIME -> READY
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ==================== قاعدة البيانات ====================
def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS posted (h TEXT PRIMARY KEY)")
        conn.commit()

def is_duplicate(txt):
    h = hashlib.md5(txt.encode()).hexdigest()
    with sqlite3.connect(DB_FILE) as conn:
        return conn.execute("SELECT 1 FROM posted WHERE h=?", (h,)).fetchone() is not None

def mark_done(txt):
    h = hashlib.md5(txt.encode()).hexdigest()
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("INSERT OR IGNORE INTO posted VALUES (?)", (h,))
        conn.commit()

# ==================== محرك Gemini المتطور (ضد التكرار) ====================
def gemini_ask(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    # إضافة ملح عشوائي للطلب لضمان تغيير النتيجة دائماً
    random_salt = random.randint(1, 1000000)
    enhanced_prompt = f"{prompt}\n(ملاحظة: اكتب نصاً فريداً تماماً، معرف الطلب: {random_salt})"
    
    payload = {
        "contents": [{"parts": [{"text": enhanced_prompt}]}], 
        "generationConfig": {"temperature": 1.0, "top_p": 0.95}
    }
    try:
        r = requests.post(url, json=payload, timeout=30)
        return r.json()['candidates'][0]['content']['parts'][0]['text'].strip()
    except: return None

def send_msg(chat_id, text, markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if markup: data["reply_markup"] = json.dumps(markup)
    return requests.post(url, json=data)

# ==================== وظيفة النشر الذكية ====================
def perform_publish():
    topic = state["current_topic"] or "نصائح عمل عامة"
    prompt = f"أنت خبير توظيف عراقي فكاهي وذكي. اكتب نصيحة أو معلومة تقنية فريدة جداً باللهجة العراقية عن {topic}. استخدم إيموجيات. لا تكرر الكلام السابق أبداً. 3 أسطر."
    
    # محاولة توليد محتوى غير مكرر حتى 5 مرات
    for _ in range(5):
        content = gemini_ask(prompt)
        if content and not is_duplicate(content):
            msg = f"💡 <b>{topic}</b>\n━━━━━━━━━━━━━━\n\n{content}\n\n📢 @iraqjopsforall"
            kb = {"inline_keyboard": [[{"text": "📢 مشاركة القناة", "url": f"https://t.me/share/url?url=https://t.me/iraqjopsforall"}]]}
            if send_msg(CHANNEL_ID, msg, kb).json().get("ok"):
                mark_done(content)
                return True
    return False

# ==================== محرك النشر التلقائي ====================
def posting_engine():
    while True:
        if state["active"] and state["remaining"] > 0:
            if perform_publish():
                state["remaining"] -= 1
                log.info(f"✅ نُشر. المتبقي: {state['remaining']}")
            time.sleep(state["interval"] * 60)
        else:
            time.sleep(5)

# ==================== لوحة تحكم "نظام الخطوات" ====================
def bot_control():
    offset = 0
    while True:
        try:
            updates = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}&timeout=20").json()
            for up in updates.get("result", []):
                offset = up["update_id"] + 1
                if "message" in up:
                    chat_id = up["message"]["chat"]["id"]
                    if up["message"].get("text") == "/start":
                        state["step"] = "TOPIC"
                        kb = {"inline_keyboard": [
                            [{"text": "💻 تقنية", "callback_data": "set_topic_تقنية"}, {"text": "🤝 مقابلات", "callback_data": "set_topic_مقابلات عمل"}],
                            [{"text": "🤖 ذكاء اصطناعي", "callback_data": "set_topic_ذكاء اصطناعي"}]
                        ]}
                        send_msg(chat_id, "مرحباً حيدر! الخطوة 1: اختر موضوع الحملة:", kb)

                elif "callback_query" in up:
                    query = up["callback_query"]
                    data = query["data"]
                    chat_id = query["message"]["chat"]["id"]

                    if data.startswith("set_topic_"):
                        state["current_topic"] = data.split("_")[2]
                        state["step"] = "SIZE"
                        kb = {"inline_keyboard": [
                            [{"text": "50 منشور", "callback_data": "set_size_50"}, {"text": "100 منشور", "callback_data": "set_size_100"}],
                            [{"text": "250 منشور", "callback_data": "set_size_250"}]
                        ]}
                        send_msg(chat_id, f"✅ اخترت {state['current_topic']}.\nالخطوة 2: اختر حجم الحملة:", kb)

                    elif data.startswith("set_size_"):
                        state["remaining"] = int(data.split("_")[2])
                        state["step"] = "TIME"
                        kb = {"inline_keyboard": [
                            [{"text": "دقيقة واحدة (فحص)", "callback_data": "set_time_1"}, {"text": "ساعة واحدة", "callback_data": "set_time_60"}],
                            [{"text": "6 ساعات", "callback_data": "set_time_360"}]
                        ]}
                        send_msg(chat_id, f"✅ الحجم: {state['remaining']}.\nالخطوة 3: اختر الفاصل الزمني:", kb)

                    elif data.startswith("set_time_"):
                        state["interval"] = int(data.split("_")[2])
                        state["step"] = "READY"
                        kb = {"inline_keyboard": [
                            [{"text": "🚀 اطلق الحملة الآن", "callback_data": "run_now"}],
                            [{"text": "🔄 إعادة ضبط", "callback_data": "reset"}]
                        ]}
                        send_msg(chat_id, f"✅ الوقت: كل {state['interval']} دقيقة.\nالخطوة الأخيرة: هل أنت جاهز؟", kb)

                    elif data == "run_now":
                        state["active"] = True
                        send_msg(chat_id, "🚀 انطلقت الحملة! يمكنك متابعة القناة الآن.")

                    elif data == "reset":
                        state.update({"active": False, "step": "START", "remaining": 0})
                        send_msg(chat_id, "🔄 تم تصفير الإعدادات. أرسل /start للبدء من جديد.")

        except Exception as e: log.error(e)
        time.sleep(1)

if __name__ == "__main__":
    init_db()
    threading.Thread(target=posting_engine, daemon=True).start()
    log.info("نظام الخطوات يعمل...")
    bot_control()
