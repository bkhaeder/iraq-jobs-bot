import time
import requests
import random

# ================== إعدادات ==================
BOT_TOKEN = "8615364517:AAG-y4NpcbNpA803DwJVtHBpIca5GfnB_gY"
CHANNEL_ID = "@iraqjopsforall"
ADMIN_ID = 7590912344

# ================== الحالة ==================
settings = {
    "enabled": False,
    "interval": 300,  # الافتراضي 5 دقائق
    "topics": ["cv", "tools", "ai", "tips", "fun"]
}

posted_messages = set()  # لتجنب التكرار

# ================== ارسال ==================
def send(chat_id, text, keyboard=None):
    data = {"chat_id": chat_id, "text": text}
    if keyboard:
        data["reply_markup"] = keyboard
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json=data)

# ================== الكيبورد ==================
def main_keyboard():
    return {
        "keyboard": [
            [{"text": "🚀 تشغيل"}, {"text": "⛔ إيقاف"}],
            [{"text": "⏱ 5 دقائق"}, {"text": "⏱ 10 دقائق"}, {"text": "⏱ 15 دقائق"}, {"text": "⏱ 30 دقيقة"}],
            [{"text": "🎯 CV"}, {"text": "🤖 AI"}, {"text": "💡 نصائح"}],
            [{"text": "📢 نشر الآن"}]
        ],
        "resize_keyboard": True
    }

# ================== المحتوى ==================
def generate():
    templates = {
        "cv": [
            "📄 نصيحة CV: لا تكتب بس خريج، اذكر شنو تعرف تسوي وكون مختصر 🔥",
            "📄 CVك أهم شي يبين شغلك مو بس شهادتك! 😉",
            "📄 خلي CVك يلمع، ألوان وخطوط مرتبة 👌"
        ],
        "ai": [
            "🤖 AI يساعدك تكتب CV ويختصر وقتك بشكل رهيب",
            "🤖 استخدم تقنيات AI لتطوير نفسك بسرعة ⚡",
            "🤖 AI مو بس للمبرمجين، يساعدك كلش تتعلم وتبدع"
        ],
        "tools": [
            "🧰 Canva يسوي CV احترافي خلال دقائق 😎",
            "🧰 Google Docs يوفر قوالب جاهزة CV بسهولة",
            "🧰 LinkedIn مهم لتعديل CVك ومتابعة الشركات"
        ],
        "tips": [
            "💡 لا ترسل نفس CV لكل شركة، عدله حسب الوظيفة",
            "💡 رسالة التقديم القصيرة ممكن ترفع فرصك 🔥",
            "💡 ترتيب الخبرات أهم شي، خلي الأهم بالأول"
        ],
        "fun": [
            "😂 معلومة: AI ممكن يرفض CV قبل ما يشوفه بشر 😅",
            "😂 كل شركة تحب CV مرتب، مو طول حچي 😎",
            "😂 اجعل CVك يقرأه صاحب العمل بحماس، لا ينعس 😴"
        ]
    }

    topic = random.choice(settings["topics"])
    msg = random.choice(templates[topic])

    # منع التكرار
    while msg in posted_messages:
        msg = random.choice(templates[topic])

    posted_messages.add(msg)
    return msg

# ================== نشر ==================
def post():
    if not settings["enabled"]:
        return
    msg = generate()
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
        "chat_id": CHANNEL_ID,
        "text": msg
    })
    print("✅ نشر:", msg)

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

    elif text == "⏱ 5 دقائق":
        settings["interval"] = 300
        send(chat_id, "⏱ كل 5 دقائق")

    elif text == "⏱ 10 دقائق":
        settings["interval"] = 600
        send(chat_id, "⏱ كل 10 دقائق")

    elif text == "⏱ 15 دقائق":
        settings["interval"] = 900
        send(chat_id, "⏱ كل 15 دقيقة")

    elif text == "⏱ 30 دقيقة":
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
    last_post = time.time()
    offset = 0

    print("🚀 البوت شغال")

    while True:
        try:
            r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}").json()
            for u in r.get("result", []):
                offset = u["update_id"] + 1
                if "message" in u:
                    handle(u["message"])

            # نشر تلقائي
            if settings["enabled"] and time.time() - last_post >= settings["interval"]:
                post()
                last_post = time.time()

        except Exception as e:
            print("Error:", e)

        time.sleep(2)

if __name__ == "__main__":
    main()
