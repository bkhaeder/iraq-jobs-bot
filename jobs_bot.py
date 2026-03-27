import time
import requests
import random
import threading

# ================== إعدادات ==================
BOT_TOKEN = "8615364517:AAG-y4NpcbNpA803DwJVtHBpIca5GfnB_gY"
CHANNEL_ID = "@iraqjopsforall"
ADMIN_ID = 7590912344

# ================== الحالة ==================
settings = {
    "enabled": False,
    "interval": 900,
    "topics": ["cv", "tools", "ai", "tips", "fun"]
}

last_post_time = 0

# ================== ارسال ==================
def send(chat_id, text, keyboard=None):
    data = {
        "chat_id": chat_id,
        "text": text
    }
    if keyboard:
        data["reply_markup"] = keyboard

    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json=data)

# ================== الكيبورد ==================
def main_keyboard():
    return {
        "keyboard": [
            [{"text": "🚀 تشغيل"}, {"text": "⛔ إيقاف"}],
            [{"text": "⏱ كل 15 دقيقة"}, {"text": "⏱ كل 30 دقيقة"}],
            [{"text": "🎯 CV"}, {"text": "🤖 AI"}, {"text": "💡 نصائح"}],
            [{"text": "📢 نشر الآن"}]
        ],
        "resize_keyboard": True
    }

# ================== المحتوى ==================
def generate():
    topic = random.choice(settings["topics"])

    if topic == "cv":
        return "📄 نصيحة CV:\nلا تكتب خريج بس، اكتب شنو تعرف تسوي 🔥"

    if topic == "ai":
        return "🤖 استخدم AI حتى تكتب CV وتطور نفسك بسهولة"

    if topic == "tools":
        return "🧰 استخدم Canva حتى تسوي CV احترافي خلال دقائق"

    if topic == "tips":
        return "💡 لا ترسل نفس CV لكل شركة، عدله حسب الوظيفة"

    return "😂 معلومة: AI ممكن يرفض CV قبل ما يشوفه بشر 😅"

# ================== نشر ==================
def post():
    global last_post_time

    if not settings["enabled"]:
        return

    if time.time() - last_post_time < settings["interval"]:
        return

    msg = generate()

    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
        "chat_id": CHANNEL_ID,
        "text": msg
    })

    print("✅ نشر")
    last_post_time = time.time()

# ================== معالجة ==================
def handle(msg):
    text = msg.get("text", "")
    chat_id = msg["chat"]["id"]

    if chat_id != ADMIN_ID:
        return

    if text == "/start":
        send(chat_id, "🔥 لوحة التحكم", main_keyboard())

    elif text == "🚀 تشغيل":
        settings["enabled"] = True
        send(chat_id, "✅ تم التشغيل")

    elif text == "⛔ إيقاف":
        settings["enabled"] = False
        send(chat_id, "⛔ تم الإيقاف")

    elif text == "⏱ كل 15 دقيقة":
        settings["interval"] = 900
        send(chat_id, "⏱ كل 15 دقيقة")

    elif text == "⏱ كل 30 دقيقة":
        settings["interval"] = 1800
        send(chat_id, "⏱ كل 30 دقيقة")

    elif text == "🎯 CV":
        settings["topics"] = ["cv"]
        send(chat_id, "🎯 محتوى CV فقط")

    elif text == "🤖 AI":
        settings["topics"] = ["ai"]
        send(chat_id, "🤖 محتوى AI فقط")

    elif text == "💡 نصائح":
        settings["topics"] = ["tips"]
        send(chat_id, "💡 نصائح فقط")

    elif text == "📢 نشر الآن":
        msg = generate()
        send(chat_id, "📢 تم النشر")
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
            "chat_id": CHANNEL_ID,
            "text": msg
        })

# ================== تشغيل ==================
def main():
    global last_post_time
    print("🚀 البوت شغال")

    offset = 0

    while True:
        try:
            # جلب الرسائل
            r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}").json()

            for u in r.get("result", []):
                offset = u["update_id"] + 1
                if "message" in u:
                    handle(u["message"])

            # تشغيل النشر التلقائي
            post()

        except Exception as e:
            print("Error:", e)

        time.sleep(2)

if __name__ == "__main__":
    main()
