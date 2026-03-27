#!/usr/bin/env python3
import time
import hashlib
import logging
import sqlite3
import random
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ==================== الإعدادات الثابتة (بياناتك) ====================
BOT_TOKEN = "8615364517:AAG-y4NpcbNpA803DwJVtHBpIca5GfnB_gY" 
CHANNEL_ID = "@iraqjopsforall"
GEMINI_API_KEY = "AIzaSyA_5I1nCiqa5m5x7pvqQLbcwLf3wpCQ-Bw"
DB_FILE = "iraq_job_tips_final.db"

TOPICS = [
    "تحسين الـ CV لشركات النفط",
    "مهارات المقابلة الشخصية (Interview)",
    "أسرار التقديم على الشركات الأجنبية",
    "تعلم الإنجليزية المهنية",
    "إدارة الوقت والإنتاجية",
    "استخدام LinkedIn للعثور على فرص",
    "العمل الحر والربح من الإنترنت",
    "كيفية التفاوض على الراتب",
    "أهمية الشهادات المهنية (PMP, HSE)",
    "تحفيز يومي للشباب الباحث عن عمل"
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("bot_log.log", encoding="utf-8"), logging.StreamHandler()],
)
log = logging.getLogger(__name__)

# ==================== قاعدة البيانات ====================
def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS posted_content (
                hash_id TEXT PRIMARY KEY, topic TEXT, posted_at TEXT
            )
        """)

def is_duplicate(content: str) -> bool:
    h = hashlib.md5(content.encode("utf-8")).hexdigest()
    with sqlite3.connect(DB_FILE) as conn:
        return conn.execute("SELECT 1 FROM posted_content WHERE hash_id=?", (h,)).fetchone() is not None

def save_posted(content: str, topic: str):
    h = hashlib.md5(content.encode("utf-8")).hexdigest()
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("INSERT INTO posted_content VALUES (?, ?, ?)", (h, topic, datetime.now().isoformat()))

# ==================== خدمات API ====================
def get_session():
    s = requests.Session()
    retries = Retry(total=5, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=retries))
    return s

HTTP = get_session()

def generate_professional_tip(topic: str) -> str:
    prompt = (
        f"أنت خبير توظيف في البصرة. اكتب نصيحة مهنية قصيرة ومفيدة جداً باللهجة العراقية 'البيضاء' عن: {topic}. "
        "اجعل الأسلوب مشجعاً وقوياً ومختصراً جداً (ما لا يزيد عن 3 أسطر)."
    )
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    # رفع الـ Temperature لتقليل التكرار
    payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.95}}
    
    try:
        r = HTTP.post(url, json=payload, timeout=30)
        data = r.json()
        if "candidates" in data:
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        log.error(f"خطأ Gemini: {e}")
    return ""

def send_post_with_buttons(text: str):
    """إرسال الرسالة مع أزرار تفاعلية وروابط صحيحة"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    clean_channel_link = f"https://t.me/{CHANNEL_ID[1:]}"
    share_url = f"https://t.me/share/url?url={clean_channel_link}&text=انضم%20لقناة%20نصائح%20العمل%20في%20العراق"

    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "📢 مشاركة القناة", "url": share_url},
                {"text": "💼 قائمة الوظائف", "url": clean_channel_link}
            ]
        ]
    }
    
    payload = {
        "chat_id": CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "reply_markup": reply_markup
    }
    
    try:
        r = HTTP.post(url, json=payload, timeout=20)
        return r.json().get("ok", False)
    except Exception as e:
        log.error(f"خطأ تليجرام: {e}")
        return False

# ==================== المحرك الرئيسي المحدث ====================
def start_automated_system(interval_min: int):
    log.info("🚀 نظام النشر التلقائي المحدث والمؤمن يعمل الآن...")
    while True:
        try:
            success = False
            attempts = 0
            
            while not success and attempts < 3:
                topic = random.choice(TOPICS)
                tip = generate_professional_tip(topic) 
                
                if tip and len(tip) > 10 and not is_duplicate(tip):
                    final_message = (
                        f"✨ <b>نصيحة مهنية: {topic}</b>\n"
                        f"━━━━━━━━━━━━━━\n\n"
                        f"{tip}\n\n"
                        f"📍 <i>بالتوفيق لجميع شبابنا</i>\n\n"
                        f"🏷 #نصائح_حيدر #توظيف_العراق"
                    )
                    
                    if send_post_with_buttons(final_message):
                        save_posted(tip, topic)
