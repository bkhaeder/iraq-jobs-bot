import requests
import time
import logging
import re

# ==================== الإعدادات ====================
BOT_TOKEN = "8615364517:AAG-y4NpcbNpA803DwJVtHBpIca5GfnB_gY"  # ⚠️ على مسؤوليتك
CHANNEL_ID = "@iraqjopsforall"
ADMIN_ID = 7590912344
USER_STATE = {}

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# ==================== قنوات مصدر الوظائف ====================
JOB_CHANNELS = [
    "@JobsBaghdad",
    "@BasraJobs",
    "@ErbilJobs",
    "@NajafJobs"
]

# ==================== صياغة المنشور ====================
def format_job_post(text, province, sector):
    return f"""💼 *وظيفة جديدة*
📍 المحافظة: {province}
🏷️ القطاع: {sector}
📝 التفاصيل: {text}"""

# ==================== لوحة التحكم ====================
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

# ==================== جلب الوظائف من القنوات ====================
def fetch_jobs_from_channels(limit=5):
    """
    يسحب آخر الوظائف من القنوات المعرفة في JOB_CHANNELS.
    """
    jobs = []
    for channel in JOB_CHANNELS:
        try:
            r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?limit=100")
            data = r.json()
            for update in reversed(data.get("result", [])):
                if "message" in update and "text" in update["message"]:
                    msg = update["message"]["text"]
                    if "وظيفة" in msg or "Job" in msg:
                        jobs.append(msg)
                        if len(jobs) >= limit:
                            return jobs
        except Exception as e:
            logging.error(f"Error fetching from {channel}: {e}")
    return jobs

# ==================== معالجة المسار المرحلي ====================
def handle_updates(update):
    if "message" not in update: return
    msg = update["message"]
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")

    if chat_id != ADMIN_ID: return

    if text == "/start" or text == "🔄 إلغاء والبدء من جديد":
        USER_STATE[chat_id] = {"step": "PROVINCE"}
        provinces = ["البصرة", "بغداد", "أربيل", "نينوى", "النجف", "كربلاء", "كركوك", "ميسان"]
        send_telegram(chat_id, "🇮🇶 **مرحبا بك في لوحة تحكم وظائف العراق**\n\n1️⃣ اختر المحافظة:", get_keyboard(provinces))

    elif USER_STATE.get(chat_id, {}).get("step") == "PROVINCE":
        USER_STATE[chat_id]["province"] = text
        USER_STATE[chat_id]["step"] = "SECTOR"
        sectors = ["نفط وغاز", "هندسة", "إدارة ومحاسبة", "طب وصيدلة", "تعليم وتدريس", "مبيعات وتسويق", "حرفيين وفنيين", "سائقين وحراسات"]
        send_telegram(chat_id, f"✅ تم اختيار {text}\n\n2️⃣ اختر قطاع الوظائف:", get_keyboard(sectors))

    elif USER_STATE.get(chat_id, {}).get("step") == "SECTOR":
        USER_STATE[chat_id]["sector"] = text
        USER_STATE[chat_id]["step"] = "LIMIT"
        send_telegram(chat_id, "3️⃣ كم عدد الوظائف التي تريد جلبها؟", get_keyboard(["5 وظائف", "10 وظائف", "20 وظيفة"]))

    elif USER_STATE.get(chat_id, {}).get("step") == "LIMIT":
        limit = int(re.search(r'\d+', text).group())
        USER_STATE[chat_id]["limit"] = limit
        send_telegram(chat_id, "🔎 جاري استخراج الوظائف وطرق التقديم...")

        # جلب الوظائف من القنوات
        raw_jobs = fetch_jobs_from_channels(limit)

        if not raw_jobs:
            send_telegram(chat_id, "❌ لم أجد نتائج حالياً، حاول مرة أخرى.", get_keyboard(["🔄 إلغاء والبدء من جديد"]))
            return

        USER_STATE[chat_id]["posts"] = [format_job_post(job, USER_STATE[chat_id]["province"], USER_STATE[chat_id]["sector"]) for job in raw_jobs]
        USER_STATE[chat_id]["step"] = "PUBLISH"
        send_telegram(chat_id, f"✅ تم العثور على {len(raw_jobs)} وظيفة.\n\n4️⃣ اختر طريقة النشر:", get_keyboard(["⚡️ نشر يدوي فوراً", "📅 جدولة ذكية"]))

    elif USER_STATE.get(chat_id, {}).get("step") == "PUBLISH":
        if "نشر يدوي" in text:
            send_telegram(chat_id, "🚀 جاري النشر في القناة...")
            for post in USER_STATE[chat_id]["posts"]:
                send_telegram(CHANNEL_ID, post)
                time.sleep(2)
            send_telegram(chat_id, "✅ تم نشر جميع الوظائف!", get_keyboard(["🔄 إلغاء والبدء من جديد"]))
        else:
            send_telegram(chat_id, "📅 تم تفعيل الجدولة الذكية. سيتم النشر تلقائياً.", get_keyboard(["🔄 إلغاء والبدء من جديد"]))
        USER_STATE[chat_id] = {}

# ==================== تشغيل البوت ====================
if __name__ == "__main__":
    offset = 0
    print("🚀 البوت يعمل الآن...")
    while True:
        try:
            r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}&timeout=20").json()
            for update in r.get("result", []):
                offset = update["update_id"] + 1
                handle_updates(update)
        except Exception as e:
            print(f"Connection Error: {e}")
        time.sleep(1)
