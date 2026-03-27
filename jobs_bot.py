diff --git a/iraq_jobs_bot.py b/iraq_jobs_bot.py
new file mode 100644
index 0000000000000000000000000000000000000000..af0a779a4e4440aa80a5368e6b255e2150088f90
--- /dev/null
+++ b/iraq_jobs_bot.py
@@ -0,0 +1,790 @@
+#!/usr/bin/env python3
+"""
+بوت وظائف العراق الذكي - @iraqjopsforall
+نسخة محسّنة: جلب وظائف حقيقية مع معالجة قوية للأخطاء وبدائل عند فشل Gemini.
+"""
+
+import os
+import re
+import json
+import time
+import hashlib
+import logging
+import sqlite3
+import threading
+from datetime import datetime, timezone
+from typing import Any, Dict, List, Optional
+
+import requests
+from requests.adapters import HTTPAdapter
+from urllib3.util.retry import Retry
+
+# ==================== الإعدادات ====================
BOT_TOKEN = "8615364517:AAG-y4NpcbNpA803DwJVtHBpIca5GfnB_gY"
CHANNEL_ID = "@iraqjopsforall"
GEMINI_API_KEY = "AIzaSyA_5I1nCiqa5m5x7pvqQLbcwLf3wpCQ-Bw"
+CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "3600"))
+DB_FILE = os.getenv("DB_FILE", "iraq_jobs.db")
+
+# بدائل مجانية (لا تحتاج مفاتيح)
+REMOTIVE_API = "https://remotive.com/api/remote-jobs"
+ARBEITNOW_API = "https://www.arbeitnow.com/api/job-board-api"
+
+IRAQ_PROVINCES = {
+    "بغداد": "Baghdad",
+    "البصرة": "Basra",
+    "نينوى": "Nineveh Mosul",
+    "أربيل": "Erbil",
+    "النجف": "Najaf",
+    "كربلاء": "Karbala",
+    "السليمانية": "Sulaymaniyah",
+    "كركوك": "Kirkuk",
+    "الأنبار": "Anbar",
+    "ديالى": "Diyala",
+    "ذي قار": "Dhi Qar",
+    "بابل": "Babylon",
+    "واسط": "Wasit",
+    "ميسان": "Maysan",
+    "المثنى": "Muthanna",
+    "القادسية": "Qadisiyyah",
+    "صلاح الدين": "Salah al-Din",
+    "دهوك": "Duhok",
+    "حلبجة": "Halabja",
+}
+
+logging.basicConfig(
+    level=logging.INFO,
+    format="%(asctime)s [%(levelname)s] %(message)s",
+    handlers=[logging.FileHandler("bot.log", encoding="utf-8"), logging.StreamHandler()],
+)
+log = logging.getLogger(__name__)
+
+paused = False
+
+
+def _build_session() -> requests.Session:
+    session = requests.Session()
+    retries = Retry(
+        total=3,
+        backoff_factor=1,
+        status_forcelist=[429, 500, 502, 503, 504],
+        allowed_methods=["GET", "POST"],
+    )
+    adapter = HTTPAdapter(max_retries=retries)
+    session.mount("https://", adapter)
+    session.mount("http://", adapter)
+    session.headers.update({"User-Agent": "IraqJobsBot/2.0"})
+    return session
+
+
+HTTP = _build_session()
+
+# ==================== قاعدة البيانات ====================
+def init_db() -> None:
+    conn = sqlite3.connect(DB_FILE)
+    conn.execute(
+        """CREATE TABLE IF NOT EXISTS posted_jobs (
+        id TEXT PRIMARY KEY,
+        title TEXT,
+        company TEXT,
+        province TEXT,
+        url TEXT,
+        posted_at TEXT
+    )"""
+    )
+    conn.execute("""CREATE TABLE IF NOT EXISTS admins (chat_id INTEGER PRIMARY KEY)""")
+    conn.commit()
+    conn.close()
+
+
+def _norm_url(url: str) -> str:
+    return (url or "").strip().lower().rstrip("/")
+
+
+def is_posted_by_url_or_hash(title: str, company: str, url: str) -> bool:
+    key = hashlib.md5(f"{title}|{company}|{_norm_url(url)}".encode("utf-8")).hexdigest()
+    conn = sqlite3.connect(DB_FILE)
+    cur = conn.execute("SELECT 1 FROM posted_jobs WHERE id = ?", (key,))
+    result = cur.fetchone()
+    conn.close()
+    return result is not None
+
+
+def mark_posted(title: str, company: str, province: str, url: str) -> None:
+    key = hashlib.md5(f"{title}|{company}|{_norm_url(url)}".encode("utf-8")).hexdigest()
+    conn = sqlite3.connect(DB_FILE)
+    conn.execute(
+        "INSERT OR IGNORE INTO posted_jobs VALUES (?, ?, ?, ?, ?, ?)",
+        (key, title, company, province, url, datetime.now(timezone.utc).isoformat()),
+    )
+    conn.commit()
+    conn.close()
+
+
+def add_admin(chat_id: int) -> None:
+    conn = sqlite3.connect(DB_FILE)
+    conn.execute("INSERT OR IGNORE INTO admins VALUES (?)", (chat_id,))
+    conn.commit()
+    conn.close()
+
+
+def get_admins() -> List[int]:
+    conn = sqlite3.connect(DB_FILE)
+    rows = conn.execute("SELECT chat_id FROM admins").fetchall()
+    conn.close()
+    return [r[0] for r in rows]
+
+
+# ==================== تيليغرام ====================
+def tg_api(method: str, payload: Dict[str, Any], timeout: int = 20) -> Optional[Dict[str, Any]]:
+    if not BOT_TOKEN:
+        log.error("BOT_TOKEN غير مضبوط في متغيرات البيئة")
+        return None
+    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
+    try:
+        r = HTTP.post(url, json=payload, timeout=timeout)
+        if r.status_code == 200:
+            return r.json()
+        log.error("Telegram %s failed: %s - %s", method, r.status_code, r.text[:200])
+    except Exception as e:
+        log.error("Telegram %s exception: %s", method, e)
+    return None
+
+
+def send_message(chat_id: int, text: str, reply_markup: Optional[Dict[str, Any]] = None) -> None:
+    payload: Dict[str, Any] = {
+        "chat_id": chat_id,
+        "text": text,
+        "parse_mode": "HTML",
+        "disable_web_page_preview": True,
+    }
+    if reply_markup:
+        payload["reply_markup"] = reply_markup
+    tg_api("sendMessage", payload)
+
+
+def send_to_channel(text: str) -> bool:
+    payload = {"chat_id": CHANNEL_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": False}
+    resp = tg_api("sendMessage", payload)
+    return bool(resp and resp.get("ok"))
+
+
+def answer_callback(cb_id: str) -> None:
+    tg_api("answerCallbackQuery", {"callback_query_id": cb_id}, timeout=10)
+
+
+def get_updates(offset: int = 0) -> List[Dict[str, Any]]:
+    if not BOT_TOKEN:
+        return []
+    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
+    try:
+        r = HTTP.get(url, params={"offset": offset, "timeout": 30}, timeout=40)
+        if r.status_code == 200:
+            return r.json().get("result", [])
+    except Exception as e:
+        log.error("get_updates error: %s", e)
+    return []
+
+
+# ==================== لوحات الأزرار ====================
+def provinces_keyboard() -> Dict[str, Any]:
+    provinces = list(IRAQ_PROVINCES.keys())
+    keyboard = []
+    for i in range(0, len(provinces), 3):
+        keyboard.append([{"text": p, "callback_data": f"prov:{p}"} for p in provinces[i : i + 3]])
+    keyboard.append([{"text": "🇮🇶 كل العراق", "callback_data": "prov:كل العراق"}])
+    return {"inline_keyboard": keyboard}
+
+
+def categories_keyboard(province: str) -> Dict[str, Any]:
+    cats = [
+        "هندسة",
+        "تقنية",
+        "محاسبة",
+        "تسويق",
+        "مبيعات",
+        "طب",
+        "تعليم",
+        "إدارة",
+        "برمجة",
+        "تصميم",
+        "موارد بشرية",
+        "قانون",
+    ]
+    keyboard = []
+    for i in range(0, len(cats), 3):
+        keyboard.append([{"text": c, "callback_data": f"cat:{province}:{c}"} for c in cats[i : i + 3]])
+    keyboard.append([{"text": "📋 كل التخصصات", "callback_data": f"cat:{province}:كل التخصصات"}])
+    return {"inline_keyboard": keyboard}
+
+
+def count_keyboard(province: str, category: str) -> Dict[str, Any]:
+    return {
+        "inline_keyboard": [
+            [{"text": str(c), "callback_data": f"cnt:{province}:{category}:{c}"} for c in [3, 5, 10, 15, 20]]
+        ]
+    }
+
+
+# ==================== جلب وظائف من Gemini (محسّن) ====================
+def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
+    if not text:
+        return None
+    clean = text.strip().replace("```json", "").replace("```", "").strip()
+
+    try:
+        data = json.loads(clean)
+        if isinstance(data, dict):
+            return data
+    except Exception:
+        pass
+
+    match = re.search(r"\{[\s\S]*\}", clean)
+    if match:
+        try:
+            data = json.loads(match.group(0))
+            if isinstance(data, dict):
+                return data
+        except Exception:
+            return None
+    return None
+
+
+def _normalize_job(job: Dict[str, Any], province: str) -> Optional[Dict[str, str]]:
+    title = str(job.get("title", "")).strip()
+    company = str(job.get("company", "")).strip()
+    location = str(job.get("location", province)).strip() or province
+    description = str(job.get("description", "")).strip()
+    requirements = str(job.get("requirements", "")).strip()
+    salary = str(job.get("salary", "")).strip()
+    source = str(job.get("source", "")).strip()
+    link = str(job.get("link", "")).strip()
+
+    if not title or not company:
+        return None
+
+    if link and not link.startswith("http"):
+        link = ""
+
+    # لا ننشر وظيفة بلا مصدر ولا رابط إطلاقاً
+    if not source and not link:
+        return None
+
+    return {
+        "title": title,
+        "company": company,
+        "location": location,
+        "description": description,
+        "requirements": requirements,
+        "salary": salary,
+        "source": source,
+        "link": link,
+    }
+
+
+def _gemini_search_jobs(count: int, category: str, province: str) -> List[Dict[str, str]]:
+    if not GEMINI_API_KEY:
+        log.warning("GEMINI_API_KEY غير مضبوط - سيتم استخدام المصادر البديلة")
+        return []
+
+    url = (
+        "https://generativelanguage.googleapis.com/v1beta/models/"
+        f"gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
+    )
+
+    province_en = "Iraq" if province == "كل العراق" else IRAQ_PROVINCES.get(province, "Iraq")
+    cat_text = category if category != "كل التخصصات" else "مختلف التخصصات"
+
+    prompt = f"""
+ابحث الآن في الويب عن وظائف منشورة حديثًا (آخر 30 يومًا) في العراق.
+المحافظة المطلوبة: {province} ({province_en})
+التخصص المطلوب: {cat_text}
+العدد المطلوب: {count}
+
+قواعد صارمة:
+1) ارجع وظائف حقيقية فقط مع روابط صفحة الوظيفة الأصلية.
+2) لا تُنشئ وظائف وهمية.
+3) إذا لم تجد بما يكفي، أرجع المتاح فقط.
+4) المخرجات JSON فقط بالمخطط:
+{{
+  "jobs": [
+    {{
+      "title": "...",
+      "company": "...",
+      "location": "...",
+      "description": "...",
+      "requirements": "...",
+      "salary": "...",
+      "source": "...",
+      "link": "https://..."
+    }}
+  ]
+}}
+""".strip()
+
+    payload = {
+        "contents": [{"parts": [{"text": prompt}]}],
+        "tools": [{"google_search": {}}],
+        "generationConfig": {
+            "temperature": 0.1,
+            "response_mime_type": "application/json",
+        },
+    }
+
+    for attempt in range(1, 4):
+        try:
+            r = HTTP.post(url, json=payload, timeout=45)
+            if r.status_code != 200:
+                log.error("Gemini status=%s body=%s", r.status_code, r.text[:240])
+                continue
+
+            data = r.json()
+            candidates = data.get("candidates", [])
+            if not candidates:
+                log.warning("Gemini returned no candidates")
+                continue
+
+            part_text = ""
+            parts = candidates[0].get("content", {}).get("parts", [])
+            if parts and isinstance(parts, list):
+                part_text = parts[0].get("text", "")
+
+            parsed = _extract_json_object(part_text)
+            if not parsed:
+                log.warning("Gemini JSON parse failed attempt %s", attempt)
+                continue
+
+            jobs = parsed.get("jobs", [])
+            normalized: List[Dict[str, str]] = []
+            for j in jobs:
+                if not isinstance(j, dict):
+                    continue
+                nj = _normalize_job(j, province)
+                if nj:
+                    normalized.append(nj)
+
+            if normalized:
+                return normalized[:count]
+        except Exception as e:
+            log.error("Gemini attempt %s error: %s", attempt, e)
+        time.sleep(1.5)
+
+    return []
+
+
+# ==================== مصادر بديلة واقعية ====================
+def _fallback_from_remotive(count: int, category: str, province: str) -> List[Dict[str, str]]:
+    params = {"limit": 50}
+    if category != "كل التخصصات":
+        params["search"] = category
+    try:
+        r = HTTP.get(REMOTIVE_API, params=params, timeout=30)
+        if r.status_code != 200:
+            return []
+        jobs = r.json().get("jobs", [])
+    except Exception:
+        return []
+
+    results: List[Dict[str, str]] = []
+    for j in jobs:
+        title = str(j.get("title", "")).strip()
+        company = str(j.get("company_name", "")).strip()
+        link = str(j.get("url", "")).strip()
+        location = str(j.get("candidate_required_location", "Remote")).strip()
+        desc = re.sub(r"<[^>]+>", "", str(j.get("description", "")))[:500]
+        if not title or not company or not link:
+            continue
+
+        if province != "كل العراق":
+            # المصدر البديل غالبًا Remote؛ نتجنبه للمحافظة المحددة
+            continue
+
+        results.append(
+            {
+                "title": title,
+                "company": company,
+                "location": location,
+                "description": desc,
+                "requirements": "راجع صفحة الوظيفة",
+                "salary": str(j.get("salary", "")).strip(),
+                "source": "Remotive",
+                "link": link,
+            }
+        )
+        if len(results) >= count:
+            break
+    return results
+
+
+def _fallback_from_arbeitnow(count: int, category: str, province: str) -> List[Dict[str, str]]:
+    try:
+        r = HTTP.get(ARBEITNOW_API, params={"page": 1}, timeout=30)
+        if r.status_code != 200:
+            return []
+        jobs = r.json().get("data", [])
+    except Exception:
+        return []
+
+    results: List[Dict[str, str]] = []
+    for j in jobs:
+        title = str(j.get("title", "")).strip()
+        company = str(j.get("company_name", "")).strip()
+        link = str(j.get("url", "")).strip()
+        location = str(j.get("location", "Remote")).strip()
+        desc = re.sub(r"<[^>]+>", "", str(j.get("description", "")))[:500]
+
+        if not title or not company or not link:
+            continue
+        if category != "كل التخصصات" and category.lower() not in title.lower() and category.lower() not in desc.lower():
+            continue
+        if province != "كل العراق":
+            continue
+
+        results.append(
+            {
+                "title": title,
+                "company": company,
+                "location": location,
+                "description": desc,
+                "requirements": "راجع صفحة الوظيفة",
+                "salary": "غير مذكور",
+                "source": "Arbeitnow",
+                "link": link,
+            }
+        )
+        if len(results) >= count:
+            break
+    return results
+
+
+def search_real_jobs(count: int, category: str, province: str) -> List[Dict[str, str]]:
+    """
+    الاستراتيجية:
+    1) Gemini + بحث ويب + JSON صارم.
+    2) إن عاد أقل من المطلوب أو فشل، نستخدم بدائل API مجانية.
+    """
+    jobs = _gemini_search_jobs(count, category, province)
+
+    if len(jobs) < count:
+        needed = count - len(jobs)
+        jobs.extend(_fallback_from_remotive(needed, category, province))
+
+    if len(jobs) < count:
+        needed = count - len(jobs)
+        jobs.extend(_fallback_from_arbeitnow(needed, category, province))
+
+    # إزالة التكرار
+    dedup: List[Dict[str, str]] = []
+    seen = set()
+    for j in jobs:
+        key = hashlib.md5(f"{j.get('title')}|{j.get('company')}|{_norm_url(j.get('link', ''))}".encode()).hexdigest()
+        if key in seen:
+            continue
+        seen.add(key)
+        dedup.append(j)
+
+    return dedup[:count]
+
+
+def ask_gemini(text: str) -> Optional[str]:
+    if not GEMINI_API_KEY:
+        return "⚠️ يرجى ضبط GEMINI_API_KEY أولاً في متغيرات البيئة."
+
+    url = (
+        "https://generativelanguage.googleapis.com/v1beta/models/"
+        f"gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
+    )
+    provinces_list = "، ".join(IRAQ_PROVINCES.keys())
+    prompt = f"""
+أنت مساعد ذكي لإدارة قناة وظائف عراقية @iraqjopsforall.
+محافظات العراق: {provinces_list}
+
+عند طلب نشر وظائف أجب JSON فقط:
+{{"action":"post_jobs","count":5,"category":"تسويق","province":"البصرة"}}
+عند طلب إحصائيات: {{"action":"stats"}}
+عند إيقاف النشر: {{"action":"pause"}}
+عند تشغيل النشر: {{"action":"resume"}}
+عند طلب اختيار محافظة: {{"action":"choose_province"}}
+للأسئلة العادية أجب بالعربية فقط بدون JSON.
+
+رسالة المدير: {text}
+""".strip()
+
+    payload = {
+        "contents": [{"parts": [{"text": prompt}]}],
+        "generationConfig": {"temperature": 0.2},
+    }
+    try:
+        r = HTTP.post(url, json=payload, timeout=25)
+        if r.status_code == 200:
+            return r.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text")
+        log.error("ask_gemini status=%s body=%s", r.status_code, r.text[:200])
+    except Exception as e:
+        log.error("خطأ Gemini: %s", e)
+    return None
+
+
+# ==================== تنسيق الوظيفة ====================
+def format_job(job: Dict[str, str], province: str = "", category: str = "") -> str:
+    title = job.get("title", "وظيفة شاغرة")
+    company = job.get("company", "")
+    location = job.get("location", province)
+    description = job.get("description", "")
+    requirements = job.get("requirements", "")
+    salary = job.get("salary", "")
+    source = job.get("source", "")
+    link = job.get("link", "")
+
+    tags = "#وظائف_العراق #العراق"
+    if province and province != "كل العراق":
+        tags += f" #{province.replace(' ', '_')}"
+    if category and category != "كل التخصصات":
+        tags += f" #{category}"
+
+    msg = f"💼 <b>{title}</b>\n"
+    if company:
+        msg += f"🏢 {company}\n"
+    msg += f"📍 {location}\n"
+    if description:
+        msg += f"\n📝 {description}\n"
+    if requirements:
+        msg += f"\n✅ <b>المتطلبات:</b> {requirements}\n"
+    if salary and salary != "غير مذكور":
+        msg += f"💰 <b>الراتب:</b> {salary}\n"
+    if source:
+        msg += f"🌐 <b>المصدر:</b> {source}\n"
+    if link and link.startswith("http"):
+        msg += f"🔗 <a href='{link}'>اضغط للتقديم</a>\n"
+
+    msg += f"\n{tags}\n━━━━━━━━━━━━━━━\n📢 @iraqjopsforall"
+    return msg
+
+
+# ==================== نشر الوظائف ====================
+def post_jobs(chat_id: int, count: int, category: str, province: str) -> None:
+    send_message(chat_id, f"🔍 جاري البحث عن {count} وظيفة {category} في {province}...\nقد يستغرق هذا 30-60 ثانية ⏳")
+    jobs = search_real_jobs(count, category, province)
+
+    if not jobs:
+        send_message(chat_id, "❌ لم أجد وظائف حقيقية كافية حالياً. جرّب محافظة/تخصص آخر أو لاحقاً.")
+        return
+
+    send_message(chat_id, f"✅ وجدت {len(jobs)} وظيفة، جاري النشر...")
+    posted = 0
+
+    for job in jobs:
+        title = job.get("title", "")
+        company = job.get("company", "")
+        link = job.get("link", "")
+
+        if is_posted_by_url_or_hash(title, company, link):
+            continue
+
+        msg = format_job(job, province, category)
+        if send_to_channel(msg):
+            mark_posted(title, company, province, link)
+            posted += 1
+            time.sleep(1.5)
+
+    send_message(chat_id, f"🎉 تم نشر {posted} وظيفة في {province} على @iraqjopsforall")
+
+
+# ==================== الأوامر ====================
+def handle_action(action_data: Dict[str, Any], chat_id: int) -> None:
+    global paused
+    action = action_data.get("action")
+
+    if action == "post_jobs":
+        threading.Thread(
+            target=post_jobs,
+            args=(
+                chat_id,
+                int(action_data.get("count", 5)),
+                str(action_data.get("category", "كل التخصصات")),
+                str(action_data.get("province", "كل العراق")),
+            ),
+            daemon=True,
+        ).start()
+
+    elif action == "choose_province":
+        send_message(chat_id, "🗺 اختر المحافظة:", reply_markup=provinces_keyboard())
+
+    elif action == "stats":
+        conn = sqlite3.connect(DB_FILE)
+        total = conn.execute("SELECT COUNT(*) FROM posted_jobs").fetchone()[0]
+        today = conn.execute(
+            "SELECT COUNT(*) FROM posted_jobs WHERE substr(posted_at,1,10)=date('now')"
+        ).fetchone()[0]
+        top = conn.execute(
+            "SELECT province, COUNT(*) c FROM posted_jobs GROUP BY province ORDER BY c DESC LIMIT 5"
+        ).fetchall()
+        conn.close()
+
+        stats = "\n".join([f"  • {p[0] or 'غير محدد'}: {p[1]}" for p in top]) or "  لا توجد بيانات"
+        send_message(
+            chat_id,
+            f"""📊 <b>إحصائيات @iraqjopsforall</b>
+
+📌 إجمالي الوظائف: <b>{total}</b>
+📅 اليوم: <b>{today}</b>
+🗺 أكثر المحافظات:
+{stats}
+⏰ النشر التلقائي: {'⏸ موقوف' if paused else '✅ يعمل'}""",
+        )
+
+    elif action == "pause":
+        paused = True
+        send_message(chat_id, "⏸ تم إيقاف النشر التلقائي.")
+
+    elif action == "resume":
+        paused = False
+        send_message(chat_id, "▶️ تم تشغيل النشر التلقائي!")
+
+
+# ==================== معالجة الرسائل ====================
+def handle_message(update: Dict[str, Any]) -> None:
+    if "callback_query" in update:
+        cb = update["callback_query"]
+        chat_id = cb["message"]["chat"]["id"]
+        data = cb.get("data", "")
+        answer_callback(cb["id"])
+        parts = data.split(":")
+
+        if parts[0] == "prov":
+            province = ":".join(parts[1:])
+            send_message(chat_id, f"✅ اخترت: <b>{province}</b>\n\nاختر التخصص:", reply_markup=categories_keyboard(province))
+        elif parts[0] == "cat":
+            province, category = parts[1], parts[2]
+            send_message(
+                chat_id,
+                f"✅ المحافظة: <b>{province}</b>\nالتخصص: <b>{category}</b>\n\nكم وظيفة؟",
+                reply_markup=count_keyboard(province, category),
+            )
+        elif parts[0] == "cnt":
+            province, category, count = parts[1], parts[2], int(parts[3])
+            threading.Thread(target=post_jobs, args=(chat_id, count, category, province), daemon=True).start()
+        return
+
+    msg = update.get("message", {})
+    chat_id = msg.get("chat", {}).get("id")
+    text = msg.get("text", "").strip()
+    if not chat_id or not text:
+        return
+
+    add_admin(chat_id)
+
+    if text == "/start":
+        send_message(
+            chat_id,
+            """👋 <b>أهلاً! بوت وظائف العراق الذكي 🇮🇶</b>
+
+يبحث عن وظائف <b>حقيقية</b> من مصادر متعددة!
+
+أمثلة:
+- انشر 5 وظائف هندسة في البصرة
+- انشر 10 وظائف تسويق في بغداد
+- الإحصائيات""",
+            reply_markup={
+                "keyboard": [
+                    [{"text": "🗺 اختر محافظة وانشر"}, {"text": "📊 الإحصائيات"}],
+                    [{"text": "⏸ إيقاف التلقائي"}, {"text": "▶️ تشغيل التلقائي"}],
+                ],
+                "resize_keyboard": True,
+            },
+        )
+        return
+
+    if text == "🗺 اختر محافظة وانشر":
+        send_message(chat_id, "🗺 اختر المحافظة:", reply_markup=provinces_keyboard())
+        return
+    if text == "📊 الإحصائيات":
+        handle_action({"action": "stats"}, chat_id)
+        return
+    if text == "⏸ إيقاف التلقائي":
+        handle_action({"action": "pause"}, chat_id)
+        return
+    if text == "▶️ تشغيل التلقائي":
+        handle_action({"action": "resume"}, chat_id)
+        return
+
+    send_message(chat_id, "🤔 جاري التفكير...")
+    response = ask_gemini(text)
+    if not response:
+        send_message(chat_id, "❌ حدث خطأ، حاول مرة أخرى.")
+        return
+
+    parsed = _extract_json_object(response)
+    if parsed and "action" in parsed:
+        handle_action(parsed, chat_id)
+        return
+
+    send_message(chat_id, response)
+
+
+# ==================== النشر التلقائي ====================
+def auto_post_loop() -> None:
+    time.sleep(90)
+    while True:
+        if not paused:
+            log.info("🔄 نشر تلقائي...")
+            for province in ["بغداد", "البصرة", "أربيل"]:
+                try:
+                    jobs = search_real_jobs(2, "كل التخصصات", province)
+                    for job in jobs:
+                        title, company, link = job.get("title", ""), job.get("company", ""), job.get("link", "")
+                        if is_posted_by_url_or_hash(title, company, link):
+                            continue
+                        if send_to_channel(format_job(job, province)):
+                            mark_posted(title, company, province, link)
+                            time.sleep(2)
+                except Exception as e:
+                    log.error("خطأ auto_post_loop: %s", e)
+
+            for admin in get_admins():
+                send_message(admin, "📢 تم النشر التلقائي ✅")
+
+        time.sleep(CHECK_INTERVAL)
+
+
+# ==================== الحلقة الرئيسية ====================
+def polling_loop() -> None:
+    offset = 0
+    log.info("👂 بدء الاستماع...")
+    while True:
+        updates = get_updates(offset)
+        for update in updates:
+            offset = update["update_id"] + 1
+            try:
+                handle_message(update)
+            except Exception as e:
+                log.error("خطأ معالجة الرسالة: %s", e)
+        time.sleep(1)
+
+
+def validate_config() -> bool:
+    ok = True
+    if not BOT_TOKEN:
+        log.error("BOT_TOKEN غير موجود. مثال: export BOT_TOKEN='123:ABC'")
+        ok = False
+    if not CHANNEL_ID:
+        log.error("CHANNEL_ID غير موجود. مثال: export CHANNEL_ID='@iraqjopsforall'")
+        ok = False
+    if not GEMINI_API_KEY:
+        log.warning("GEMINI_API_KEY غير موجود: سيعمل البوت بمصادر بديلة فقط.")
+    return ok
+
+
+def main() -> None:
+    log.info("🚀 تشغيل البوت...")
+    init_db()
+
+    if not validate_config():
+        return
+
+    send_to_channel("🇮🇶 <b>بوت وظائف العراق الذكي يعمل!</b>\nجلب وظائف حقيقية من مصادر متعددة 🔍")
+    threading.Thread(target=auto_post_loop, daemon=True).start()
+    polling_loop()
+
+
+if __name__ == "__main__":
+    main()
