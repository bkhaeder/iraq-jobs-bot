import time
import requests

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

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

    print("فتح الموقع...")
    driver.get("https://www.iraqijobs.com/jobs/")

    time.sleep(5)  # ننتظر تحميل الصفحة

    job_cards = driver.find_elements(By.CSS_SELECTOR, ".job_listing")

    print(f"عدد الوظائف الموجودة: {len(job_cards)}")

    for job in job_cards[:5]:
        try:
            title = job.find_element(By.CSS_SELECTOR, ".job_title").text
            company = job.find_element(By.CSS_SELECTOR, ".company_name").text
            link = job.find_element(By.TAG_NAME, "a").get_attribute("href")

            jobs.append({
                "title": title,
                "company": company,
                "link": link
            })
        except:
            continue

    return jobs

# ==================== إرسال إلى التليجرام ====================
def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": CHANNEL_ID,
        "text": text,
        "parse_mode": "Markdown"
    })

# ==================== تشغيل ====================
if __name__ == "__main__":
    jobs = fetch_jobs()

    if not jobs:
        print("❌ ما تم جلب أي وظائف")
    else:
        print("✅ تم جلب وظائف")

        for job in jobs:
            msg = f"""💼 *{job['title']}*
🏢 {job['company']}
🔗 {job['link']}"""

            print(msg)
            send_telegram(msg)
            time.sleep(2)

    driver.quit()
