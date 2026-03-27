import requests
import time
import hashlib
import logging
import threading
import re
import json
from bs4 import BeautifulSoup

# ==================== الإعدادات المؤكدة ====================
BOT_TOKEN = "8615364517:AAG-y4NpcbNpA803DwJVtHBpIca5GfnB_gY"
GEMINI_API_KEY = "AIzaSyA_5I1nCiqa5m5x7pvqQLbcwLf3wpCQ-Bw"
CHANNEL_ID = "@iraqjopsforall"
ADMIN_ID = 7590912344

USER_STATE = {}

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# ==================== الأزرار المرحلية ====================
def get_kb_provinces():
    return {"keyboard": [
        [{"text": "📍 البصرة"}, {"text": "📍 بغداد"}, {"text": "📍 نينوى"}],
        [{"text": "📍 أربيل"}, {"text": "📍 كركوك"}, {"text": "📍 النجف"}],
        [{"text": "📍 كربلاء"}, {"text": "📍 ذي قار"}, {"text": "📍 ميسان"}],
        [{"text": "📍 بابل"}, {"text": "📍 الأنبار"}, {"text": "📍 واسط"}]
    ], "resize_keyboard": True}

def get_kb_sectors():
    return {"keyboard": [
        [{"text": "💼 نفط وغاز"}, {"text": "💼 هندسة"}, {"text": "💼 طب وصيدلة"}],
        [{"text": "💼 إدارة ومحاسبة"}, {"text": "💼 مبيعات وتسويق"}, {"text": "💼 تعليم وتدريس"}],
        [{"text": "💼 برمجة وتصميم"}, {"text": "💼 قانون ومحاماة"}, {"text": "💼 حرفيين وعمال"}],
        [{"text": "💼 سياحة وفندقة"}, {"text": "💼 حراسات وأمن"}, {"text": "💼 وظائف عامة"}],
        [{"text": "🔙 إلغاء"}]
    ], "resize_keyboard": True}

def get_kb_limits():
    return {"keyboard": [[{"text": "🔢 5 منشورات"}, {"text": "🔢 20 منشور"}, {"text": "🔢 50 منشور"}]], "resize_keyboard": True}

def get_kb_publish_type():
    return {"keyboard": [[{"text": "⚡️ نشر يدوي فوراً"}, {"text": "📅 جدولة تلقائية"}]], "resize_keyboard": True}

# ==================== محرك البحث الخارق (Google Jobs) ====================
def fetch_jobs_from_web(province, sector, limit=5):
    # استخدام محرك بحث جوجل للوظائف كبديل أقوى
    search_query = f"{sector} في {province} العراق وظائف شاغرة"
    url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
    }
    
    try:
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.content, 'html.parser')
        
        # البحث عن الروابط الخارجية التي تحتوي على كلمات توظيف
        links = soup.find_all('a')
        results = []
        
        for link in links:
            href = link.get('href', '')
            title = link.get_text().strip()
            
            if 'http' in href and len(title) > 10:
                # تصفية الروابط لتكون من مواقع توظيف موثوقة
                if any(site in href for site in ['tanqeeb', 'linkedin', 'bayt', 'akhtaboot', 'drjobs']):
                    results.append({"title": title, "link": href, "prov": province, "sect": sector})
        
        # إذا لم يجد في جوجل، نعود لمحاولة مباشرة في تنقيب مع رأس متصفح جديد
        if not results:
            t_url = f"https://iraq.tanqeeb.com/ar/s/{sector.replace(' ', '-')}-في-{province}"
            r_t = requests.get(t_url, headers=headers, timeout=15)
            soup_t = BeautifulSoup(r_t.content, 'html.parser')
            items = soup_t.find_all('div', class_='item')
            for it in items[:limit]:
                t = it.find('h2').get_text(strip=True) if it.find('h2') else ""
                l = it.find('a')['href'] if it.find('a') else ""
                if t and l:
                    if not l.startswith('http'): l = "https://iraq.tanqeeb.com" + l
                    results.append({"title": t, "link": l, "prov": province, "sect": sector})

        return results[:limit]
    except Exception as e:
        log.error(f"Search Error: {e}")
        return []

def ai_refine(job):
    prompt = f"أنت خبير توظيف عراقي. صغ هذا الإعلان بشكل جذاب جداً لقناة تليجرام مع إيموجي: {job['title']} في {job['prov']}. القسم: {job['sect']}. الرابط: {job['link']}. اجعل الأسلوب باللهجة العراقية المهذبة."
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    try:
        r = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=15)
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except:
        return f"💼 {job['title']}\n📍 {job['prov']}\n🔗 {job['link']}"

# ==================== معالجة الرسائل ====================
def send_m(chat_id, text, markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if markup: payload["reply_markup"] = markup
    return requests.post(url, json=payload)

def handle_updates(update):
    if "message" not in update: return
    msg = update["message"]
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")

    if chat_id != ADMIN_ID: return

    if text == "/start" or text == "🔙 إلغاء":
        USER_STATE[chat_id] = {"step": "PROVINCE"}
        send_m(chat_id, "🇮🇶 مرحباً حيدر.\nالخطوة 1: اختر المحافظة:", get_kb_provinces())

    elif USER_STATE.get(chat_id, {}).get("step") == "PROVINCE":
        USER_STATE[chat_id]["province"] = text.replace("📍 ", "")
        USER_STATE[chat_id]["step"] = "SECTOR"
        send_m(chat_id, f"تم اختيار {text}.\nالخطوة 2: اختر القطاع:", get_kb_sectors())

    elif USER_STATE.get(chat_id, {}).get("step") == "SECTOR":
        USER_STATE[chat_id]["sector"] = text.replace("💼 ", "")
        USER_STATE[chat_id]["step"] = "LIMIT"
        send_m(chat_id, "الخطوة 3: اختر عدد المنشورات:", get_kb_limits())

    elif USER_STATE.get(chat_id, {}).get("step") == "LIMIT":
        limit = int(re.search(r'\d+', text).group())
        USER_STATE[chat_id]["limit"] = limit
        send_m(chat_id, "🔎 جاري البحث في المواقع وقنوات التوظيف... انتظر ثواني.")
        
        jobs = fetch_jobs_from_web(USER_STATE[chat_id]["province"], USER_STATE[chat_id]["sector"], limit)
        if not jobs:
            send_m(chat_id, "❌ لم يتم العثور على نتائج حالياً. جرب قطاعاً آخر أو محافظة أخرى.", get_kb_provinces())
            USER_STATE[chat_id] = {"step": "PROVINCE"}
            return

        processed = [ai_refine(j) for j in jobs]
        USER_STATE[chat_id]["jobs"] = processed
        USER_STATE[chat_id]["step"] = "PUBLISH"
        
        send_m(chat_id, f"✅ تم العثور على {len(processed)} وظيفة حقيقية.\nالخطوة 4: اختر طريقة النشر:", get_kb_publish_type())

    elif USER_STATE.get(chat_id, {}).get("step") == "PUBLISH":
        if text == "⚡️ نشر يدوي فوراً":
            for post in USER_STATE[chat_id]["jobs"]:
                send_m(CHANNEL_ID, post)
                time.sleep(3)
            send_m(chat_id, "✅ تم النشر في القناة بنجاح!", get_kb_provinces())
            USER_STATE[chat_id] = {"step": "PROVINCE"}

if __name__ == "__main__":
    offset = 0
    while True:
        try:
            r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}&timeout=20").json()
            for up in r.get("result", []):
                offset = up["update_id"] + 1
                handle_updates(up)
        except: pass
        time.sleep(1)
