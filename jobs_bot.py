#!/usr/bin/env python3
"""
بوت قناة نصائح العمل في العراق - @iraqjopsforall
نسخة احترافية مستقرة 2026 - حيدر باسم
توليد نصائح بذكاء اصطناعي + أزرار تفاعلية + منع تكرار
"""

import time
import hashlib
import logging
import sqlite3
import random
import json
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ==================== الإعدادات الثابتة (بياناتك) ====================
BOT_TOKEN = "8615364517:AAG-y4NpcbNpA803DwJVtHBpIca5GfnB_gY" 
CHANNEL_ID = "@iraqjopsforall"
GEMINI_API_KEY = "AIzaSyA_5I1nCiqa5m5x7pvqQLbcwLf3wpCQ-Bw"
DB_FILE = "iraq_job_tips_final.db"

# مواضيع النصائح المخصصة للشباب العراقي
TOPICS = [
    "تحسين الـ CV لشركات النفط والغاز",
    "مهارات المقابلة الشخصية (Interview)",
    "أسرار التقديم على الشركات الأجنبية في البصرة",
    "تعلم الإنجليزية المهنية وتطوير اللغة",
    "إدارة الوقت والإنتاجية أثناء البحث عن عمل",
    "استخدام LinkedIn للعثور على فرص حقيقية",
    "العمل الحر (Freelance) والربح من الإنترنت",
    "كيفية التفاوض على الراتب والمميزات",
    "أهمية الشهادات المهنية مثل PMP و HSE",
    "نصيحة تحفيزية لصباح الباحثين عن عمل"
]

# إعدادات اللوغز (التسجيل)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("bot_activity.log", encoding="utf-8"), logging.StreamHandler()],
)
log = logging.getLogger(__name__)

# ==================== إدارة قاعدة البيانات ====================
def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS posted_content (
                hash_id TEXT PRIMARY KEY, 
                topic TEXT, 
                posted_at TEXT
            )
        """)
        conn.commit()

def is_duplicate(content: str) -> bool:
    h = hashlib.md5(content.encode("utf-8")).hexdigest()
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.execute("SELECT 1 FROM posted_content WHERE hash_id=?", (h,))
            return cur.fetchone() is not None
    except Exception:
        return False

def save_posted(content: str, topic: str):
    h = hashlib.md5(content.encode("utf-8")).hexdigest()
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("INSERT INTO posted_content VALUES (?, ?, ?)", 
                         (h, topic, datetime.now().isoformat()))
            conn.commit()
    except Exception as e:
        log.error(f"خطأ في حفظ البيانات: {e}")

# ==================== خدمات API والاتصال ====================
def get_session():
    s = requests.Session()
    retries = Retry(total=5, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=retries))
    return s

HTTP = get_session()

def generate_professional_tip(topic: str) -> str:
    """توليد نصيحة احترافية باللهجة العراقية باستخدام Gemini"""
    prompt = (
        f"أنت خبير توظيف عراقي محترف جداً. اكتب نصيحة مهنية عملية ومفيدة باللهجة العراقية 'البيضاء' عن موضوع: {topic}. "
        "اجعل الأسلوب قوياً ومختصراً (3 أسطر كحد أقصى). ابدأ النصيحة مباشرة بدون مقدمات رسمية."
    )
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}], 
        "generationConfig": {"temperature": 0.9}
    }
    
    try:
        r = HTTP.post(url, json=payload, timeout=30)
        data = r.json()
        if "candidates" in data and data["candidates"]:
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        log.error(f"خطأ في Gemini API: {e}")
    return ""

def send_post_with_buttons(text: str):
    """إرسال المنشور مع الأزرار التفاعلية - حل مشكلة اختفاء الأزرار"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    # معالجة روابط القناة
    channel_user = CHANNEL_ID[1:] if CHANNEL_ID.startswith('@') else CHANNEL_ID
    clean_link = f"https://t.me/{channel_user}"
    share_url = f"https://t.me/share/url?url={clean_link}&text=انصحكم%20بمتابعة%20هذه%20القناة%20لنصائح%20العمل"

    # مصفوفة الأزرار بصيغة JSON
    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "📢 مشاركة القناة", "url": share_url},
                {"text": "💼 قائمة الوظائف", "url": clean_link}
            ]
        ]
    }
    
    payload = {
        "chat_id": CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "reply_markup": json.dumps(reply_markup) # تحويل الأزرار لنص JSON لضمان الظهور
    }
    
    try:
        r = HTTP.post(url, data=payload, timeout=20)
        res = r.json()
        if not res.get("ok"):
            log.error(f"فشل إرسال تليجرام: {res.get('description')}")
        return res.get("ok", False)
    except Exception as e:
        log.error(f"خطأ اتصال تليجرام: {e}")
        return False

# ==================== المحرك الرئيسي (تشغيل مستمر) ====================
def start_automated_system(interval_min: int):
    log.info(f"🚀 البوت يعمل الآن! القناة: {CHANNEL_ID} | التوقيت: كل {interval_min} دقيقة.")
    init_db() 
    
    while True:
        try:
            success = False
            attempts = 0
            
            # محاولة توليد محتوى غير مكرر (3 محاولات) لتجنب الحلقات المفرغة
            while not success and attempts < 3:
                topic = random.choice(TOPICS)
                tip = generate_professional_tip(topic) 
                
                if tip and len(tip) > 10 and not is_duplicate(tip):
                    # تنسيق المنشور
                    final_message = (
                        f"✨ <b>نصيحة مهنية: {topic}</b>\n"
                        f"━━━━━━━━━━━━━━\n\n"
                        f"{tip}\n\n"
                        f"📍 <i>بالتوفيق لجميع شبابنا في مسيرتهم</i>\n\n"
                        f"🏷 #نصائح_عمل #العراق #مستقبلكم"
                    )
                    
                    if send_post_with_buttons(final_message):
                        save_posted(tip, topic)
                        log.info(f"✅ تم النشر بنجاح عن موضوع: {topic}")
                        success = True
                    else:
                        log.warning("⚠️ فشل الإرسال، قد يكون بسبب صلاحيات الأدمن.")
                        break # الخروج للمحاولة في الدورة القادمة
                else:
                    attempts += 1
                    log.info(f"♻️ محتوى مكرر أو قصير، محاولة {attempts}/3...")
                    time.sleep(3) # انتظار بسيط بين المحاولات

            if not success:
                log.warning("⚠️ تعذر النشر في هذه الدورة لتجنب التكرار.")

        except Exception as e:
            log.error(f"⚠️ خطأ مفاجئ في الحلقة الرئيسية: {e}")
            
        # الانتظار للدورة القادمة
        log.info(f"💤 سأنتظر لمدة {interval_min} دقيقة حتى المنشور القادم...")
        time.sleep(interval_min * 60)

# ==================== نقطة الانطلاق ====================
if __name__ == "__main__":
    # تشغيل النشر التلقائي (مثلاً كل 60 دقيقة)
    try:
        start_automated_system(interval_min=60)
    except KeyboardInterrupt:
        log.info("تم إيقاف البوت يدوياً.")
