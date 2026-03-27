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
DB_FILE = "iraq_bot_open.db"

# حالة النظام
state = {
    "active": False,
    "interval": 60, # دقائق
    "remaining": 0,
    "custom_topic": None # إذا كان None سيعتمد البوت على ذكاء Gemini في اختيار المواضيع
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

# ==================== محرك النشر التلقائي (الذكي) ====================
def posting_engine():
    while True:
        if state["active"] and state["remaining"] > 0:
            # إذا لم يحدد المستخدم موضوعاً، Gemini يبتكر موضوعاً جديداً في كل مرة
            if not state["custom_topic"]:
                topic_prompt = "أنت خبير توظيف عراقي، اقترح موضوعاً واحداً مهماً للنشر عنه اليوم (مثلاً: مقابلة عمل، مهارة تقنية، تطوير ذات). اكتب اسم الموضوع فقط بكلمتين."
                current_topic = gemini_ask(topic_prompt) or "تطوير المهارات"
            else:
                current_topic = state["custom_topic"]

            content_prompt = f"اكتب نصيحة مهنية عملية ومختصرة جداً باللهجة العراقية للشباب عن موضوع: {current_topic}. لا تزد عن 3 أسطر. اجعلها مشجعة."
            content = gemini_ask(content_prompt)
            
            if content and not is_duplicate(content):
                msg = f"✨ <b>نصيحة اليوم: {current_topic}</b>\n━━━━━━━━━━━━━━\n\n{content}\n\n📢 @iraqjopsforall"
                kb = {"inline_keyboard": [[{"text": "📢 مشاركة القناة", "url": f"https://t.me/share/url?url=https://t.me/iraqjopsforall"}]]}
                
                if send_msg(CHANNEL_ID, msg, kb).json().get("ok"):
                    mark_done(content)
                    state["remaining"] -= 1
                    log.info(f"نُشر منشور عن {current_topic}. المتبقي: {state['remaining']}")
            
            time.sleep(state["interval"] * 60)
        else:
            time.sleep(10)

# ==================== لوحة التحكم المفتوحة ====================
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
                    text = msg.get("text", "")

                    if text == "/start":
                        kb = {
                            "inline_keyboard": [
                                [{"text": "🚀 تشغيل/استئناف", "callback_data": "run"}, {"text": "⏸️ إيقاف مؤقت", "callback_data": "stop"}],
                                [{"text": "📦 اختر حجم الحملة", "callback_data": "campaign_size"}],
                                [{"text": "⏱️ ضبط الفاصل الزمني", "callback_data": "set_time"}],
                                [{"text": "📊 حالة البوت", "callback_data": "status"}]
                            ]
                        }
                        send_msg(chat_id, "أهلاً بك في لوحة تحكم القناة! (مفتوحة لجميع المستخدمين حالياً):", kb)

                elif "callback_query" in up:
                    query = up["callback_query"]
                    data = query["data"]
                    chat_id = query["message"]["chat"]["id"]
                    
                    if data == "campaign_size":
                        kb = {"inline_keyboard": [
                            [{"text": "50 منشور", "callback_data": "size_50"}, {"text": "100 منشور", "callback_data": "size_100"}],
                            [{"text": "200 منشور", "callback_data": "size_200"}, {"text": "250 منشور", "callback_data": "size_250"}]
                        ]}
                        send_msg(chat_id, "كم عدد المنشورات التي تود جدولتها؟", kb)
                    
                    elif data.startswith("size_"):
                        val = int(data.split("_")[1])
                        state["remaining"] = val
                        state["active"] = True
                        send_msg(chat_id, f"✅ تم جدولة {val} منشور. البوت سيبدأ النشر الآن.")

                    elif data == "set_time":
                        kb = {"inline_keyboard": [
                            [{"text": "30 دقيقة", "callback_data": "time_30"}, {"text": "ساعة واحدة", "callback_data": "time_60"}],
                            [{"text": "ساعتين", "callback_data": "time_120"}, {"text": "6 ساعات", "callback_data": "time_360"}]
                        ]}
                        send_msg(chat_id, "اختر الوقت الفاصل بين المنشورات:", kb)

                    elif data.startswith("time_"):
                        val = int(data.split("_")[1])
                        state["interval"] = val
                        send_msg(chat_id, f"⏱️ تم ضبط الفاصل الزمني إلى {val} دقيقة.")

                    elif data == "status":
                        status = "✅ يعمل" if state["active"] else "🛑 متوقف"
                        info = f"الحالة: {status}\nالمتبقي بالحملة: {state['remaining']}\nالفاصل: {state['interval']} دقيقة"
                        send_msg(chat_id, info)
                    
                    elif data == "run":
                        state["active"] = True
                        send_msg(chat_id, "🚀 تم تفعيل النشر التلقائي.")
                    
                    elif data == "stop":
                        state["active"] = False
                        send_msg(chat_id, "⏸️ تم إيقاف النشر مؤقتاً.")

        except Exception as e: log.error(e)
        time.sleep(1)

if __name__ == "__main__":
    init_db()
    threading.Thread(target=posting_engine, daemon=True).start()
    log.info("البوت يعمل بنجاح وبدون قيود أدمن.")
    bot_control()
