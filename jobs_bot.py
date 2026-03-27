#!/usr/bin/env python3
import time, hashlib, logging, sqlite3, random, json, threading
import requests

# ==================== الإعدادات الثابتة ====================
BOT_TOKEN = "8615364517:AAG-y4NpcbNpA803DwJVtHBpIca5GfnB_gY" 
CHANNEL_ID = "@iraqjopsforall"
GEMINI_API_KEY = "AIzaSyA_5I1nCiqa5m5x7pvqQLbcwLf3wpCQ-Bw"
DB_FILE = "iraq_bot_fixed_v7.db"

state = {
    "active": False,
    "interval": 60,
    "remaining": 0,
    "current_topic": "تطوير الذات",
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

# ==================== محرك Gemini (المصلح ضد خطأ candidates) ====================
def gemini_ask(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    
    # إعدادات الأمان لتقليل الحجب (Safety Settings)
    payload = {
        "contents": [{"parts": [{"text": f"{prompt} (Unique ID: {random.randint(1,100000)})"}]}],
        "generationConfig": {"temperature": 1.0},
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ]
    }
    
    try:
        r = requests.post(url, json=payload, timeout=30)
        data = r.json()
        
        # التأكد من وجود candidates قبل محاولة قراءتها
        if "candidates" in data and len(data["candidates"]) > 0:
            candidate = data["candidates"][0]
            if "content" in candidate and "parts" in candidate["content"]:
                return candidate["content"]["parts"][0]["text"].strip()
        
        # طباعة الخطأ القادم من جوجل للتشخيص
        log.warning(f"⚠️ رد غير مكتمل من جوجل: {data.get('promptFeedback', 'No Feedback')}")
        return None
    except Exception as e:
        log.error(f"❌ خطأ تقني في Gemini: {e}")
        return None

# ==================== دالة النشر المصلحة ====================
def send_msg(chat_id, text, markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if markup: payload["reply_markup"] = json.dumps(markup)
    
    try:
        r = requests.post(url, json=payload, timeout=20)
        return r.json().get("ok", False)
    except Exception as e:
        log.error(f"❌ خطأ تليجرام: {e}")
        return False

def perform_publish():
    topic = state["current_topic"]
    prompt = f"أنت خبير توظيف عراقي. اكتب نصيحة مهنية قصيرة ومميزة جداً عن {topic} باللهجة العراقية. استخدم إيموجيات. 3 أسطر فقط."
    
    # محاولة توليد النص (3 محاولات في حال فشل Gemini)
    for i in range(3):
        content = gemini_ask(prompt)
        if content and not is_duplicate(content):
            msg = f"💡 <b>{topic}</b>\n━━━━━━━━━━━━━━\n\n{content}\n\n📢 @iraqjopsforall"
            kb = {"inline_keyboard": [[{"text": "📢 مشاركة القناة", "url": f"https://t.me/share/url?url=https://t.me/iraqjopsforall"}]]}
            
            if send_msg(CHANNEL_ID, msg, kb):
                mark_done(content)
                return True
        log.info(f"🔄 محاولة ثانية للتوليد (المحاولة {i+1})...")
        time.sleep(2)
    return False

# ==================== المحرك الرئيسي ونظام الخطوات ====================
def posting_engine():
    while True:
        if state["active"] and state["remaining"] > 0:
            if perform_publish():
                state["remaining"] -= 1
                log.info(f"✅ تم النشر. المتبقي: {state['remaining']}")
            else:
                log.error("❌ فشل النشر بعد عدة محاولات.")
            time.sleep(state["interval"] * 60)
        else:
            time.sleep(5)

def bot_control():
    offset = 0
    log.info("🚀 البوت يعمل الآن.. أرسل /start في تليجرام.")
    while True:
        try:
            r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}&timeout=20").json()
            for up in r.get("result", []):
                offset = up["update_id"] + 1
                if "message" in up:
                    cid = up["message"]["chat"]["id"]
                    if up["message"].get("text") == "/start":
                        kb = {"inline_keyboard": [
                            [{"text": "💻 تقنية", "callback_data": "t_تقنية"}, {"text": "🤝 مقابلات", "callback_data": "t_المقابلات"}],
                            [{"text": "🤖 ذكاء اصطناعي", "callback_data": "t_الذكاء الاصطناعي"}]
                        ]}
                        send_msg(cid, "<b>الخطوة 1:</b> اختر موضوع الحملة:", kb)
                
                elif "callback_query" in up:
                    query = up["callback_query"]
                    data = query["data"]
                    cid = query["message"]["chat"]["id"]
                    
                    if data.startswith("t_"):
                        state["current_topic"] = data.split("_")[1]
                        kb = {"inline_keyboard": [[{"text": "10", "callback_data": "s_10"}, {"text": "50", "callback_data": "s_50"}, {"text": "100", "callback_data": "s_100"}]]}
                        send_msg(cid, f"✅ الموضوع: {state['current_topic']}\n<b>الخطوة 2:</b> اختر عدد المنشورات:", kb)
                    
                    elif data.startswith("s_"):
                        state["remaining"] = int(data.split("_")[1])
                        kb = {"inline_keyboard": [[{"text": "دقيقة", "callback_data": "v_1"}, {"text": "ساعة", "callback_data": "v_60"}]]}
                        send_msg(cid, f"✅ الحجم: {state['remaining']}\n<b>الخطوة 3:</b> اختر الوقت:", kb)
                    
                    elif data.startswith("v_"):
                        state["interval"] = int(data.split("_")[1])
                        kb = {"inline_keyboard": [[{"text": "🚀 ابدأ الآن", "callback_data": "go"}]]}
                        send_msg(cid, "<b>الخطوة الأخيرة:</b> اضغط للبدء:", kb)
                    
                    elif data == "go":
                        state["active"] = True
                        send_msg(cid, "🚀 انطلق البوت! تحقق من القناة الآن.")
                        threading.Thread(target=perform_publish).start()

        except Exception as e:
            log.error(f"خطأ غير متوقع: {e}")
        time.sleep(1)

if __name__ == "__main__":
    init_db()
    threading.Thread(target=posting_engine, daemon=True).start()
    bot_control()
