import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# ==================== إعدادات البوت ====================
BOT_TOKEN = "8615364517:AAG-y4NpcbNpA803DwJVtHBpIca5GfnB_gY"
CHANNEL_ID = "@iraqjopsforall"
ADMIN_ID = 7590912344

# ==================== إعداد Selenium ====================
options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# ==================== مخزن الحالة ====================
USER_STATE = {}

# ==================== جلب الوظائف ====================
def fetch_jobs(province="العراق", sector="عام", limit=5):
    jobs = []

    driver.get("https://www.iraqijobs.com/jobs/")
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.job"))
        )
    except TimeoutException:
        print("❌ الموقع لم يحمل الوظائف خلال 15 ثانية")
        return []

    job_cards = driver.find_elements(By.CSS_SELECTOR, "div.job")[:limit]

    for job in job_cards:
        try:
            title = job.find_element(By.CSS_SELECTOR, "h2").text
            company = job.find_element(By.CSS_SELECTOR, ".company").text
            link = job.find_element(By.TAG_NAME, "a").get_attribute("href")
            jobs.append({"title": title, "company": company, "link": link})
        except:
            continue

    return jobs

# ==================== إرسال للتليجرام ====================
def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHANNEL_ID, "text": text, "parse_mode": "MarkdownV2"}
    requests.post(url, json=payload)

# ==================== لوحة التحكم ====================
def get_keyboard(options):
    return {"keyboard": [[{"text": opt}] for opt in options],
            "resize_keyboard": True,
            "one_time_keyboard": True}

def handle_updates(update):
    if "message" not in update: return
    msg = update["message"]
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")

    if chat_id != ADMIN_ID: return

    if text == "/start" or text == "🔄 إلغاء والبدء من جديد":
        USER_STATE[chat_id] = {"step": "PROVINCE"}
        provinces = ["البصرة", "بغداد", "أربيل", "نينوى", "النجف", "كربلاء", "كركوك", "ميسان"]
        send_telegram("🇮🇶 اختر المحافظة المطلوبة:")
        return

    step = USER_STATE.get(chat_id, {}).get("step")
    
    if step == "PROVINCE":
        USER_STATE[chat_id]["province"] = text
        USER_STATE[chat_id]["step"] = "SECTOR"
        sectors = ["نفط وغاز", "هندسة", "إدارة ومحاسبة", "طب وصيدلة", "تعليم وتدريس", "مبيعات وتسويق", "حرفيين وفنيين", "سائقين وحراسات"]
        send_telegram(f"✅ تم اختيار {text}. اختر القطاع:")
    elif step == "SECTOR":
        USER_STATE[chat_id]["sector"] = text
        USER_STATE[chat_id]["step"] = "LIMIT"
        send_telegram("كم عدد الوظائف التي تريد جلبها؟ 5، 10، أو 20؟")
    elif step == "LIMIT":
        try:
            limit = int(text)
        except:
            limit = 5
        USER_STATE[chat_id]["limit"] = limit
        send_telegram("🔎 جاري استخراج الوظائف...")
        province = USER_STATE[chat_id]["province"]
        sector = USER_STATE[chat_id]["sector"]

        jobs = fetch_jobs(province, sector, limit)
        if not jobs:
            send_telegram("❌ لم يتم جلب وظائف. حاول مرة أخرى.")
            return

        for job in jobs:
            msg = f"💼 *{job['title'].replace('_','\\_')}*\n🏢 {job['company'].replace('_','\\_')}\n🔗 {job['link']}"
            send_telegram(msg)
            time.sleep(2)

        send_telegram("✅ تم نشر جميع الوظائف!")
        USER_STATE[chat_id] = {}

# ==================== حلقة التشغيل الرئيسية ====================
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
