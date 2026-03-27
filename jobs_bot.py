#!/usr/bin/env python3
import time, hashlib, logging, sqlite3, random, json, threading
import requests

# ==================== الإعدادات الثابتة ====================
BOT_TOKEN = "8615364517:AAG-y4NpcbNpA803DwJVtHBpIca5GfnB_gY" 
CHANNEL_ID = "@iraqjopsforall"
# جرب الموديل المستقر 1.5 فلاش
MODEL_NAME = "gemini-1.5-flash" 
GEMINI_API_KEY = "AIzaSyA_5I1nCiqa5m5x7pvqQLbcwLf3wpCQ-Bw"
DB_FILE = "iraq_bot_stable_v8.db"

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

# ==================== محرك Gemini (نسخة الاستقرار) ====================
def gemini_ask(prompt):
    # استخدام رابط الـ v1beta لضمان التوافق
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"
    
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{"text": f"{prompt} (ID: {random.randint(1,9999)})"}]
        }]
    }
    
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=30)
        data = r.json()
        
        # تشخيص دقيق للخطأ في حال وجد
        if "error" in data:
            log.error(f"❌ خطأ من جوجل API: {data['error'].get('message')}")
            return None

        if "candidates" in data and len(data["candidates"]) > 0:
            parts = data["candidates"][0].get("content", {}).get("parts", [])
            if parts:
                return parts[0].get("text", "").strip()
        
        log.warning(f"⚠️ رد غير متوقع من جوجل: {data}")
        return None
    except Exception as e:
        log.error(f"❌ خطأ تقني: {e}")
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
    prompt = f"اكتب نصيحة مهنية قصيرة جداً (سطرين) باللهجة العراقية عن موضوع {topic} للشباب العراقي. ابدأ مباشرة بدون مقدمات."
    
    for i in range(3):
        content = gemini_ask(prompt)
        if content and not is_duplicate(content):
            msg = f"💡 <b>{topic}</b>\n━━━━━━━━━━━━━━\n\n{content}\n\n📢 @iraqjopsforall"
            kb = {"inline_keyboard": [[{"text": "📢 مشاركة القناة", "url": "https://t.me/iraqjopsforall"}]]}
            if send_msg(CHANNEL_ID, msg, kb):
                mark_done(content)
                return True
        log.info(f"🔄 محاولة {i+1} للتوليد...")
        time.sleep(3)
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
    log.info("🚀 البوت المستقر يعمل الآن.. أرسل /start")
    while True:
        try:
            r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}&timeout=20").json()
            for up in r.get("result", []):
                offset = up["update_id"] + 1
                if "message" in up:
                    cid = up["message"]["chat"]["id"]
                    if up["message"].get("text") == "/start":
                        kb = {"inline_keyboard": [[{"text": "💻 تقنية", "callback_data": "t_تقنية"}]]}
                        send_msg(cid, "<b>اضغط للبدء:</b>", kb)
                
                elif "callback_query" in up:
                    data = up["callback_query"]["data"]
                    cid = up["callback_query"]["message"]["chat"]["id"]
                    if data == "t_تقنية":
                        state.update({"active": True, "remaining": 10, "interval": 1, "current_topic": "تقنية"})
                        send_msg(cid, "🚀 انطلقت حملة تجريبية (10 منشورات كل دقيقة). تحقق من القناة!")
                        threading.Thread(target=perform_publish).start()

        except Exception as e: log.error(e)
        time.sleep(1)

if __name__ == "__main__":
    init_db()
    threading.Thread(target=posting_engine, daemon=True).start()
    bot_control()
