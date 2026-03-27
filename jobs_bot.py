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

# ==================== إعدادات ====================
BOT_TOKEN = "8615364517:AAG-y4NpcbNpA803DwJVtHBpIca5GfnB_gY"
CHANNEL_ID = "@iraqjopsforall"

# ==================== إعداد Selenium ====================
options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# ==================== جلب الوظائف ====================
def fetch_jobs():
    jobs = []

    driver.get("https://www.iraqijobs.com/jobs/")

    try:
        # ننتظر حتى يظهر أول عنصر وظيفة
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.job"))
        )
    except TimeoutException:
        print("❌ الموقع لم يحمل الوظائف خلال 15 ثانية")
        return []

    job_cards = driver.find_elements(By.CSS_SELECTOR, "div.job")  # كل بطاقة وظيفة

    print(f"عدد الوظائف الموجودة: {len(job_cards)}")

    for job in job_cards[:5]:  # أخذ أول 5 وظائف
        try:
            title = job.find_element(By.CSS_SELECTOR, "h2").text
            company = job.find_element(By.CSS_SELECTOR, ".company").text
            link = job.find_element(By.TAG_NAME, "a").get_attribute("href")
            jobs.append({"title": title, "company": company, "link": link})
        except:
            continue

    return jobs

# ==================== إرسال إلى التليجرام ====================
def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHANNEL_ID, "text": text, "parse_mode": "MarkdownV2"}
    requests.post(url, json=payload)

# ==================== تشغيل ====================
if __name__ == "__main__":
    jobs = fetch_jobs()

    if not jobs:
        print("❌ لم يتم جلب أي وظائف. تحقق من الموقع أو الاتصال بالإنترنت.")
    else:
        print(f"✅ تم جلب {len(jobs)} وظائف")

        for job in jobs:
            # الهروب من الرموز الخاصة في MarkdownV2
            msg = f"💼 *{job['title'].replace('_', '\\_')}*\n🏢 {job['company'].replace('_', '\\_')}\n🔗 {job['link']}"
            print(msg)
            send_telegram(msg)
            time.sleep(2)

    driver.quit()
