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
DB_FILE = "iraq_bot_final_pro.db"

# حالة النظام
state = {
    "active": False,
    "interval": 60, # دقائق
    "remaining": 0,
    "current_topic": "نصائح مهنية عامة"
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

# ==================== محرك Gemini & Telegram ====================
def gemini_ask(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 1.0}}
    try:
        r = requests.post(url, json=payload, timeout=30)
        return r.json()['candidates'][0]['content']['parts'][0]['text'].strip()
    except: return None

def send_msg(chat_id, text, markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if markup: data["reply_markup"] = json.dumps(markup)
    return requests.post(url, json=data)

# ==================== وظيفة النشر الموحدة ====================
def perform_publish():
    """تقوم بتوليد محتوى ونشره فوراً"""
    topic = state["current_topic"]
    prompt = f"أنت خبير تقني وتوظيف عراقي. اكتب محتوى مفيد جداً (نصيحة أو معلومة) باللهجة العراقية عن: {topic}. لا تزد عن 4 أسطر. اجعلها احترافية."
    content = gemini_ask(prompt)
    
    if content and not is_duplicate(content):
        msg = f"💡 <b>{topic}</b>\n━━━━━━━━━━━━━━\n\n{content}\n\n📢 @iraqjopsforall"
        kb = {"inline_keyboard": [[{"text": "📢 مشاركة القناة", "url": f"https://t.me/share/url?url=https://t.me/iraqjopsforall"}]]}
        
        if send_msg(CHANNEL_ID, msg, kb).json().get("ok"):
            mark_done(content)
            return True
    return False

# ==================== محرك النشر التلقائي المجدول ====================
def posting_engine():
    while True:
        if state["active"] and state["remaining"] > 0:
            if perform_publish():
                state["remaining"] -= 1
                log.info(f"تم النشر التلقائي. المتبقي: {state['remaining']}")
            time.sleep(state["interval"] * 60)
        else:
            time.sleep(5)

# ==================== لوحة التحكم المحدثة ====================
def bot_control():
    offset = 0
    while True:
        try:
            updates = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}&timeout=20").json()
            for up in updates.get("result", []):
                offset = up["update_id"] + 1
                
                if "message" in up:
                    msg = up["message"]
                    chat_id = msg["chat"]["id"]
                    if msg.get("text") == "/start":
                        kb = {
                            "inline_keyboard": [
                                [{"text": "🚀 تشغيل/استئناف", "callback_data": "run"}, {"text": "⏸️ إيقاف مؤقت", "callback_data": "stop"}],
                                [{"text": "📝 اختر موضوع الحملة", "callback_data": "select_topic"}],
                                [{"text": "📦 حجم الحملة", "callback_data": "campaign_size"}, {"text": "⏱️ وقت النشر", "callback_data": "set_time"}],
                                [{"text": "⚡ انشر الآن (يدوي)", "callback_data": "publish_now"}],
                                [{"text": "📊 حالة البوت", "callback_data": "status"}]
                            ]
                        }
                        send_msg(chat_id, "لوحة التحكم المتطورة - @iraqjopsforall\nاختر من الخيارات التالية:", kb)

                elif "callback_query" in up:
                    query = up["callback_query"]
                    data = query["data"]
                    chat_id = query["message"]["chat"]["id"]
                    
                    if data == "select_topic":
                        kb = {"inline_keyboard": [
                            [{"text": "💻 تقنية وبرمجيات", "callback_data": "topic_تقنية وبرمجيات"}, {"text": "🤝 مقابلات العمل", "callback_data": "topic_خوض مقابلات العمل"}],
                            [{"text": "🤖 ذكاء اصطناعي", "callback_data": "topic_ذكاء اصطناعي ومعلومات تقنية"}],
                            [{"text": "🌐 نصائح عامة", "callback_data": "topic_نصائح مهنية عامة"}]
                        ]}
                        send_msg(chat_id, "اختر الموضوع الذي سيتحدث عنه Gemini في هذه الحملة:", kb)

                    elif data.startswith("topic_"):
                        state["current_topic"] = data.split("_")[1]
                        send_msg(chat_id, f"✅ تم تحديد الموضوع: {state['current_topic']}")

                    elif data == "campaign_size":
                        kb = {"inline_keyboard": [
                            [{"text": "50", "callback_data": "size_50"}, {"text": "100", "callback_data": "size_100"}],
                            [{"text": "250", "callback_data": "size_250"}, {"text": "500", "callback_data": "size_500"}]
                        ]}
                        send_msg(chat_id, "اختر عدد المنشورات المطلوب جدولتها:", kb)
                    
                    elif data.startswith("size_"):
                        state["remaining"] = int(data.split("_")[1])
                        state["active"] = True
                        send_msg(chat_id, f"✅ تم جدولة {state['remaining']} منشور.")

                    elif data == "set_time":
                        kb = {"inline_keyboard": [
                            [{"text": "⏰ كل دقيقة (فحص)", "callback_data": "time_1"}, {"text": "⏰ كل 30 دقيقة", "callback_data": "time_30"}],
                            [{"text": "⏰ كل ساعة", "callback_data": "time_60"}, {"text": "⏰ كل 6 ساعات", "callback_data": "time_360"}]
                        ]}
                        send_msg(chat_id, "اختر الفاصل الزمني:", kb)

                    elif data.startswith("time_"):
                        state["interval"] = int(data.split("_")[1])
                        send_msg(chat_id, f"⏱️ تم ضبط الوقت كل {state['interval']} دقيقة.")

                    elif data == "publish_now":
                        send_msg(chat_id, "⏳ جاري توليد ونشر محتوى الآن...")
                        if perform_publish():
                            send_msg(chat_id, "✅ تم النشر اليدوي بنجاح!")
                        else:
                            send_msg(chat_id, "❌ فشل النشر (قد يكون المحتوى مكرراً).")

                    elif data == "status":
                        status = "✅ يعمل" if state["active"] else "🛑 متوقف"
                        info = f"الحالة: {status}\nالموضوع: {state['current_topic']}\nالمتبقي: {state['remaining']}\nالفاصل: {state['interval']} دقيقة"
                        send_msg(chat_id, info)
                    
                    elif data == "run": state["active"] = True; send_msg(chat_id, "🚀 بدأ النشر.")
                    elif data == "stop": state["active"] = False; send_msg(chat_id, "⏸️ تم الإيقاف.")

        except Exception as e: log.error(e)
        time.sleep(1)

if __name__ == "__main__":
    init_db()
    threading.Thread(target=posting_engine, daemon=True).start()
    log.info("البوت الاحترافي يعمل الآن...")
    bot_control()
