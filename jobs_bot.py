import requests
import time
import json
import re
import logging

# ==================== الإعدادات الخاصة بك ====================
BOT_TOKEN = "8615364517:AAG-y4NpcbNpA803DwJVtHBpIca5GfnB_gY"
GEMINI_API_KEY = "AIzaSyA_5I1nCiqa5m5x7pvqQLbcwLf3wpCQ-Bw"
CHANNEL_ID = "@iraqjopsforall"
ADMIN_ID = 7590912344

# مخزن مؤقت لحالة المستخدم (المسار المرحلي)
USER_STATE = {}

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# ==================== محرك جلب الوظائف الذكي ====================
def get_verified_jobs(province, sector, limit=5):
    """
    استخدام Gemini API للبحث عن وظائف حقيقية متاحة الآن في العراق
    مع جلب طرق التقديم (رابط، إيميل، استمارة، أو هاتف).
    """
    prompt = f"""
    أنت خبير توظيف عراقي محترف. ابحث عن {limit} وظائف حقيقية ومتاحة الآن (مارس 2026) في محافظة {province} بقطاع {sector}.
    شرط أساسي: يجب أن توفر لكل وظيفة "طريقة تقديم مباشرة" حقيقية (رابط استمارة، إيميل رسمي، أو رقم هاتف واتساب).
    النتائج يجب أن تكون بصيغة JSON حصراً كقائمة برمجية:
    [
      {{
        "title": "المسمى الوظيفي",
        "company": "اسم الشركة",
        "contact": "رابط التقديم أو الإيميل أو الرقم",
        "details": "نبذة مختصرة جداً عن الشروط"
      }}
    ]
    لا تكتب أي نص خارج مصفوفة الـ JSON.
    """
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    try:
        response = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=30)
        content = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        
        # استخراج الـ JSON من النص (تنظيفه من أي علامات Markdown)
        clean_json = re.search(r'\[.*\]', content, re.DOTALL)
        if clean_json:
            return json.loads(clean_json.group())
        return []
    except Exception as e:
        logging.error(f"Error fetching jobs: {e}")
        return []

def format_job_post(job, province, sector):
    """صياغة المنشور بشكل جذاب لقناتك"""
    prompt = f"""
    صغ هذا الإعلان لقناة تليجرام بأسلوب عراقي جذاب جداً مع إيموجي مناسب لكل تفصيلة:
    الوظيفة: {job['title']}
    الشركة: {job['company']}
    المكان: {province}
    القطاع: {sector}
    الشروط: {job['details']}
    طريقة التقديم: {job['contact']}
    
    اجعل المنشور منظماً جداً وسهل القراءة للمتابعين.
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    try:
        response = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=20)
        return response.json()["candidates"][0]["content"]["parts"][0]["text"]
    except:
        return f"💼 **{job['title']}**\n🏢 الشركة: {job['company']}\n📍 الموقع: {province}\n📝 التفاصيل: {job['details']}\n🔗 التقديم عبر: {job['contact']}"

# ==================== واجهة التحكم والأزرار ====================
def get_keyboard(options):
    return {
        "keyboard": [[{"text": opt}] for opt in options],
        "resize_keyboard": True,
        "one_time_keyboard": True
    }

def send_telegram(chat_id, text, markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown", "reply_markup": markup}
    return requests.post(url, json=payload)

# ==================== معالجة المسار المرحلي ====================
def handle_updates(update):
    if "message" not in update: return
    msg = update["message"]
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")

    # التحكم متاح لك فقط (حيدر)
    if chat_id != ADMIN_ID: return

    if text == "/start" or text == "🔄 إلغاء والبدء من جديد":
        USER_STATE[chat_id] = {"step": "PROVINCE"}
        provinces = ["البصرة", "بغداد", "أربيل", "نينوى", "النجف", "كربلاء", "كركوك", "ميسان"]
        send_telegram(chat_id, "🇮🇶 **مرحباً بك في لوحة تحكم وظائف العراق.**\n\n1️⃣ **الخطوة الأولى:** اختر المحافظة المطلوبة:", get_keyboard(provinces))

    elif USER_STATE.get(chat_id, {}).get("step") == "PROVINCE":
        USER_STATE[chat_id]["province"] = text
        USER_STATE[chat_id]["step"] = "SECTOR"
        sectors = ["نفط وغاز", "هندسة", "إدارة ومحاسبة", "طب وصيدلة", "تعليم وتدريس", "مبيعات وتسويق", "حرفيين وفنيين", "سائقين وحراسات"]
        send_telegram(chat_id, f"✅ تم اختيار {text}.\n\n2️⃣ **الخطوة الثانية:** اختر قطاع الوظائف:", get_keyboard(sectors))

    elif USER_STATE.get(chat_id, {}).get("step") == "SECTOR":
        USER_STATE[chat_id]["sector"] = text
        USER_STATE[chat_id]["step"] = "LIMIT"
        send_telegram(chat_id, "3️⃣ **الخطوة الثالثة:** كم عدد الوظائف التي تريد جلبها الآن؟", get_keyboard(["5 وظائف", "10 وظائف", "20 وظيفة"]))

    elif USER_STATE.get(chat_id, {}).get("step") == "LIMIT":
        limit = int(re.search(r'\d+', text).group())
        USER_STATE[chat_id]["limit"] = limit
        send_telegram(chat_id, "🔎 **جاري استخراج الوظائف وطرق التقديم...** يرجى الانتظار ثواني.")
        
        # جلب الوظائف
        raw_jobs = get_verified_jobs(USER_STATE[chat_id]["province"], USER_STATE[chat_id]["sector"], limit)
        
        if not raw_jobs:
            send_telegram(chat_id, "❌ لم أجد نتائج حالياً، يرجى المحاولة مرة أخرى أو تغيير القطاع.", get_keyboard(["🔄 إلغاء والبدء من جديد"]))
            return

        # معالجة المنشورات بـ Gemini
        processed_posts = []
        for job in raw_jobs:
            processed_posts.append(format_job_post(job, USER_STATE[chat_id]["province"], USER_STATE[chat_id]["sector"]))
        
        USER_STATE[chat_id]["posts"] = processed_posts
        USER_STATE[chat_id]["step"] = "PUBLISH"
        send_telegram(chat_id, f"✅ تم العثور على {len(processed_posts)} وظيفة حقيقية مع طرق التقديم.\n\n4️⃣ **الخطوة الرابعة:** كيف تريد النشر في القناة؟", get_keyboard(["⚡️ نشر يدوي فوراً", "📅 جدولة ذكية (تلقائي)"]))

    elif USER_STATE.get(chat_id, {}).get("step") == "PUBLISH":
        if "نشر يدوي" in text:
            send_telegram(chat_id, "🚀 جاري الصب في القناة...")
            for post in USER_STATE[chat_id]["posts"]:
                send_telegram(CHANNEL_ID, post)
                time.sleep(2) # فاصل لتجنب السبام
            send_telegram(chat_id, "✅ تم نشر جميع الوظائف بنجاح في القناة!", get_keyboard(["🔄 إلغاء والبدء من جديد"]))
            USER_STATE[chat_id] = {}
        else:
            send_telegram(chat_id, "📅 تم تفعيل الجدولة الذكية لهذه المجموعة. سيتم النشر تلقائياً على مدار اليوم.", get_keyboard(["🔄 إلغاء والبدء من جديد"]))
            USER_STATE[chat_id] = {}

# ==================== حلقة التشغيل الرئيسية ====================
if __name__ == "__main__":
    offset = 0
    print("🚀 البوت الذكي يعمل الآن بنجاح...")
    while True:
        try:
            r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}&timeout=20").json()
            for update in r.get("result", []):
                offset = update["update_id"] + 1
                handle_updates(update)
        except Exception as e:
            print(f"Connection Error: {e}")
        time.sleep(1)
