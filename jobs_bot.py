#!/usr/bin/env python3
import time, hashlib, logging, sqlite3, random, json, threading
import requests

# ==================== الإعدادات الثابتة ====================
BOT_TOKEN = "8615364517:AAG-y4NpcbNpA803DwJVtHBpIca5GfnB_gY" 
CHANNEL_ID = "@iraqjopsforall" # تأكد أن هذا اليوزرنيم صحيح للقناة العامة
GEMINI_API_KEY = "AIzaSyA_5I1nCiqa5m5x7pvqQLbcwLf3wpCQ-Bw"
DB_FILE = "iraq_bot_v6.db"

state = {
    "active": False,
    "interval": 60,
    "remaining": 0,
    "current_topic": "نصائح عمل",
    "step": "START"
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

# ==================== محرك Gemini ====================
def gemini_ask(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": f"{prompt} (Request ID: {random.randint(1,99999)})"}]}],
        "generationConfig": {"temperature": 1.0}
    }
    try:
        r = requests.post(url, json=payload, timeout=30)
        return r.json()['candidates'][0]['content']['parts'][0]['text'].strip()
    except Exception as e:
        log.error(f"خطأ Gemini: {e}")
        return None

# ==================== دالة النشر (المصلحة) ====================
def send_msg(chat_id, text, markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if markup:
        payload["reply_markup"] = json.dumps(markup)
    
    try:
        r = requests.post(url, json=payload, timeout=20)
        res = r.json()
        if not res.get("ok"):
            log.error(f"❌ فشل النشر في القناة: {res.get('description')}")
            # إذا كان الخطأ أن البوت ليس مشرفاً، سيظهر هنا في اللوغز
        return res.get("ok", False)
    except Exception as e:
        log.error(f"❌ خطأ اتصال تليجرام: {e}")
        return False

def perform_publish():
    topic = state["current_topic"]
    prompt = f"أنت خبير توظيف عراقي. اكتب نصيحة مهنية قصيرة ومميزة جداً عن {topic} باللهجة العراقية. استخدم إيموجيات. 3 أسطر."
    
    for _ in range(3): # محاولة توليد نص غير مكرر
        content = gemini_ask(prompt)
        if content and not is_duplicate(content):
            msg = f"💡 <b>{topic}</b>\n━━━━━━━━━━━━━━\n\n{content}\n\n📢 @iraqjopsforall"
            kb = {"inline_keyboard": [[{"text": "📢 مشاركة القناة", "url": f"https://t.me/share/url?url=https://t.me/iraqjopsforall"}]]}
            
            if send_msg(CHANNEL_ID, msg, kb):
                mark_done(content)
                return True
    return False

# ==================== المحرك الرئيسي ====================
def posting_engine():
    while True:
        if state["active"] and state["remaining"] > 0:
            if perform_publish():
                state["remaining"] -= 1
                log.info(f"✅ تم النشر. المتبقي: {state['remaining']}")
            time.sleep(state["interval"] * 60)
        else:
            time.sleep(5)

def bot_control():
    offset = 0
    log.info("🚀 البوت يعمل الآن.. أرسل /start في تليجرام للبدء.")
    while True:
        try:
            r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}&timeout=20").json()
            for up in r.get("result", []):
                offset = up["update_id"] + 1
                if "message" in up:
                    cid = up["message"]["chat"]["id"]
                    if up["message"].get("text") == "/start":
                        kb = {"inline_keyboard": [
                            [{"text": "💻 تقنية", "callback_data": "topic_تقنية"}, {"text": "🤝 مقابلات", "callback_data": "topic_المقابلات"}],
                            [{"text": "🤖 ذكاء اصطناعي", "callback_data": "topic_الذكاء الاصطناعي"}]
                        ]}
                        send_msg(cid, "<b>الخطوة 1:</b> اختر موضوع الحملة:", kb)
                
                elif "callback_query" in up:
                    query = up["callback_query"]
                    data = query["data"]
                    cid = query["message"]["chat"]["id"]
                    
                    if data.startswith("topic_"):
                        state["current_topic"] = data.split("_")[1]
                        kb = {"inline_keyboard": [[{"text": "10", "callback_data": "size_10"}, {"text": "50", "callback_data": "size_50"}, {"text": "100", "callback_data": "size_100"}]]}
                        send_msg(cid, f"✅ اخترت: {state['current_topic']}\n<b>الخطوة 2:</b> اختر عدد المنشورات:", kb)
                    
                    elif data.startswith("size_"):
                        state["remaining"] = int(data.split("_")[1])
                        kb = {"inline_keyboard": [[{"text": "دقيقة واحدة", "callback_data": "time_1"}, {"text": "ساعة", "callback_data": "time_60"}]]}
                        send_msg(cid, f"✅ الحجم: {state['remaining']}\n<b>الخطوة 3:</b> اختر الوقت بين المنشورات:", kb)
                    
                    elif data.startswith("time_"):
                        state["interval"] = int(data.split("_")[1])
                        kb = {"inline_keyboard": [[{"text": "🚀 اطلق الحملة", "callback_data": "run_now"}]]}
                        send_msg(cid, "<b>الخطوة الأخيرة:</b> اضغط للبدء بالنشر في القناة:", kb)
                    
                    elif data == "run_now":
                        state["active"] = True
                        send_msg(cid, "🚀 انطلقت الحملة! تحقق من القناة الآن.")
                        # تجربة نشر أول منشور فوراً للتأكد
                        threading.Thread(target=perform_publish).start()

        except Exception as e:
            log.error(e)
        time.sleep(1)

if __name__ == "__main__":
    init_db()
    threading.Thread(target=posting_engine, daemon=True).start()
    bot_control()
