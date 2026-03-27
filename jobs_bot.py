import requests
from bs4 import BeautifulSoup
import time
import random

# ==================== الإعدادات ====================
BOT_TOKEN = "8615364517:AAG-y4NpcbNpA803DwJVtHBpIca5GfnB_gY"
CHANNEL_ID = "@iraqjopsforall"
ADMIN_ID = 7590912344

USER_STATE = {}
posted_jobs = set()

PROVINCES = ["بغداد", "البصرة", "أربيل", "نينوى", "النجف", "كربلاء", "كركوك", "ميسان"]
SECTORS = ["نفط وغاز", "هندسة", "إدارة ومحاسبة", "طب وصيدلة", "تعليم وتدريس", "مبيعات وتسويق", "حرفيين وفنيين", "سائقين وحراسات"]

# ==================== جلب الوظائف ====================
def fetch_iraqijobs(limit=5):
    jobs = []
    try:
        res = requests.get("https://www.iraqijobs.com/jobs/")
        soup = BeautifulSoup(res.text, "html.parser")
        for job_card in soup.select(".job_listing")[:limit]:
            title = job_card.select_one(".job_title")
            company = job_card.select_one(".company_name")
            link = job_card.select_one("a")
            if title and company and link:
                jobs.append({"title": title.text.strip(), "company": company.text.strip(), "contact": link["href"]})
    except:
        pass
    return jobs

def fetch_akhtaboot(limit=5):
    jobs = []
    try:
        res = requests.get("https://www.akhtaboot.com/en/iraq/jobs/")
        soup = BeautifulSoup(res.text, "html.parser")
        for job_card in soup.select(".job-card")[:limit]:
            title = job_card.select_one(".job-title")
            company = job_card.select_one(".company-name")
            link = job_card.select_one("a")
            if title and company and link:
                jobs.append({"title": title.text.strip(), "company": company.text.strip(), "contact": "https://www.akhtaboot.com"+link["href"]})
    except:
        pass
    return jobs

def fetch_bayt(limit=5):
    jobs = []
    try:
        res = requests.get("https://www.bayt.com/en/iraq/jobs/")
        soup = BeautifulSoup(res.text, "html.parser")
        for job_card in soup.select(".jobCard")[:limit]:
            title = job_card.select_one(".jobTitle")
            company = job_card.select_one(".companyName")
            link = job_card.select_one("a")
            if title and company and link:
                jobs.append({"title": title.text.strip(), "company": company.text.strip(), "contact": "https://www.bayt.com"+link["href"]})
    except:
        pass
    return jobs

def fetch_forasna(limit=5):
    jobs = []
    try:
        res = requests.get("https://forasna.com/")
        soup = BeautifulSoup(res.text, "html.parser")
        for job_card in soup.select(".job-item")[:limit]:
            title = job_card.select_one(".job-title")
            company = job_card.select_one(".job-company")
            link = job_card.select_one("a")
            if title and company and link:
                jobs.append({"title": title.text.strip(), "company": company.text.strip(), "contact": link["href"]})
    except:
        pass
    return jobs

def fetch_wuzzuf(limit=5):
    jobs = []
    try:
        res = requests.get("https://wuzzuf.net/search/jobs/?q=iraq")
        soup = BeautifulSoup(res.text, "html.parser")
        for job_card in soup.select(".css-1gatmva")[:limit]:
            title = job_card.select_one("h2")
            company = job_card.select_one("a.css-17s97q8")
            link = job_card.select_one("a.css-o171kl")
            if title and company and link:
                jobs.append({"title": title.text.strip(), "company": company.text.strip(), "contact": "https://wuzzuf.net"+link["href"]})
    except:
        pass
    return jobs

def fetch_all_jobs(limit=5):
    jobs = []
    jobs.extend(fetch_iraqijobs(limit))
    jobs.extend(fetch_akhtaboot(limit))
    jobs.extend(fetch_bayt(limit))
    jobs.extend(fetch_forasna(limit))
    jobs.extend(fetch_wuzzuf(limit))
    return jobs

# ==================== صياغة الوظائف ====================
def categorize_job(job):
    province = random.choice(PROVINCES)
    sector = random.choice(SECTORS)
    return province, sector

def format_job(job):
    province, sector = categorize_job(job)
    return f"""💼 *{job['title']}*
🏢 الشركة: {job['company']}
📍 المحافظة: {province}
🏷️ القطاع: {sector}
🔗 التقديم: {job['contact']}"""

# ==================== Telegram ====================
def send_telegram(chat_id, text, markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown", "reply_markup": markup}
    requests.post(url, json=payload)

def get_keyboard(options):
    return {"keyboard":[[{"text":o}] for o in options], "resize_keyboard":True}

# ==================== التحكم ====================
def handle(update):
    if "message" not in update: return
    msg = update["message"]
    chat_id = msg["chat"]["id"]
    text = msg.get("text","")

    if chat_id != ADMIN_ID: return

    if text=="/start" or text=="🔄 إعادة":
        USER_STATE[chat_id]={"step":"PROVINCE"}
        send_telegram(chat_id,"اختر المحافظة:",get_keyboard(PROVINCES))

    elif USER_STATE.get(chat_id,{}).get("step")=="PROVINCE":
        USER_STATE[chat_id]["province"]=text
        USER_STATE[chat_id]["step"]="SECTOR"
        send_telegram(chat_id,"اختر القطاع:",get_keyboard(SECTORS))

    elif USER_STATE.get(chat_id,{}).get("step")=="SECTOR":
        USER_STATE[chat_id]["sector"]=text
        USER_STATE[chat_id]["step"]="LIMIT"
        send_telegram(chat_id,"كم عدد الوظائف؟",get_keyboard(["5","10","20"]))

    elif USER_STATE.get(chat_id,{}).get("step")=="LIMIT":
        limit=int(text)
        send_telegram(chat_id,"جاري جلب الوظائف...")
        jobs=fetch_all_jobs(limit)
        if not jobs:
            send_telegram(chat_id,"❌ لم يتم العثور على وظائف")
            return

        USER_STATE[chat_id]["posts"]=[format_job(j) for j in jobs]
        USER_STATE[chat_id]["step"]="PUBLISH"
        send_telegram(chat_id,"اختر طريقة النشر:",get_keyboard(["نشر الآن","نشر تدريجي"]))

    elif USER_STATE.get(chat_id,{}).get("step")=="PUBLISH":
        if "الآن" in text:
            for post in USER_STATE[chat_id]["posts"]:
                send_telegram(CHANNEL_ID,post)
                time.sleep(2)
            send_telegram(chat_id,"✅ تم النشر",get_keyboard(["🔄 إعادة"]))
        else:
            send_telegram(chat_id,"⏳ تم جدولة النشر",get_keyboard(["🔄 إعادة"]))
        USER_STATE[chat_id]={}

# ==================== تشغيل ====================
if __name__=="__main__":
    offset=0
    print("🚀 البوت شغال...")
    while True:
        try:
            res=requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}").json()
            for update in res.get("result",[]):
                offset=update["update_id"]+1
                handle(update)
        except Exception as e:
            print("❌ خطأ:",e)
        time.sleep(1)
