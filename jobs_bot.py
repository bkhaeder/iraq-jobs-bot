import time
import requests
import random
import threading

# ================== إعدادات ==================
BOT_TOKEN = "8615364517:AAG-y4NpcbNpA803DwJVtHBpIca5GfnB_gY"
CHANNEL_ID = "@iraqjopsforall"
ADMIN_ID = 7590912344

# ================== حالة البوت ==================
settings = {
    "enabled": False,
    "interval": 900,   # 15 دقيقة
    "days": 1,
    "topics": ["cv", "tools", "ai", "tips", "fun"]
}

start_time = None

# ================== إرسال ==================
def send(chat_id, text):
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
        "chat_id": chat_id,
        "text": text
    })

def send_channel(text):
    send(CHANNEL_ID, text)

# ================== توليد المحتوى ==================
def generate_content():
    topic = random.choice(settings["topics"])

    if topic == "cv":
        return """📄 نصيحة CV

لا تكتب "خريج جديد" ❌  
اكتب شنو تعرف تسوي ✔️  

🎯 خليهم يشوفون قيمتك بسرعة"""

    elif topic == "tools":
        return """🧰 موقع يفيدك:

canva.com  

🔥 سوِ CV احترافي خلال دقائق"""

    elif topic == "ai":
        return """🤖 AI يفيدك بهالأشياء:

✔️ كتابة CV  
✔️ تحسين LinkedIn  
✔️ كتابة رسالة تقديم  

💡 استغله صح"""

    elif topic == "tips":
        return """💡 نصيحة:

لا ترسل نفس CV لكل وظيفة ❌  

✔️ عدل حسب الوظيفة  
✔️ ركز على المطلوب"""

    else:
        return """😂 معلومة:

AI ممكن يرفض السيفي قبل لا يشوفه بشر 😅  

#تقنية"""

# ================== النشر ==================
def post_loop():
    global start_time

    while settings["enabled"]:
        if time.time() - start_time > settings["days"] * 86400:
            send(ADMIN_ID, "⛔ انتهت مدة النشر التلقائي")
            settings["enabled"] = False
            break

        content = generate_content()
        send_channel(content)
        send(ADMIN_ID, "✅ تم نشر بوست")

        time.sleep(settings["interval"])

# ================== التحكم ==================
def handle(msg):
    text = msg.get("text", "")
    chat_id = msg["chat"]["id"]

    if chat_id != ADMIN_ID:
        return

    # تشغيل
    if text == "/start":
        send(chat_id, """🔥 تحكم البوت:

تشغيل → start  
إيقاف → stop  

تغيير الوقت:
interval 15

تحديد الأيام:
days 3

اختيار المواضيع:
topics cv,ai

المواضيع:
cv - tools - ai - tips - fun
""")

    elif text == "start":
        if not settings["enabled"]:
            settings["enabled"] = True
            start_time = time.time()
            threading.Thread(target=post_loop).start()
            send(chat_id, "🚀 تم تشغيل النشر التلقائي")

    elif text == "stop":
        settings["enabled"] = False
        send(chat_id, "⛔ تم إيقاف النشر")

    elif text.startswith("interval"):
        minutes = int(text.split()[1])
        settings["interval"] = minutes * 60
        send(chat_id, f"⏱ تم ضبط الوقت: {minutes} دقيقة")

    elif text.startswith("days"):
        d = int(text.split()[1])
        settings["days"] = d
        send(chat_id, f"📅 النشر لمدة {d} يوم")

    elif text.startswith("topics"):
        t = text.split()[1]
        settings["topics"] = t.split(",")
        send(chat_id, f"🎯 المواضيع: {settings['topics']}")

# ================== تشغيل ==================
def main():
    print("🚀 البوت شغال...")

    offset = 0

    while True:
        try:
            r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}").json()

            for u in r.get("result", []):
                offset = u["update_id"] + 1
                if "message" in u:
                    handle(u["message"])

        except Exception as e:
            print("Error:", e)

        time.sleep(2)

if __name__ == "__main__":
    main()
