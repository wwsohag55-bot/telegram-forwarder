import time
import os
import re
import threading
import requests
import queue
import datetime
from flask import Flask
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from dotenv import load_dotenv
load_dotenv()

# ============================================================
# 🌍 GLOBAL CONFIG (No Logic Change)
# ============================================================

BOT_NAME = os.environ.get("BOT_NAME", "Cooker Zone")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8799150227:AAEM7HLL9m_fzONkhLYYEdVHAl2jUh4PPzU")
ADMIN_IDS = os.environ.get("ADMIN_IDS", "5653849290").split(",")
TARGET_GROUP_ID = "-1003543577960" 

LOGIN_URL = os.environ.get("LOGIN_URL", "https://www.konektapremium.net/sign-in")
OTP_URL = os.environ.get("OTP_URL", "https://www.konektapremium.net/client/SMSCDRStats")
LOGIN_HEADERS_ENV = os.environ.get("LOGIN_HEADERS", "")
PANEL_USER = os.environ.get("PANEL_USER", "otpcookers")
PANEL_PASS = os.environ.get("PANEL_PASS", "otpcookers")

# Mapping from Env
COL_MAP = [int(i)-1 for i in os.environ.get("COL_MAPPING", "1,2,3,6").split(",")]
CHECK_DELAY = float(os.environ.get("CHECK_DELAY", 1.0))

IS_FIRST_RUN = True
OTP_QUEUE = queue.Queue()
PROCESSED_OTP_CACHE = set()
CACHE_LOCK = threading.Lock()

threads_status = {"collector": None, "sender": None}

app = Flask(__name__)

@app.route('/')
def home():
    return f"🦅 {BOT_NAME} Status: Ultra-Speed Sniper Active"

# ============================================================
# ⚡ স্মার্ট ইউটিলিটি
# ============================================================

def mask_phone(phone):
    if not phone or len(phone) < 7:
        return phone
    return f"{phone[:-7]}***{phone[-4:]}"

def memory_cleaner():
    global PROCESSED_OTP_CACHE
    while True:
        time.sleep(86400) 
        with CACHE_LOCK:
            PROCESSED_OTP_CACHE.clear()
            send_admin_log("🧹 Memory Cleared Successfully.")

# ============================================================
# 📨 TELEGRAM WORKER (Format Updated to Match Image)
# ============================================================

def telegram_worker():
    """ টেলিগ্রাম সেন্ডার থ্রেড - ছবি অনুযায়ী হুবহু ফরম্যাট """
    tg_session = requests.Session()
    while True:
        try:
            msg_data = OTP_QUEUE.get()
            if msg_data is None: break
            
            phone, country, service, otp, full_msg = msg_data
            masked_number = mask_phone(phone)
            
            # --- Bangladesh Time (UTC + 6) ---
            now_utc = datetime.datetime.utcnow()
            bd_time = now_utc + datetime.timedelta(hours=6)
            formatted_time = bd_time.strftime('%Y-%m-%d %H:%M:%S')
            
            # --- New Message Format based on Image ---
            formatted_text = (
                f"✅ {country} | {service} OTP Received\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"📱 <b>Number:</b> {masked_number}\n"
                f"🔑 <b>OTP Code:</b> {otp}\n"
                f"🛠 <b>Service:</b> {service}\n"
                f"🌍 <b>Country:</b> {country}\n"
                f"⏰ <b>Time:</b> {formatted_time}\n\n"
                f"💬 <b>Message:</b>\n"
                f"<blockquote>{full_msg}</blockquote>"
            )
            
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            
            # Payload with No Buttons
            payload = {
                "chat_id": TARGET_GROUP_ID, 
                "text": formatted_text, 
                "parse_mode": "HTML"
            }
            
            while True:
                res = tg_session.post(url, json=payload, timeout=10)
                if res.status_code == 429:
                    retry_after = res.json().get('parameters', {}).get('retry_after', 3)
                    time.sleep(retry_after)
                    continue
                break
            
            time.sleep(0.5)
            OTP_QUEUE.task_done()
        except Exception:
            time.sleep(1)

# ============================================================
# 🛠 অ্যাডমিন লগ ও ইঞ্জিন টুলস
# ============================================================

def send_telegram(msg, parse_mode="HTML"):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    for admin in ADMIN_IDS:
        try: requests.post(url, json={"chat_id": admin, "text": msg, "parse_mode": parse_mode}, timeout=10)
        except: pass

def send_admin_log(msg):
    # BD Time for System Log
    now_utc = datetime.datetime.utcnow()
    bd_time = now_utc + datetime.timedelta(hours=6)
    t_str = bd_time.strftime('%H:%M:%S')
    
    formatted_msg = f"🛰 <b>{BOT_NAME} SYSTEM LOG</b>\n────────────────\n{msg}\n────────────────\n🕒 {t_str}"
    send_telegram(formatted_msg)

def send_error_telegram(action_failed, reason, target):
    msg = (
        f"🛑 <b>{BOT_NAME} - SYSTEM ALERT</b> 🛑\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"❌ <b>Action Failed:</b> <code>{action_failed}</code>\n"
        f"📍 <b>Target:</b> <code>{target}</code>\n"
        f"⚠️ <b>Reason:</b> <i>{reason}</i>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🕒 {time.strftime('%H:%M:%S')}"
    )
    send_telegram(msg)

COUNTRY_EMOJIS = {
"Afghanistan": "🇦🇫", "Albania": "🇦🇱", "Algeria": "🇩🇿", "Andorra": "🇦🇩", "Angola": "🇦🇴", "Antigua and Barbuda": "🇦🇬", "Argentina": "🇦🇷", "Armenia": "🇦🇲", "Australia": "🇦🇺", "Austria": "🇦🇹", "Azerbaijan": "🇦🇿",
"Bahamas": "🇧🇸", "Bahrain": "🇧🇭", "Bangladesh": "🇧🇩", "Barbados": "🇧🇧", "Belarus": "🇧🇾", "Belgium": "🇧🇪", "Belize": "🇧🇿", "Benin": "🇧🇯", "Bhutan": "🇧🇹", "Bolivia": "🇧🇴", "Bosnia": "🇧🇦", "Botswana": "🇧🇼", "Brazil": "🇧🇷", "Brunei": "🇧🇳", "Bulgaria": "🇧🇬", "Burkina": "🇧🇫", "Burundi": "🇧🇮",
"Cabo Verde": "🇨🇻", "Cambodia": "🇰🇭", "Cameroon": "🇨🇲", "Canada": "🇨🇦", "Central African Republic": "🇨🇫", "Chad": "🇹🇩", "Chile": "🇨🇱", "China": "🇨🇳", "Colombia": "🇨🇴", "Comoros": "🇰🇲", "Congo": "🇨🇬", "DR Congo": "🇨🇩", "Costa Rica": "🇨🇷", "Croatia": "🇭🇷", "Cuba": "🇨🇺", "Cyprus": "🇨🇾", "Czech": "🇨🇿",
"Denmark": "🇩🇰", "Djibouti": "🇩🇯", "Dominica": "🇩🇲", "Dominican Republic": "🇩🇴", "East Timor": "🇹🇱", "Ecuador": "🇪🇨", "Egypt": "🇪🇬", "El Salvador": "🇸🇻", "Equatorial Guinea": "🇬🇶", "Eritrea": "🇪🇷", "Estonia": "🇪🇪", "Eswatini": "🇸🇿", "Ethiopia": "🇪🇹",
"Fiji": "🇫🇯", "Finland": "🇫🇮", "France": "🇫🇷", "Gabon": "🇬🇦", "Gambia": "🇬🇲", "Georgia": "🇬🇪", "Germany": "🇩🇪", "Ghana": "🇬🇭", "Greece": "🇬🇷", "Grenada": "🇬🇩", "Guatemala": "🇬🇹", "Guinea": "🇬🇳", "Guinea-Bissau": "🇬🇼", "Guyana": "🇬🇾",
"Haiti": "🇭🇹", "Honduras": "🇭🇳", "Hong Kong": "🇭🇰", "Hungary": "🇭🇺", "Iceland": "🇮🇸", "India": "🇮🇳", "Indonesia": "🇮🇩", "Iran": "🇮🇷", "Iraq": "🇮🇶", "Ireland": "🇮🇪", "Israel": "🇮🇱", "Italy": "🇮🇹", "Ivory Coast": "🇨🇮",
"Jamaica": "🇯🇲", "Japan": "🇯🇵", "Jordan": "🇯🇴", "Kazakhstan": "🇰🇿", "Kenya": "🇰🇪", "Kiribati": "🇰🇮", "Kosovo": "🇽🇰", "Kuwait": "🇰🇼", "Kyrgyzstan": "🇰🇬", "Laos": "🇱🇦", "Latvia": "🇱🇻", "Lebanon": "🇱🇧", "Lesotho": "🇱🇸", "Liberia": "🇱🇷", "Libya": "🇱🇾", "Liechtenstein": "🇱🇮", "Lithuania": "🇱🇹", "Luxembourg": "🇱🇺",
"Macau": "🇲🇴", "Madagascar": "🇲🇬", "Malawi": "🇲🇼", "Malaysia": "🇲🇾", "Maldives": "🇲🇻", "Mali": "🇲🇱", "Malta": "🇲🇹", "Marshall Islands": "🇲🇭", "Mauritania": "🇲🇷", "Mauritius": "🇲🇺", "Mexico": "🇲🇽", "Micronesia": "🇫🇲", "Moldova": "🇲🇩", "Monaco": "🇲🇨", "Mongolia": "🇲🇳", "Montenegro": "🇲🇪", "Morocco": "🇲🇦", "Mozambique": "🇲🇿", "Myanmar": "🇲🇲",
"Namibia": "🇳🇦", "Nauru": "🇳🇷", "Nepal": "🇳🇵", "Netherlands": "🇳🇱", "New Zealand": "🇳🇿", "Nicaragua": "🇳🇮", "Niger": "🇳🇪", "Nigeria": "🇳🇬", "North Korea": "🇰🇵", "North Macedonia": "🇲🇰", "Norway": "🇳🇴", "Oman": "🇴🇲",
"Pakistan": "🇵🇰", "Palau": "🇵🇼", "Palestine": "🇵🇸", "Panama": "🇵🇦", "Papua New Guinea": "🇵🇬", "Paraguay": "🇵🇾", "Peru": "🇵🇪", "Philippines": "🇵🇭", "Poland": "🇵🇱", "Portugal": "🇵🇹", "Qatar": "🇶🇦", "Romania": "🇷🇴", "Russia": "🇷🇺", "Rwanda": "🇷🇼",
"Saint Kitts and Nevis": "🇰🇳", "Saint Lucia": "🇱🇨", "Saint Vincent": "🇻🇨", "Samoa": "🇼🇸", "San Marino": "🇸🇲", "Sao Tome": "🇸🇹", "Saudi Arabia": "🇸🇦", "Senegal": "🇸🇳", "Serbia": "🇷🇸", "Seychelles": "🇸🇨", "Sierra Leone": "🇸🇱", "Singapore": "🇸🇬", "Slovakia": "🇸🇰", "Slovenia": "🇸🇮", "Solomon Islands": "🇸🇧", "Somalia": "🇸🇴", "South Africa": "🇿🇦", "South Korea": "🇰🇷", "South Sudan": "🇸🇸", "Spain": "🇪🇸", "Sri Lanka": "🇱🇰", "Sudan": "🇸🇩", "Suriname": "🇸🇷", "Sweden": "🇸🇪", "Switzerland": "🇨🇭", "Syria": "🇸🇾",
"Taiwan": "🇹🇼", "Tajikistan": "🇹🇯", "Tanzania": "🇹🇿", "Thailand": "🇹🇭", "Timor-Leste": "🇹🇱", "Togo": "🇹🇬", "Tonga": "🇹🇴", "Trinidad and Tobago": "🇹🇹", "Tunisia": "🇹🇳", "Turkey": "🇹🇷", "Turkmenistan": "🇹🇲", "Tuvalu": "🇹🇻",
"Uganda": "🇺🇬", "Ukraine": "🇺🇦", "UAE": "🇦🇪", "UK": "🇬🇧", "USA": "🇺🇸", "Uruguay": "🇺🇾", "Uzbekistan": "🇺🇿", "Vanuatu": "🇻🇺", "Vatican City": "🇻🇦", "Venezuela": "🇻🇪", "Vietnam": "🇻🇳", "Yemen": "🇾🇪", "Zambia": "🇿🇲", "Zimbabwe": "🇿🇼"
}

def get_emoji(country_text):
    for c, e in COUNTRY_EMOJIS.items():
        if c.lower() in country_text.lower(): return f"{c} {e}"
    return country_text.split()[0] if country_text else "Unknown"

def solve_math(html):
    match = re.search(r'(\d+)\s*([+-])\s*(\d+)', html)
    if match:
        n1, op, n2 = int(match.group(1)), match.group(2), int(match.group(3))
        return str(n1 + n2 if op == '+' else n1 - n2)
    return None

def extract_otp(message):
    msg_str = str(message)
    matches = re.findall(r'\b\d{4,10}\b|\b\d{3,5}[-\s]\d{3,5}\b', msg_str)
    if matches:
        return matches[0].replace(" ", "").replace("-", "")
    match_fallback = re.search(r'\d{3,}', msg_str)
    return match_fallback.group(0) if match_fallback else "N/A"

def parse_env_headers():
    headers = {}
    action_url = None
    default_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"
    headers["User-Agent"] = default_ua
    if not LOGIN_HEADERS_ENV: return headers, None
    clean_text = LOGIN_HEADERS_ENV.replace("\\\n", " ").replace("\\", " ")
    parts = re.split(r'\s-H\s|\s--header\s', clean_text)
    for part in parts:
        part = part.strip().strip("'").strip('"')
        if part.startswith("http") and "://" in part and not action_url:
            action_url = part.split()[0].strip("'").strip('"')
            continue
        if part.startswith("curl") or part.startswith("--") or part.startswith("-"): continue
        if ":" in part:
            try:
                key, val = part.split(":", 1)
                clean_val = re.split(r'\s--', val)[0].strip().strip("'").strip('"')
                headers[key.strip()] = clean_val
            except: pass
    return headers, action_url

# ============================================================
# 🚀 ইউনিভার্সাল স্নাইপার ইঞ্জিন (Main Logic Kept Intact)
# ============================================================

def run_engine():
    global IS_FIRST_RUN
    
    while True:
        session = requests.Session()
        custom_headers, header_action_url = parse_env_headers()
        session.headers.update(custom_headers)
        
        session.headers.update({
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Expires': '0'
        })
        
        try:
            # Login Process
            res_get = session.get(LOGIN_URL, timeout=15)
            soup = BeautifulSoup(res_get.text, 'html.parser')
            form = soup.find('form')
            final_action_url = header_action_url if header_action_url else (urljoin(LOGIN_URL, form.get('action')) if form else LOGIN_URL)

            payload = {}
            if form:
                inputs = form.find_all('input')
                for inp in inputs:
                    name, type_ = inp.get('name'), inp.get('type', 'text').lower()
                    if not name: continue
                    if type_ == 'password': payload[name] = PANEL_PASS
                    elif type_ == 'hidden': payload[name] = inp.get('value', '')
                    elif 'user' in name.lower() or 'email' in name.lower() or 'login' in name.lower():
                        if type_ != 'hidden': payload[name] = PANEL_USER
                    elif 'capt' in name.lower() or 'answer' in name.lower():
                        ans = solve_math(res_get.text)
                        if ans: payload[name] = ans

            if "Content-Type" not in session.headers:
                session.headers["Content-Type"] = "application/x-www-form-urlencoded"
            
            post_res = session.post(final_action_url, data=payload, timeout=15)

            if post_res.status_code == 200:
                send_admin_log("✅ Login Successful! Collector Active.")
                
                while True:
                    try:
                        # Fetch Data
                        refresh_check = session.get(OTP_URL, timeout=10)
                        
                        if "login" in refresh_check.url.lower():
                            send_admin_log("⚠️ Session Expired! Re-logging...")
                            break 

                        raw_rows = []
                        ajax_link = None
                        ajax_patterns = [r'sAjaxSource":\s*"([^"]+)"', r'url:\s*[\'"]([^\'"]+res/data[^\'"]+)[\'"]']
                        for p in ajax_patterns:
                            m = re.search(p, refresh_check.text)
                            if m: ajax_link = urljoin(OTP_URL, m.group(1)); break

                        if ajax_link:
                            ajx_h = session.headers.copy()
                            ajx_h.update({'X-Requested-With': 'XMLHttpRequest', 'Referer': OTP_URL})
                            ajax_res = session.get(ajax_link, headers=ajx_h, timeout=10)
                            try:
                                jd = ajax_res.json()
                                raw_rows = jd.get('aaData', []) or jd.get('data', [])
                            except: pass
                        else:
                            soup_otp = BeautifulSoup(refresh_check.text, 'html.parser')
                            for tr in soup_otp.select("table tr")[1:]:
                                cols = [td.get_text(separator=" ", strip=True) for td in tr.find_all("td")]
                                if cols: raw_rows.append(cols)

                        # Reverse Logic
                        if raw_rows:
                            raw_rows = raw_rows[::-1]

                        target_rows = raw_rows[:100] if raw_rows else []
                        
                        for row in target_rows:
                            if len(row) > max(COL_MAP):
                                phone = str(row[COL_MAP[1]])
                                full_msg = str(row[COL_MAP[3]])
                                otp_code = extract_otp(full_msg)
                                cache_key = f"{phone}_{otp_code}_{full_msg}"
                                
                                with CACHE_LOCK:
                                    if cache_key not in PROCESSED_OTP_CACHE:
                                        PROCESSED_OTP_CACHE.add(cache_key)
                                        
                                        # Queue for Telegram
                                        country = get_emoji(str(row[COL_MAP[0]]))
                                        service = str(row[COL_MAP[2]])
                                        OTP_QUEUE.put((phone, country, service, otp_code, full_msg))
                        
                        time.sleep(CHECK_DELAY)
                    except Exception as e:
                        # Small errors won't break the session
                        time.sleep(CHECK_DELAY)
                        continue

            else:
                send_error_telegram("Login Failed", f"Status: {post_res.status_code}", "Engine")
                time.sleep(10)
        except Exception as e:
            time.sleep(5)
        finally:
            session.close()

# ============================================================
# 🛡️ সুপারভাইজার (Thread Monitor - Removed DB Logic)
# ============================================================

def thread_supervisor():
    while True:
        if threads_status["collector"] is None or not threads_status["collector"].is_alive():
            t = threading.Thread(target=run_engine, daemon=True)
            t.start()
            threads_status["collector"] = t
            send_admin_log("🚀 Collector Thread Assigned.")

        if threads_status["sender"] is None or not threads_status["sender"].is_alive():
            t = threading.Thread(target=telegram_worker, daemon=True)
            t.start()
            threads_status["sender"] = t
            send_admin_log("🚀 Sender Thread Assigned.")
        
        time.sleep(5)

# ======================
# 🔄 স্টার্টআপ
# ======================

# সরাসরি থ্রেডগুলো এবং ফ্লাস্ক রান করা (if __name__ == "__main__": বাদ দেওয়া হয়েছে)
threading.Thread(target=memory_cleaner, daemon=True).start()
threading.Thread(target=thread_supervisor, daemon=True).start()

port = int(os.environ.get("PORT", 5000))
app.run(host='0.0.0.0', port=port)
