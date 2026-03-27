#!/usr/bin/env python3
import time, hashlib, logging, sqlite3, random, json, threading
import requests

# ==================== الإعدادات الثابتة ====================
BOT_TOKEN = "8615364517:AAG-y4NpcbNpA803DwJVtHBpIca5GfnB_gY" 
CHANNEL_ID = "@iraqjopsforall"
# تغيير الموديل والرابط للإصدار المستقر v1
MODEL_NAME = "gemini-1.5-flash" 
GEMINI_API_KEY = "AIzaSyA_5I1nCiqa5m5x7pvqQLbcwLf3wpCQ-Bw"
DB_FILE = "iraq_bot_final_v9.db"

state = {"active": False, "interval": 60, "remaining": 0, "current_topic": "تطوير الذات"}

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

# ==================== محرك Gemini (الرابط المستقر v1) ====================
def gemini_ask(prompt):
    # استخدام الإصدار المستقر v1 بدلاً من v1beta
    url = f"https://generativelanguage.googleapis.com/v1/models/{MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"
    
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{"text": f"{prompt} (Request Code: {random.randint(100,999)})"}]
        }]
    }
    
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=30)
        data = r.json()
        
        if "error" in data:
            log.error(f"❌ خطأ API: {data['error'].get('message')}")
            return None

        if "candidates" in data and len(data["candidates"]) > 0:
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        
        return None
    except Exception as e:
        log.error(f"❌ خطأ اتصال: {e}")
        return None

# ==================== وظائف النشر ====================
def send_msg(chat_id, text, markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if markup: payload["reply_markup"] = json.dumps(markup)
    try:
        r = requests.post(url, json=payload, timeout=20)
        return r.json().get("ok", False)
    except: return False

def perform_publish():
    topic = state["current_topic"]
    prompt = f"أنت خبير توظيف عراقي. اكتب نصيحة مهنية باللهجة العراقية عن {topic}. سطرين فقط."
    
    for i in range(3):
        content = gemini_ask(prompt)
        if content and not is_duplicate(content):
            msg = f"💡 <b>{topic}</b>\n━━━━━━━━━━━━━━\n\n{content}\n\n📢 @iraqjopsforall"
            kb = {"inline_keyboard": [[{"text": "📢 مشاركة", "url": "https://t.me/iraqjopsforall"}]]}
            if send_msg(CHANNEL_ID, msg, kb):
                mark_done(content)
                return True
        time.sleep(2)
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
    log.info("🚀 البوت يعمل بالنسخة v1 المستقرة..")
    while True:
        try:
            r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}&timeout=20").json()
            for up in r.get("result", []):
                offset = up["update_id"] + 1
                if "message" in up:
                    cid = up["message"]["chat"]["id"]
                    if up["message"].get("text") == "/start":
                        kb = {"inline_keyboard": [[{"text": "🚀 ابدأ النشر التجريبي", "callback_data": "go"}]]}
                        send_msg(cid, "<b>اضغط للبدء:</b>", kb)
                
                elif "callback_query" in up:
                    cid = up["callback_query"]["message"]["chat"]["id"]
                    state.update({"active": True, "remaining": 50, "interval": 1, "current_topic": "نصائح عامة"})
                    send_msg(cid, "🚀 انطلقت الحملة! سيتم النشر كل دقيقة الآن.")
                    threading.Thread(target=perform_publish).start()

        except Exception as e: log.error(e)
        time.sleep(1)

if __name__ == "__main__":
    init_db()
    threading.Thread(target=posting_engine, daemon=True).start()
    bot_control()
