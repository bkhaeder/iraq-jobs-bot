import requests
from bs4 import BeautifulSoup
import time
import json
import random

BOT_TOKEN = "8615364517:AAG-y4NpcbNpA803DwJVtHBpIca5GfnB_gY"
CHANNEL_ID = "@iraqjopsforall"

posted_jobs = set()

# المصادر
SOURCES = [
    {"name": "IraqiJobs", "url": "https://www.iraqijobs.com/jobs/"},
    {"name": "Akhtaboot", "url": "https://www.akhtaboot.com/en/iraq/jobs/"},
    {"name": "Bayt", "url": "https://www.bayt.com/en/iraq/jobs/"},
    {"name": "Forasna", "url": "https://forasna.com/"},
    {"name": "Wuzzuf", "url": "https://wuzzuf.net/search/jobs/?q=iraq"}
]

# المحافظات والقطاعات لتصنيف الوظائف
PROVINCES = ["بغداد", "البصرة", "أربيل", "نينوى", "النجف", "كربلاء", "كركوك", "ميسان"]
SECTORS = ["نفط وغاز", "هندسة", "إدارة ومحاسبة", "طب وصيدلة", "تعليم وتدريس",
           "مبيعات وتسويق", "حرفيين وفنيين", "سائقين وحراسات"]

# ------------------- دوال جلب الوظائف لكل موقع -------------------

def fetch_iraqijobs(limit=10):
    res = requests.get("https://www.iraqijobs.com/jobs/")
    soup = BeautifulSoup(res.text, "html.parser")
    jobs = []
    for job_card in soup.select(".job_listing")[:limit]:
        try:
            title = job_card.select_one(".job_title").text.strip()
            company = job_card.select_one(".company_name").text.strip()
            link = job_card.select_one("a")["href"]
            jobs.append({"title": title, "company": company, "contact": link})
        except: 
            continue
    return jobs

def fetch_akhtaboot(limit=10):
    res = requests.get("https://www.akhtaboot.com/en/iraq/jobs/")
    soup = BeautifulSoup(res.text, "html.parser")
    jobs = []
    for job_card in soup.select(".job-card")[:limit]:
        try:
            title = job_card.select_one(".job-title").text.strip()
            company = job_card.select_one(".company-name").text.strip()
            link = "https://www.akhtaboot.com" + job_card.select_one("a")["href"]
            jobs.append({"title": title, "company": company, "contact": link})
        except: continue
    return jobs

def fetch_bayt(limit=10):
    res = requests.get("https://www.bayt.com/en/iraq/jobs/")
    soup = BeautifulSoup(res.text, "html.parser")
    jobs = []
    for job_card in soup.select(".jobCard")[:limit]:
        try:
            title = job_card.select_one(".jobTitle").text.strip()
            company = job_card.select_one(".companyName").text.strip()
            link = "https://www.bayt.com" + job_card.select_one("a")["href"]
            jobs.append({"title": title, "company": company, "contact": link})
        except: continue
    return jobs

def fetch_forasna(limit=10):
    res = requests.get("https://forasna.com/")
    soup = BeautifulSoup(res.text, "html.parser")
    jobs = []
    for job_card in soup.select(".job-item")[:limit]:
        try:
            title = job_card.select_one(".job-title").text.strip()
            company = job_card.select_one(".job-company").text.strip()
            link = job_card.select_one("a")["href"]
            jobs.append({"title": title, "company": company, "contact": link})
        except: continue
    return jobs

def fetch_wuzzuf(limit=10):
    res = requests.get("https://wuzzuf.net/search/jobs/?q=iraq")
    soup = BeautifulSoup(res.text, "html.parser")
    jobs = []
    for job_card in soup.select(".css-1gatmva")[:limit]:
        try:
            title = job_card.select_one("h2").text.strip()
            company = job_card.select_one("a.css-17s97q8").text.strip()
            link = "https://wuzzuf.net" + job_card.select_one("a.css-o171kl")["href"]
            jobs.append({"title": title, "company": company, "contact": link})
        except: continue
    return jobs

# ------------------- دوال الذكاء لصياغة الرسائل -------------------

def categorize_job(job):
    # تصنيف عشوائي مؤقت حسب المحافظة والقطاع (يمكن تطويره لاحقاً باستخدام NLP)
    province = random.choice(PROVINCES)
    sector = random.choice(SECTORS)
    return province, sector

def format_job_ai(job):
    province, sector = categorize_job(job)
    return f"💼 *{job['title']}*\n🏢 الشركة: {job['company']}\n📍 المحافظة: {province}\n🏷️ القطاع: {sector}\n🔗 التقديم: {job['contact']}"

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHANNEL_ID, "text": msg, "parse_mode": "Markdown"})

# ------------------- الحلقة الرئيسية -------------------

def scrape_and_post():
    all_jobs = []
    all_jobs.extend(fetch_iraqijobs())
    all_jobs.extend(fetch_akhtaboot())
    all_jobs.extend(fetch_bayt())
    all_jobs.extend(fetch_forasna())
    all_jobs.extend(fetch_wuzzuf())

    print(f"🟢 جلب {len(all_jobs)} وظيفة جديدة...")

    for job in all_jobs:
        job_id = job['contact']
        if job_id not in posted_jobs:
            msg = format_job_ai(job)
            send_telegram(msg)
            posted_jobs.add(job_id)
            time.sleep(random.randint(2, 5))  # فاصل عشوائي لتجنب السبام

    print("✅ تم نشر جميع الوظائف الجديدة.")

if __name__ == "__main__":
    while True:
        try:
            scrape_and_post()
            # جدولة ذكية على مدار اليوم
            sleep_time = random.randint(1800, 3600)  # 30-60 دقيقة
            print(f"⏳ الانتظار {sleep_time//60} دقيقة قبل التحديث القادم...")
            time.sleep(sleep_time)
        except Exception as e:
            print(f"❌ خطأ: {e}")
            time.sleep(60)
