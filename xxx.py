"""
ANSHU ETHICALX v5.0
Cyber Security Learning + Safe Local Lab Telegram Bot

Features:
- Hindi + English explanations
- 100 structured cyber-security lessons
- Python, Java and C++ learning tracks
- Safe localhost/self-device labs
- Quizzes and progress tracking
- SQLite database
- Admin statistics/broadcast
- Rate limiting and error handling

Install:
    pip install python-telegram-bot

Set environment variables:
    export BOT_TOKEN="YOUR_NEW_BOT_TOKEN"
    export ADMIN_ID="YOUR_TELEGRAM_NUMERIC_ID"

IMPORTANT:
This project intentionally does NOT implement credential theft, phishing,
brute-force against real services, malware/RAT creation, 2FA bypass,
Wi-Fi password cracking, or attacks against third-party systems.
"""

import logging
import os
import sqlite3
import time
from collections import defaultdict
from datetime import datetime, timezone
from html import escape

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

BOT_NAME = "ANSHU ETHICALX"
VERSION = "5.0"
DB_PATH = os.getenv(
    "DB_PATH",
    "/var/data/anshu_ethicalx.db" if os.path.isdir("/var/data") else "anshu_ethicalx.db",
)

# ============================================================
# TELEGRAM CONFIG — APNI VALUES YAHAN DAALO
# ============================================================
# Example:
# BOT_TOKEN = "123456:ABC..."
# ADMIN_ID = 123456789
#
# Environment variables are optional overrides. Empty/invalid
# Render values will NOT overwrite the values written here.
BOT_TOKEN = "8827214752:AAGeObND4pSDeztVmj8A6dhNqisAlI4XX10"
ADMIN_ID = 6644342214

_env_token = os.getenv("BOT_TOKEN", "").strip()
if _env_token:
    BOT_TOKEN = _env_token

_env_admin = os.getenv("ADMIN_ID", "").strip()
if _env_admin:
    try:
        ADMIN_ID = int(_env_admin)
    except ValueError:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger(BOT_NAME)

RATE_LIMIT = defaultdict(list)
RATE_MAX = 30
RATE_WINDOW = 60


# ---------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                lesson INTEGER DEFAULT 1,
                score INTEGER DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS quiz_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                lesson INTEGER NOT NULL,
                correct INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def upsert_user(user):
    if user is None:
        return
    now = datetime.now(timezone.utc).isoformat()
    with db() as conn:
        conn.execute(
            """
            INSERT INTO users(user_id, username, first_seen, last_seen)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username,
                last_seen=excluded.last_seen
            """,
            (user.id, user.username or "", now, now),
        )
        conn.commit()


def get_progress(user_id):
    with db() as conn:
        row = conn.execute(
            "SELECT lesson, score FROM users WHERE user_id=?",
            (user_id,),
        ).fetchone()
    if row is None:
        return 1, 0
    return int(row["lesson"]), int(row["score"])


def set_progress(user_id, lesson):
    with db() as conn:
        conn.execute(
            "UPDATE users SET lesson=? WHERE user_id=?",
            (lesson, user_id),
        )
        conn.commit()


def add_score(user_id, lesson, correct):
    with db() as conn:
        conn.execute(
            """
            INSERT INTO quiz_scores(user_id, lesson, correct, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                user_id,
                lesson,
                int(correct),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.execute(
            "UPDATE users SET score=score+? WHERE user_id=?",
            (int(correct), user_id),
        )
        conn.commit()


# ---------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------
def allowed(user_id):
    now = time.time()
    events = [t for t in RATE_LIMIT[user_id] if now - t < RATE_WINDOW]
    if len(events) >= RATE_MAX:
        RATE_LIMIT[user_id] = events
        return False
    events.append(now)
    RATE_LIMIT[user_id] = events
    return True


# ---------------------------------------------------------------------
# Lessons
# ---------------------------------------------------------------------
CATEGORIES = {
    "computer": "Computer & Linux",
    "network": "Networking",
    "web": "Web Security",
    "crypto": "Cryptography",
    "defense": "Defensive Security",
    "forensics": "Digital Forensics",
    "programming": "Programming",
    "python": "Python",
    "java": "Java",
    "cpp": "C++",
    "professional": "Professional Security",
}

LESSONS = {}


def add_lesson(num, category, title, hi, en, lab, quiz, options, answer):
    LESSONS[num] = {
        "category": category,
        "title": title,
        "hi": hi,
        "en": en,
        "lab": lab,
        "quiz": quiz,
        "options": options,
        "answer": answer,
    }


# 1-10: Computer/Linux
base_lessons = [
    (1, "computer", "Computer Security Basics",
     "Cyber security ka matlab systems, data aur users ko unauthorized access aur damage se bachana hai.",
     "Cyber security protects systems, data and users from unauthorized access and damage.",
     "Safe lab: `python -m http.server 8000` apne computer par chalao, phir browser me http://127.0.0.1:8000 kholo.",
     "Cyber security ka primary goal kya hai?", ["Data aur systems ki protection", "Passwords churaana", "Random scanning", "Accounts bypass karna"], 0),
    (2, "computer", "Linux Terminal Basics",
     "Terminal se files, folders aur programs ko manage karna seekho.",
     "Learn to manage files, folders and programs from the terminal.",
     "Safe: `pwd`, `ls`, `mkdir lab`, `cd lab`.",
     "Current directory dekhne ka command?", ["pwd", "rm", "mkdir", "clear"], 0),
    (3, "computer", "Files and Permissions",
     "Permissions decide karti hain kaun file ko read, write ya execute kar sakta hai.",
     "Permissions control who can read, write or execute a file.",
     "Safe: apne lab folder me `ls -l` dekho.",
     "Linux permission listing ke liye common command?", ["ls -l", "whoami --all", "netcat -x", "passwd --dump"], 0),
    (4, "computer", "Processes",
     "Running programs ko processes kehte hain; monitoring troubleshooting ka important part hai.",
     "Running programs are processes; monitoring them is important for troubleshooting.",
     "Safe: `python -c \"import time; time.sleep(60)\"` ko apne system par start karke process monitor karo.",
     "Process monitoring ka purpose?", ["Running programs samajhna", "Passwords crack karna", "Firewall todna", "Data steal karna"], 0),
    (5, "computer", "Environment Variables",
     "Secrets ko source code me hard-code karne ke bajay environment variables me rakhna safer hota hai.",
     "Keeping secrets in environment variables is safer than hard-coding them in source code.",
     "Safe: `export DEMO_VALUE=hello` aur Python se `os.getenv('DEMO_VALUE')` read karo.",
     "Secret token ko source code me hard-code karna?", ["Avoid karna chahiye", "Hamesha karna chahiye", "Public karna chahiye", "Logs me daalna chahiye"], 0),
    (6, "computer", "Git Basics",
     "Git code changes ko track karta hai aur safe collaboration me help karta hai.",
     "Git tracks code changes and supports safe collaboration.",
     "Safe: local folder me `git init`, file create, `git status`.",
     "Git ka main use?", ["Version control", "Password cracking", "Network flooding", "Account bypass"], 0),
    (7, "computer", "Backups",
     "Important files ki tested backups ransomware aur accidental deletion ke against useful hain.",
     "Tested backups help against ransomware and accidental deletion.",
     "Safe: apne lab folder ki copy `cp -r lab lab_backup` se banao.",
     "Backup ka benefit?", ["Recovery", "Credential theft", "Bypass", "Phishing"], 0),
    (8, "computer", "Logging",
     "Logs security events ko understand aur investigate karne me help karte hain.",
     "Logs help understand and investigate security events.",
     "Safe: Python logging module se local application log banao.",
     "Logs ka useful role?", ["Investigation", "Password guessing", "Malware delivery", "Unauthorized access"], 0),
    (9, "computer", "Least Privilege",
     "User ko sirf utni permissions milni chahiye jitni uske kaam ke liye required hain.",
     "Users should receive only the permissions required for their work.",
     "Safe lab: do local users/roles imagine karke minimum required permissions ka table banao.",
     "Least privilege kya kehta hai?", ["Minimum required access", "Maximum access", "No logging", "Shared passwords"], 0),
    (10, "computer", "Security Mindset",
     "Har test ke pehle scope, authorization, safety aur rollback plan define karo.",
     "Before testing, define scope, authorization, safety and rollback plans.",
     "Safe lab: apne localhost project ke liye one-page test scope likho.",
     "Authorized testing ka first step?", ["Scope and permission", "Random target choose karna", "Credentials collect karna", "Phishing page banana"], 0),
]
for x in base_lessons:
    add_lesson(*x)


# 11-20: Networking
network_lessons = [
    (11, "network", "IP Addresses", "IP address network par device/interface ko identify karta hai.",
     "An IP address identifies a device or interface on a network.",
     "Safe: apne device par `ip addr` ya `ifconfig` se local interfaces dekho.",
     "IP address ka role?", ["Network addressing", "Password hashing", "HTML rendering", "Code compilation"], 0),
    (12, "network", "MAC Addresses", "MAC address network interface ka link-layer identifier hota hai.",
     "A MAC address is a link-layer identifier for a network interface.",
     "Safe: apne device ke network-interface details dekho.",
     "MAC kis layer se related hai?", ["Link layer", "Application only", "Database layer", "Source code layer"], 0),
    (13, "network", "TCP vs UDP", "TCP reliable connection-oriented transport deta hai; UDP lightweight datagrams use karta hai.",
     "TCP provides reliable connection-oriented transport; UDP uses lightweight datagrams.",
     "Safe: localhost applications me TCP-based HTTP server observe karo.",
     "Reliable ordered delivery ke liye common choice?", ["TCP", "UDP", "DNS", "HTML"], 0),
    (14, "network", "Ports", "Ports network services ko identify karne me help karte hain.",
     "Ports help identify network services.",
     "Safe: apne localhost server ko port 8000 par run karo.",
     "HTTP lab server ke liye humne kaunsa port use kiya?", ["8000", "22", "53", "443"], 0),
    (15, "network", "DNS", "DNS domain names ko IP addresses jaise network information se map karta hai.",
     "DNS maps domain names to network information such as IP addresses.",
     "Safe: `nslookup example.com` public DNS information dekhne ke liye use karo.",
     "DNS primarily kya karta hai?", ["Name resolution", "Password storage", "Code compilation", "Image editing"], 0),
    (16, "network", "HTTP", "HTTP web clients aur servers ke beech requests aur responses ka protocol hai.",
     "HTTP is a protocol for requests and responses between web clients and servers.",
     "Safe: localhost server ko browser se open karo aur developer tools me request dekho.",
     "HTTP me client kya bhejta hai?", ["Request", "Binary password list", "Kernel module", "Compiler"], 0),
    (17, "network", "HTTPS", "HTTPS HTTP ko TLS ke through protect karta hai.",
     "HTTPS protects HTTP using TLS.",
     "Safe: apne browser me HTTPS certificate details inspect karo.",
     "HTTPS ka security layer?", ["TLS", "FTP", "SQL", "CSS"], 0),
    (18, "network", "NAT", "NAT private aur public addressing ke beech translation provide kar sakta hai.",
     "NAT can translate between private and public addressing.",
     "Safe: apne home router ke private IP range ko observe karo.",
     "NAT ka common purpose?", ["Address translation", "Password hashing", "Java compilation", "HTML parsing"], 0),
    (19, "network", "Firewalls", "Firewall traffic ko defined rules ke basis par allow ya block karta hai.",
     "A firewall allows or blocks traffic according to rules.",
     "Safe lab: localhost service ke expected port aur unnecessary exposed ports ki checklist banao.",
     "Firewall ka main function?", ["Traffic control", "Password recovery", "Source compilation", "Image compression"], 0),
    (20, "network", "Network Troubleshooting", "Ping, DNS checks aur local service checks basic troubleshooting tools hain.",
     "Ping, DNS checks and local service checks are basic troubleshooting tools.",
     "Safe: `ping 127.0.0.1` aur apne localhost HTTP server ko test karo.",
     "127.0.0.1 kya represent karta hai?", ["Localhost", "Broadcast internet", "DNS root", "A remote server"], 0),
]
for x in network_lessons:
    add_lesson(*x)


# 21-30: Web Security
web_lessons = [
    (21, "web", "HTML Basics", "HTML webpage ka structure define karta hai.",
     "HTML defines webpage structure.", "Safe lab: ek local HTML file banao aur browser me kholo.",
     "HTML ka purpose?", ["Web structure", "Password cracking", "Encryption", "Routing"], 0),
    (22, "web", "JavaScript Basics", "JavaScript browser me interactive behavior add karta hai.",
     "JavaScript adds interactive behavior in browsers.", "Safe lab: local page par button click counter banao.",
     "Browser interaction ke liye common language?", ["JavaScript", "SQL", "Bash only", "DNS"], 0),
    (23, "web", "Cookies", "Cookies browser aur web application ke beech state maintain karne me use hote hain.",
     "Cookies can maintain state between a browser and web application.",
     "Safe: apni localhost app ki cookies browser developer tools me inspect karo.",
     "Cookie ka common role?", ["State/session data", "CPU control", "Compiler settings", "Wi-Fi password cracking"], 0),
    (24, "web", "Sessions", "Session server-side user state ko represent kar sakti hai.",
     "A session can represent server-side user state.",
     "Safe lab: localhost app me random session ID generate karo; real credentials use mat karo.",
     "Session ka purpose?", ["Maintain application state", "Compile C++", "Resolve DNS", "Format disk"], 0),
    (25, "web", "Input Validation", "User input ko expected type, length aur format ke against validate karo.",
     "Validate user input against expected type, length and format.",
     "Safe lab: localhost form me email/number validation implement karo.",
     "Validation ka goal?", ["Unexpected input reduce karna", "Secrets publish karna", "Access bypass", "Traffic flood"], 0),
    (26, "web", "XSS Concept", "XSS me untrusted input browser context me execute ho sakta hai; defense me output encoding important hai.",
     "XSS can occur when untrusted input executes in a browser context; output encoding is important.",
     "Safe lab: intentionally vulnerable localhost page banao aur phir escaping se fix compare karo.",
     "XSS defense ka common measure?", ["Output encoding", "Shared passwords", "Disable logging", "Random redirects"], 0),
    (27, "web", "SQL Injection Concept", "SQL injection unsafe query construction ki wajah se database query ka meaning change kar sakta hai.",
     "SQL injection can change query meaning when queries are built unsafely.",
     "Safe lab: localhost SQLite app me parameterized queries implement karo.",
     "Best basic defense?", ["Parameterized queries", "String concatenation", "Hard-coded passwords", "No validation"], 0),
    (28, "web", "CSRF", "CSRF victim ke authenticated browser se unwanted state-changing action trigger karne ka risk hai.",
     "CSRF is the risk of unwanted state-changing actions through an authenticated browser.",
     "Safe lab: localhost app me CSRF token concept implement karo.",
     "Common defense?", ["CSRF token", "Disable HTTPS", "Expose cookies", "Shared credentials"], 0),
    (29, "web", "Security Headers", "Security headers browser behavior ko safer banane me help karte hain.",
     "Security headers can make browser behavior safer.",
     "Safe lab: localhost response me Content-Security-Policy aur X-Content-Type-Options jaise headers add karo.",
     "CSP kis area me help karta hai?", ["Browser content control", "Password hashing", "C++ compilation", "DNS routing"], 0),
    (30, "web", "Access Control", "Server ko har protected action par authorization check karna chahiye.",
     "Servers should enforce authorization checks for protected actions.",
     "Safe lab: localhost app me user/admin roles banao aur har endpoint par authorization check lagao.",
     "Authorization kya decide karta hai?", ["Who may perform an action", "How HTML is styled", "DNS address", "CPU speed"], 0),
]
for x in web_lessons:
    add_lesson(*x)


# 31-40: Cryptography
crypto_lessons = [
    (31, "crypto", "Encoding vs Encryption", "Encoding format change hai; encryption confidentiality ke liye key use karta hai.",
     "Encoding changes representation; encryption uses keys for confidentiality.",
     "Safe: Base64 encode/decode ko Python me try karo; ise encryption mat samjho.",
     "Base64 kya hai?", ["Encoding", "Strong encryption", "Hashing", "Firewall"], 0),
    (32, "crypto", "Hashing", "Hash function input ko fixed-size digest me map karta hai.",
     "A hash function maps input to a fixed-size digest.",
     "Safe: Python hashlib se apne test text ka SHA-256 digest nikalo.",
     "Hash ka common use?", ["Integrity", "Reversible storage", "HTML styling", "Routing"], 0),
    (33, "crypto", "Salting Passwords", "Unique salt password hashes ko precomputed lookup attacks ke against stronger banata hai.",
     "Unique salts strengthen password hashing against precomputed lookup attacks.",
     "Safe lab: random salt generate karke password hashing design compare karo.",
     "Salt ka benefit?", ["Unique hash inputs", "Password sharing", "DNS lookup", "Code execution"], 0),
    (34, "crypto", "Symmetric Encryption", "Same secret key encryption aur decryption dono me use hoti hai.",
     "The same secret key is used for encryption and decryption.",
     "Safe: trusted crypto library ke documented example ko localhost test data par use karo.",
     "Symmetric crypto me key model?", ["Same secret key", "No key", "Only public key", "DNS key"], 0),
    (35, "crypto", "Asymmetric Encryption", "Public/private key pair encryption, signatures aur key exchange scenarios me use hota hai.",
     "Public/private key pairs are used for encryption, signatures and key exchange scenarios.",
     "Safe: toy key-pair concept ko study karo; production crypto khud implement mat karo.",
     "Asymmetric cryptography uses?", ["Key pair", "Single shared password only", "No keys", "HTML tags"], 0),
    (36, "crypto", "Digital Signatures", "Digital signatures authenticity aur integrity verify karne me help karti hain.",
     "Digital signatures help verify authenticity and integrity.",
     "Safe: documented signing/verification example ko test message par run karo.",
     "Signature primarily kya prove karne me help karti hai?", ["Authenticity/integrity", "CPU speed", "DNS route", "HTML layout"], 0),
    (37, "crypto", "TLS Certificates", "Certificates public keys ko identities se bind karne me help karte hain.",
     "Certificates help bind public keys to identities.",
     "Safe: browser me kisi HTTPS site's certificate details inspect karo.",
     "Certificate ka role?", ["Bind identity and public key", "Store passwords in plaintext", "Compile Java"], 0),
    (38, "crypto", "Randomness", "Security-sensitive tokens ke liye cryptographically secure randomness important hai.",
     "Cryptographically secure randomness is important for security-sensitive tokens.",
     "Safe: Python `secrets` module se random test token generate karo.",
     "Security tokens ke liye preferred Python module?", ["secrets", "random only", "math", "os.path"], 0),
    (39, "crypto", "Key Management", "Strong algorithm ke saath secure key storage aur rotation bhi important hai.",
     "Secure key storage and rotation matter alongside strong algorithms.",
     "Safe lab: environment variable aur restricted config file ke pros/cons compare karo.",
     "Crypto security me keys ka kya importance hai?", ["Critical", "Unimportant", "Only UI related", "Only DNS related"], 0),
    (40, "crypto", "Password Storage", "Passwords ko plaintext me nahi rakhna chahiye; dedicated password hashing approach use karo.",
     "Passwords should not be stored in plaintext; use a dedicated password-hashing approach.",
     "Safe lab: Argon2/bcrypt jaise maintained password-hashing libraries ke documented examples study karo.",
     "Password storage ka safer approach?", ["Dedicated password hashing", "Plaintext", "Reversible Base64", "Logs"], 0),
]
for x in crypto_lessons:
    add_lesson(*x)


# 41-50: Defensive security
defense_lessons = [
    (41, "defense", "Threat Modeling", "Threat modeling assets, attackers, entry points aur mitigations ko systematically identify karta hai.",
     "Threat modeling systematically identifies assets, threats, entry points and mitigations.",
     "Safe lab: apni localhost app ke assets aur threats ka simple diagram banao.",
     "Threat modeling ka goal?", ["Risk identify/reduce karna", "Credentials steal karna", "Spam", "Code obfuscation"], 0),
    (42, "defense", "Risk", "Risk ko likelihood aur impact ke combination ke roop me assess kiya ja sakta hai.",
     "Risk can be assessed using likelihood and impact.",
     "Safe lab: 5 localhost risks ko Low/Medium/High rate karo.",
     "Risk assessment me kya dekha jata hai?", ["Likelihood and impact", "Font size", "Screen brightness", "CPU brand"], 0),
    (43, "defense", "Rate Limiting", "Rate limiting repeated requests ko control karta hai aur abuse reduce karta hai.",
     "Rate limiting controls repeated requests and reduces abuse.",
     "Safe lab: is bot ke rate limiter ko study karo.",
     "Rate limiting ka purpose?", ["Abuse control", "Password recovery", "Encryption", "HTML rendering"], 0),
    (44, "defense", "Secure Authentication", "Authentication me strong password hashing, MFA aur session protections important hain.",
     "Strong password hashing, MFA and session protections are important in authentication.",
     "Safe lab: localhost login design me password hashing aur session expiry plan karo.",
     "Authentication kya verify karta hai?", ["Identity", "Authorization only", "CSS", "DNS"], 0),
    (45, "defense", "Authorization", "Authentication ke baad authorization decide karta hai user kya kar sakta hai.",
     "Authorization decides what an authenticated user may do.",
     "Safe lab: localhost app me user/admin permission matrix banao.",
     "Authorization decides?", ["Permissions", "Identity", "DNS", "Hash algorithm"], 0),
    (46, "defense", "Incident Response", "Incident response preparation, detection, containment, eradication, recovery aur lessons learned cover karta hai.",
     "Incident response covers preparation, detection, containment, eradication, recovery and lessons learned.",
     "Safe lab: fake localhost incident ka response checklist banao.",
     "Recovery kis phase ka part hai?", ["Incident response", "HTML", "Compilation", "DNS"], 0),
    (47, "defense", "Security Monitoring", "Monitoring suspicious behavior ko early detect karne me help karta hai.",
     "Monitoring helps detect suspicious behavior early.",
     "Safe lab: localhost app ke request counts aur errors log karo.",
     "Monitoring ka benefit?", ["Early detection", "Password theft", "Bypass", "Source deletion"], 0),
    (48, "defense", "Patch Management", "Known vulnerabilities ko reduce karne ke liye software updates important hain.",
     "Software updates help reduce known vulnerabilities.",
     "Safe lab: installed packages ki update checklist maintain karo.",
     "Patch management ka goal?", ["Known vulnerabilities reduce karna", "Passwords expose karna", "Disable security"], 0),
    (49, "defense", "Secure Configuration", "Unused services, default credentials aur unnecessary exposure ko remove karna hardening ka part hai.",
     "Removing unused services, default credentials and unnecessary exposure is part of hardening.",
     "Safe lab: apne localhost app ki hardening checklist banao.",
     "Hardening ka purpose?", ["Attack surface reduce karna", "Attack surface increase karna", "Secrets publish karna", "Logging disable karna"], 0),
    (50, "defense", "Security Checklist", "Checklist repeatable security reviews ko reliable banati hai.",
     "Checklists make repeatable security reviews more reliable.",
     "Safe lab: authentication, input validation, logging aur backups ki checklist banao.",
     "Checklist ka benefit?", ["Repeatability", "Credential theft", "Bypass", "Spam"], 0),
]
for x in defense_lessons:
    add_lesson(*x)


# 51-60: Forensics
forensics_lessons = [
    (51, "forensics", "Digital Evidence", "Evidence ko preserve karna investigation ki integrity ke liye important hai.",
     "Preserving evidence is important for investigation integrity.",
     "Safe lab: apne test file ki SHA-256 hash record karo.",
     "Evidence preservation ka goal?", ["Integrity maintain karna", "Evidence alter karna", "Secrets publish karna", "Logs delete karna"], 0),
    (52, "forensics", "File Hashing", "Hash file changes detect karne me help karta hai.",
     "Hashes help detect file changes.",
     "Safe: Python hashlib se local test file hash karo.",
     "Hash comparison kya detect kar sakta hai?", ["Changes", "Screen size", "CPU model", "DNS zone"], 0),
    (53, "forensics", "Metadata", "Metadata file ke creation/modification aur format related information de sakta hai.",
     "Metadata can contain information about file creation/modification and format.",
     "Safe lab: apni khud ki image/document metadata inspect karo.",
     "Metadata kya ho sakta hai?", ["File-related information", "Only passwords", "Only DNS", "Only code"], 0),
    (54, "forensics", "Timelines", "Event timeline incident investigation me sequence samajhne me help karti hai.",
     "Event timelines help understand the sequence during an investigation.",
     "Safe lab: apne lab logs se timestamp timeline banao.",
     "Timeline ka purpose?", ["Event sequence", "Password generation", "HTML styling", "Compilation"], 0),
    (55, "forensics", "Indicators of Compromise", "IOCs suspicious files, domains, hashes ya behaviors jaise indicators ho sakte hain.",
     "IOCs can include suspicious files, domains, hashes or behaviors.",
     "Safe lab: fake IOC list bana kar detection rules practice karo.",
     "IOC ka meaning?", ["Indicator of compromise", "Internet-only command", "Input output compiler", "Internal OS code"], 0),
    (56, "forensics", "Log Analysis", "Logs ko timestamp, source, action aur result ke basis par analyze kiya ja sakta hai.",
     "Logs can be analyzed by timestamp, source, action and result.",
     "Safe lab: is bot ke SQLite logs/quiz data ko inspect karo.",
     "Log analysis kisliye?", ["Investigate events", "Compile C++", "Design CSS"], 0),
    (57, "forensics", "Chain of Custody", "Evidence kisne, kab aur kaise handle kiya iska record chain of custody hota hai.",
     "A chain of custody records who handled evidence, when and how.",
     "Safe lab: fictional evidence handoff form banao.",
     "Chain of custody?", ["Evidence handling record", "Password list", "Firewall rule"], 0),
    (58, "forensics", "IOC Validation", "Ek indicator ko blindly malicious maan ne ke bajay context aur multiple signals se validate karo.",
     "Validate indicators using context and multiple signals instead of blindly treating them as malicious.",
     "Safe lab: fake logs me false positives identify karo.",
     "False positive kya hai?", ["Benign event flagged as malicious", "Confirmed attack", "Encryption key"], 0),
    (59, "forensics", "Incident Notes", "Clear notes investigation ko reproducible aur reviewable banati hain.",
     "Clear notes make investigations reproducible and reviewable.",
     "Safe lab: fictional incident ka timeline + findings document karo.",
     "Good investigation notes?", ["Clear and timestamped", "Hidden and incomplete", "Random", "Deleted"], 0),
    (60, "forensics", "Forensics Ethics", "Evidence ko alter ya misuse nahi karna chahiye; authorization aur privacy ka respect zaroori hai.",
     "Do not alter or misuse evidence; authorization and privacy matter.",
     "Safe lab: fictional case par evidence-handling rules likho.",
     "Forensics me authorization?", ["Required", "Never needed", "Optional for strangers", "Only after publishing"], 0),
]
for x in forensics_lessons:
    add_lesson(*x)


# 61-70: Programming
programming_lessons = [
    (61, "programming", "Programming Fundamentals", "Variables, conditions, loops aur functions programming ke core concepts hain.",
     "Variables, conditions, loops and functions are core programming concepts.",
     "Safe lab: teen numbers ka sum program banao.",
     "Loop ka purpose?", ["Repeat work", "Encrypt everything", "Resolve DNS"], 0),
    (62, "python", "Python Basics", "Python readable syntax aur large ecosystem ki wajah se automation ke liye useful hai.",
     "Python has readable syntax and a large ecosystem useful for automation.",
     "Safe lab: `print('Hello EthicalX')`.",
     "Python file extension?", [".py", ".java", ".cpp", ".html"], 0),
    (63, "python", "Python Functions", "Functions reusable logic ko organize karti hain.",
     "Functions organize reusable logic.",
     "Safe lab: `def add(a,b): return a+b`.",
     "Reusable logic ke liye?", ["Function", "Comment only", "Port", "Cookie"], 0),
    (64, "python", "Python Exceptions", "try/except se expected runtime errors ko safely handle kiya ja sakta hai.",
     "try/except can safely handle expected runtime errors.",
     "Safe lab: invalid integer input ko handle karo.",
     "Python exception handling?", ["try/except", "if-only", "DNS", "HTML"], 0),
    (65, "python", "Python SQLite", "SQLite small local applications ke liye embedded database hai.",
     "SQLite is an embedded database useful for small local applications.",
     "Safe lab: `sqlite3.connect('lab.db')` se local database banao.",
     "SQLite kya hai?", ["Embedded database", "Compiler", "Firewall"], 0),
    (66, "java", "Java Basics", "Java strongly typed, object-oriented language hai jo JVM ecosystem me widely used hai.",
     "Java is a strongly typed, object-oriented language widely used in the JVM ecosystem.",
     "Safe lab: `class Main { public static void main(String[] a){ System.out.println(\"Hello\"); } }` compile/run karo.",
     "Java program ka common entry point?", ["main", "start_html", "dns", "shell"], 0),
    (67, "java", "Java Exceptions", "Java me exceptions ko try/catch/finally aur appropriate propagation se handle kiya jata hai.",
     "Java exceptions are handled using try/catch/finally and appropriate propagation.",
     "Safe lab: number parsing error handle karo.",
     "Java exception handling?", ["try/catch", "HTML/CSS", "DNS"], 0),
    (68, "cpp", "C++ Basics", "C++ compiled language hai jisme performance aur low-level control important strengths hain.",
     "C++ is compiled and offers performance and low-level control.",
     "Safe lab: `std::cout << \"Hello\";` compile karo.",
     "C++ output stream?", ["std::cout", "print_html", "dns_send"], 0),
    (69, "cpp", "Memory Safety Concepts", "Pointers aur manual memory management powerful hain, lekin bugs ka risk bhi badha sakte hain.",
     "Pointers and manual memory management are powerful but can increase bug risk.",
     "Safe lab: sanitizer-enabled local build me simple C++ program test karo.",
     "Memory bugs ko detect karne ka useful tool?", ["Sanitizers", "DNS", "CSS"], 0),
    (70, "programming", "Secure Coding", "Input validation, safe APIs, least privilege aur clear error handling secure coding ke basics hain.",
     "Input validation, safe APIs, least privilege and clear error handling are secure-coding basics.",
     "Safe lab: kisi local form/API ke inputs ke validation rules likho.",
     "Secure coding ka focus?", ["Reduce vulnerabilities", "Hide malware", "Steal credentials"], 0),
]
for x in programming_lessons:
    add_lesson(*x)


# 71-80: Python/Java/C++ applied security
applied_lessons = [
    (71, "python", "Python HTTP Local Server", "Python ka built-in HTTP server local files ko test environment me serve kar sakta hai.",
     "Python's built-in HTTP server can serve local files in a test environment.",
     "Run: `python -m http.server 8000 --bind 127.0.0.1`, then visit http://127.0.0.1:8000.",
     "Local-only bind address?", ["127.0.0.1", "0.0.0.0 always", "8.8.8.8", "255.255.255.255"], 0),
    (72, "python", "Python URL Parsing", "urllib.parse se URL ko safely components me parse kiya ja sakta hai.",
     "urllib.parse can safely parse URLs into components.",
     "Safe lab: apne test URL ko `urlsplit()` se parse karo.",
     "URL parsing ke liye module?", ["urllib.parse", "sqlite3 only", "logging only"], 0),
    (73, "python", "Python JSON APIs", "JSON web APIs me structured data exchange ka common format hai.",
     "JSON is a common structured data format for web APIs.",
     "Safe lab: local JSON object ko `json.dumps`/`json.loads` se test karo.",
     "Python JSON module?", ["json", "hashlib only", "socket only"], 0),
    (74, "python", "Python Secure Tokens", "Security-sensitive random tokens ke liye `secrets` module use karo.",
     "Use Python's `secrets` module for security-sensitive random tokens.",
     "Safe lab: `secrets.token_urlsafe(16)` ka output dekho.",
     "Secure random tokens?", ["secrets", "random.randint only", "math"], 0),
    (75, "java", "Java Collections", "Collections structured data ko safely organize aur process karne me help karti hain.",
     "Collections help organize and process structured data.",
     "Safe lab: ArrayList me test values add/remove karo.",
     "Java dynamic list?", ["ArrayList", "DNSList", "PortList"], 0),
    (76, "java", "Java Secure Coding", "Java input validation, safe serialization choices aur least privilege par focus karo.",
     "Java secure coding should focus on validation, safe serialization choices and least privilege.",
     "Safe lab: untrusted text ko validate karke process karo.",
     "Untrusted input?", ["Validate", "Trust blindly", "Publish"], 0),
    (77, "cpp", "C++ RAII", "RAII resource lifetime ko object lifetime se tie karta hai aur resource leaks reduce kar sakta hai.",
     "RAII ties resource lifetime to object lifetime and can reduce leaks.",
     "Safe lab: local file stream ko scope ke andar use karo.",
     "RAII benefit?", ["Resource lifetime management", "DNS resolution", "Password cracking"], 0),
    (78, "cpp", "C++ Input Validation", "External input ko parse aur validate karke unexpected states reduce karo.",
     "Parse and validate external input to reduce unexpected states.",
     "Safe lab: integer range validation implement karo.",
     "Validation kyun?", ["Unexpected input reduce karne ke liye", "Secrets leak karne ke liye", "Bypass ke liye"], 0),
    (79, "programming", "Unit Testing", "Tests expected behavior ko automatically verify karte hain.",
     "Tests automatically verify expected behavior.",
     "Safe lab: calculator function ke positive/negative test cases likho.",
     "Unit test kya verify karta hai?", ["Expected behavior", "Passwords", "Network routes"], 0),
    (80, "programming", "Dependency Security", "Third-party dependencies ko update, pin aur review karna important hai.",
     "Updating, pinning and reviewing third-party dependencies is important.",
     "Safe lab: apne Python project's dependency list review karo.",
     "Dependency review kyun?", ["Supply-chain risk reduce karna", "DNS speed", "Screen brightness"], 0),
]
for x in applied_lessons:
    add_lesson(*x)


# 81-90: Professional security
professional_lessons = [
    (81, "professional", "Scope and Authorization", "Security testing sirf explicitly authorized scope me karo.",
     "Perform security testing only within explicitly authorized scope.",
     "Safe lab: localhost-only scope document karo.",
     "Testing scope?", ["Authorized boundaries", "Anything online", "Random targets"], 0),
    (82, "professional", "Vulnerability Reports", "Good report me title, impact, reproduction in authorized lab, evidence aur remediation hota hai.",
     "A good report includes title, impact, authorized reproduction, evidence and remediation.",
     "Safe lab: localhost bug ka mock report banao.",
     "Report me remediation kyun?", ["Fix guide dene ke liye", "Attack expand karne ke liye"], 0),
    (83, "professional", "CVSS Concept", "CVSS vulnerability severity communicate karne ka standardized framework hai.",
     "CVSS is a standardized framework for communicating vulnerability severity.",
     "Safe lab: fictional vulnerability ke impact factors discuss karo.",
     "CVSS kisliye?", ["Severity communication", "Code compilation"], 0),
    (84, "professional", "Responsible Disclosure", "Vulnerability ko affected owner ko responsibly report karna best practice hai.",
     "Responsible disclosure means reporting vulnerabilities to the affected owner appropriately.",
     "Safe lab: fictional vendor report template banao.",
     "Disclosure ka goal?", ["Safe remediation", "Publicly expose secrets"], 0),
    (85, "professional", "Bug Bounty Ethics", "Program rules, scope aur rate limits follow karna mandatory practice hai.",
     "Follow program rules, scope and rate limits.",
     "Safe lab: imaginary bug-bounty scope document padho aur allowed/disallowed actions mark karo.",
     "Bug bounty me kya follow karein?", ["Program scope", "Anything you want"], 0),
    (86, "professional", "CTF Methodology", "CTFs intentionally vulnerable environments me problem solving sikhate hain.",
     "CTFs teach problem solving in intentionally vulnerable environments.",
     "Safe lab: apna local puzzle/flag file banao.",
     "CTF ka safe environment?", ["Authorized challenge lab", "Random website"], 0),
    (87, "professional", "Security Review", "Design, code, configuration aur deployment ko review karna layered security deta hai.",
     "Reviewing design, code, configuration and deployment provides layered security.",
     "Safe lab: localhost app ka four-layer review karo.",
     "Layered security?", ["Multiple controls", "One password only"], 0),
    (88, "professional", "Secure SDLC", "Security requirements ko design se deployment tak integrate karo.",
     "Integrate security requirements from design through deployment.",
     "Safe lab: small app ke lifecycle me security checkpoints add karo.",
     "Security kab add karni chahiye?", ["Throughout lifecycle", "Only after incident"], 0),
    (89, "professional", "Privacy by Design", "Collect minimum data, protect it and define retention.",
     "Collect minimal data, protect it and define retention.",
     "Safe lab: bot ke database fields ko minimize karne ki checklist banao.",
     "Privacy principle?", ["Data minimization", "Collect everything"], 0),
    (90, "professional", "Security Culture", "Security sirf tools nahi; processes, people aur habits bhi important hain.",
     "Security is not just tools; processes, people and habits matter too.",
     "Safe lab: apne project ke top five security habits likho.",
     "Security culture includes?", ["People + process + technology", "Tools only"], 0),
]
for x in professional_lessons:
    add_lesson(*x)


# 91-100: Advanced safe labs
advanced_lessons = [
    (91, "web", "Local Flask Security Lab", "Flask se localhost-only educational web app bana kar validation aur sessions practice kar sakte ho.",
     "Build a localhost-only educational Flask app to practice validation and sessions.",
     "Install Flask, bind only to 127.0.0.1, and use fake test data. Do not expose the lab publicly.",
     "Local lab ka safer bind?", ["127.0.0.1", "Public interface"], 0),
    (92, "network", "Local Service Mapping", "Apne hi localhost services ko document karna defensive asset inventory practice hai.",
     "Documenting your own localhost services is defensive asset-inventory practice.",
     "Safe lab: apne application ke ports/services ki table banao.",
     "Asset inventory ka purpose?", ["Know what you own/expose", "Attack strangers"], 0),
    (93, "defense", "Local Rate-Limit Lab", "Local API par request counter laga kar rate limiting behavior observe karo.",
     "Add a request counter to a local API and observe rate limiting behavior.",
     "Safe lab: 10 requests per minute ki artificial limit implement karo.",
     "Rate limit kis cheez ko control karta hai?", ["Request frequency", "CPU temperature"], 0),
    (94, "web", "Secure Headers Lab", "Local server responses me defensive headers add aur inspect karo.",
     "Add and inspect defensive headers in local server responses.",
     "Safe lab: CSP, X-Content-Type-Options aur Referrer-Policy test karo.",
     "Security headers kahan apply hote hain?", ["HTTP responses", "C++ compiler"], 0),
    (95, "crypto", "Password Hashing Lab", "Fake passwords ke saath password-hashing workflow practice karo.",
     "Practice password-hashing workflows with fake passwords.",
     "Safe lab: maintained Argon2/bcrypt library ke documented local example ko use karo.",
     "Password hashing ka goal?", ["Safe password verification", "Reversible plaintext storage"], 0),
    (96, "forensics", "Local Log Investigation", "Apne generated application logs se suspicious patterns identify karo.",
     "Identify suspicious patterns in logs generated by your own application.",
     "Safe lab: fake login events generate karo aur timestamps/IP placeholders analyze karo.",
     "Log investigation ka focus?", ["Events and patterns", "Random guessing"], 0),
    (97, "programming", "Secure API Lab", "Local API me schema validation, authentication simulation, authorization aur error handling practice karo.",
     "Practice schema validation, simulated authentication, authorization and error handling in a local API.",
     "Safe lab: fake users aur fake tokens only; API ko localhost par bind rakho.",
     "API lab me data?", ["Fake test data", "Real credentials"], 0),
    (98, "defense", "Backup and Restore Lab", "Backup banana hi nahi, restore test karna bhi important hai.",
     "Testing restoration is as important as creating backups.",
     "Safe lab: local SQLite database ka backup banao aur separate file me restore test karo.",
     "Backup strategy me kya test karein?", ["Restore", "Only creation"], 0),
    (99, "professional", "Final Security Audit", "Asset, authentication, authorization, validation, logging, dependencies aur backups ko review karo.",
     "Review assets, authentication, authorization, validation, logging, dependencies and backups.",
     "Safe lab: apne localhost project ka final checklist audit karo.",
     "Final audit ka objective?", ["Risk reduce karna", "Attack strangers"], 0),
    (100, "professional", "Capstone: Secure Local App", "Ab ek localhost-only application banao jo secure coding ke learned concepts combine kare.",
     "Build a localhost-only application combining the secure-coding concepts you learned.",
     "Capstone: Python/Java/C++ component + SQLite + validation + logging + rate limiting + tests + documentation.",
     "Capstone kis environment me?", ["Authorized local lab", "Random public target"], 0),
]
for x in advanced_lessons:
    add_lesson(*x)


# ---------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------
def main_menu():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📚 Learn", callback_data="menu:learn"),
                InlineKeyboardButton("📝 Quiz", callback_data="menu:quiz"),
            ],
            [
                InlineKeyboardButton("🧪 Safe Labs", callback_data="menu:labs"),
                InlineKeyboardButton("📊 Progress", callback_data="menu:progress"),
            ],
            [
                InlineKeyboardButton("💻 Languages", callback_data="menu:languages"),
                InlineKeyboardButton("📖 Categories", callback_data="menu:categories"),
            ],
            [
                InlineKeyboardButton("🔎 Search", callback_data="menu:search"),
                InlineKeyboardButton("ℹ️ Help", callback_data="menu:help"),
            ],
        ]
    )


def lesson_keyboard(n):
    buttons = []
    if n > 1:
        buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"lesson:{n-1}"))
    if n < 100:
        buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"lesson:{n+1}"))
    rows = [buttons] if buttons else []
    rows.append([InlineKeyboardButton("📝 Quiz", callback_data=f"quiz:{n}")])
    rows.append([InlineKeyboardButton("🏠 Menu", callback_data="menu:home")])
    return InlineKeyboardMarkup(rows)


def render_lesson(n):
    lesson = LESSONS[n]
    return (
        f"<b>📚 Lesson {n}/100 — {escape(lesson['title'])}</b>\n"
        f"<b>Category:</b> {escape(CATEGORIES.get(lesson['category'], lesson['category']))}\n\n"
        f"<b>🇮🇳 Hindi:</b>\n{escape(lesson['hi'])}\n\n"
        f"<b>🇬🇧 English:</b>\n{escape(lesson['en'])}\n\n"
        f"<b>🧪 Safe Local Lab:</b>\n<code>{escape(lesson['lab'])}</code>\n\n"
        "⚠️ Sirf apne device/localhost ya explicitly authorized lab par test karo."
    )


async def send_lesson(update, n):
    text = render_lesson(n)
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, parse_mode=ParseMode.HTML, reply_markup=lesson_keyboard(n)
        )
    else:
        await update.message.reply_text(
            text, parse_mode=ParseMode.HTML, reply_markup=lesson_keyboard(n)
        )


# ---------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update.effective_user.id):
        await update.message.reply_text("⏳ Thoda wait karo; rate limit active hai.")
        return
    upsert_user(update.effective_user)
    await update.message.reply_text(
        f"<b>🛡️ {BOT_NAME} v{VERSION}</b>\n\n"
        "Cyber Security Learning + Safe Local Lab.\n\n"
        "Beginner se Level 100 tak Hindi + English me learning.\n"
        "Python • Java • C++ • Networking • Web Security • Crypto • Defense",
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu(),
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    upsert_user(update.effective_user)
    await update.message.reply_text(
        "<b>📖 Commands</b>\n\n"
        "/start — Main menu\n"
        "/learn [1-100] — Lesson\n"
        "/quiz [1-100] — Quiz\n"
        "/progress — Progress\n"
        "/categories — Categories\n"
        "/search word — Search lessons\n"
        "/lab — Safe localhost labs\n"
        "/languages — Python, Java, C++\n"
        "/glossary — Security glossary\n"
        "/help — Help\n\n"
        "Testing only on your own device, localhost or authorized lab.",
        parse_mode=ParseMode.HTML,
    )


async def learn_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    upsert_user(update.effective_user)
    n = get_progress(update.effective_user.id)[0]
    if context.args:
        try:
            n = int(context.args[0])
        except ValueError:
            await update.message.reply_text("Use: /learn 1")
            return
    if n not in LESSONS:
        await update.message.reply_text("Lesson 1 se 100 ke beech choose karo.")
        return
    set_progress(update.effective_user.id, n)
    await send_lesson(update, n)


async def quiz_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    upsert_user(update.effective_user)
    n = get_progress(update.effective_user.id)[0]
    if context.args:
        try:
            n = int(context.args[0])
        except ValueError:
            await update.message.reply_text("Use: /quiz 1")
            return
    await send_quiz(update, n)


async def progress_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    upsert_user(update.effective_user)
    lesson, score = get_progress(update.effective_user.id)
    await update.message.reply_text(
        f"<b>📊 Your Progress</b>\n\n"
        f"Current lesson: <b>{lesson}/100</b>\n"
        f"Quiz score: <b>{score}</b>\n\n"
        f"Next: /learn {lesson}",
        parse_mode=ParseMode.HTML,
    )


async def categories_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    upsert_user(update.effective_user)
    lines = ["<b>📖 Categories</b>\n"]
    for key, name in CATEGORIES.items():
        count = sum(1 for x in LESSONS.values() if x["category"] == key)
        lines.append(f"• {escape(name)} — {count} lessons")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def languages_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "<b>💻 Programming Tracks</b>\n\n"
        "🐍 Python — syntax, functions, files, SQLite, APIs, testing\n"
        "☕ Java — classes, exceptions, collections, secure coding\n"
        "⚙️ C++ — basics, RAII, memory-safety concepts, validation\n\n"
        "Start: /learn 62",
        parse_mode=ParseMode.HTML,
    )


async def lab_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "<b>🧪 Safe Local Labs</b>\n\n"
        "1) Local HTTP server:\n"
        "<code>python -m http.server 8000 --bind 127.0.0.1</code>\n\n"
        "2) Test it:\n"
        "<code>curl http://127.0.0.1:8000/</code>\n\n"
        "3) Python version:\n"
        "<code>python --version</code>\n\n"
        "4) Localhost ping:\n"
        "<code>ping 127.0.0.1</code>\n\n"
        "5) SQLite:\n"
        "<code>python -c \"import sqlite3; print(sqlite3.sqlite_version)\"</code>\n\n"
        "⚠️ Labs ko public internet par expose mat karo jab tak tumhe secure deployment properly na aata ho.",
        parse_mode=ParseMode.HTML,
    )


async def glossary_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "<b>📖 Mini Glossary</b>\n\n"
        "IP — network address\n"
        "Port — service endpoint identifier\n"
        "DNS — name resolution system\n"
        "HTTP — web request/response protocol\n"
        "TLS — transport security layer used by HTTPS\n"
        "Hash — one-way digest function\n"
        "Salt — unique random value used with password hashing\n"
        "Authentication — identity verification\n"
        "Authorization — permission decision\n"
        "XSS — browser-side injection vulnerability class\n"
        "CSRF — unwanted state-changing request risk\n"
        "IOC — indicator of compromise\n"
        "CVSS — vulnerability severity framework",
        parse_mode=ParseMode.HTML,
    )


async def search_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    upsert_user(update.effective_user)
    if not context.args:
        await update.message.reply_text("Use: /search networking")
        return
    q = " ".join(context.args).lower()
    hits = []
    for n, lesson in LESSONS.items():
        blob = " ".join(
            [lesson["title"], lesson["hi"], lesson["en"], lesson["category"]]
        ).lower()
        if q in blob:
            hits.append(n)
    if not hits:
        await update.message.reply_text("Koi matching lesson nahi mila.")
        return
    text = "<b>🔎 Search Results</b>\n\n" + "\n".join(
        f"• Lesson {n}: {escape(LESSONS[n]['title'])}" for n in hits[:20]
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# ---------------------------------------------------------------------
# Quiz
# ---------------------------------------------------------------------
async def send_quiz(update, n):
    if n not in LESSONS:
        if update.callback_query:
            await update.callback_query.answer("Lesson 1-100 choose karo.")
        else:
            await update.message.reply_text("Lesson 1-100 choose karo.")
        return

    lesson = LESSONS[n]
    buttons = [
        [InlineKeyboardButton(option, callback_data=f"answer:{n}:{i}")]
        for i, option in enumerate(lesson["options"])
    ]
    buttons.append([InlineKeyboardButton("🏠 Menu", callback_data="menu:home")])
    text = (
        f"<b>📝 Quiz — Lesson {n}</b>\n\n"
        f"{escape(lesson['quiz'])}"
    )
    markup = InlineKeyboardMarkup(buttons)

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, parse_mode=ParseMode.HTML, reply_markup=markup
        )
    else:
        await update.message.reply_text(
            text, parse_mode=ParseMode.HTML, reply_markup=markup
        )


# ---------------------------------------------------------------------
# Callback buttons
# ---------------------------------------------------------------------
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    upsert_user(update.effective_user)

    data = query.data

    if data == "menu:home":
        await query.edit_message_text(
            f"<b>🛡️ {BOT_NAME} v{VERSION}</b>\n\nChoose an option:",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu(),
        )
        return

    if data == "menu:learn":
        lesson = get_progress(update.effective_user.id)[0]
        await send_lesson(update, lesson)
        return

    if data == "menu:quiz":
        lesson = get_progress(update.effective_user.id)[0]
        await send_quiz(update, lesson)
        return

    if data == "menu:progress":
        lesson, score = get_progress(update.effective_user.id)
        await query.edit_message_text(
            f"<b>📊 Progress</b>\n\nLesson: {lesson}/100\nScore: {score}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🏠 Menu", callback_data="menu:home")]]
            ),
        )
        return

    if data == "menu:categories":
        lines = ["<b>📖 Categories</b>\n"]
        for key, name in CATEGORIES.items():
            count = sum(1 for x in LESSONS.values() if x["category"] == key)
            lines.append(f"• {escape(name)} — {count}")
        await query.edit_message_text(
            "\n".join(lines),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🏠 Menu", callback_data="menu:home")]]
            ),
        )
        return

    if data == "menu:languages":
        await query.edit_message_text(
            "<b>💻 Languages</b>\n\n"
            "🐍 Python — /learn 62\n"
            "☕ Java — /learn 66\n"
            "⚙️ C++ — /learn 68\n\n"
            "Advanced applied lessons: 71-80",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🏠 Menu", callback_data="menu:home")]]
            ),
        )
        return

    if data == "menu:labs":
        await query.edit_message_text(
            "<b>🧪 Safe Labs</b>\n\n"
            "<code>python -m http.server 8000 --bind 127.0.0.1</code>\n"
            "<code>curl http://127.0.0.1:8000/</code>\n"
            "<code>ping 127.0.0.1</code>\n\n"
            "Only localhost/self-device/authorized labs.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🏠 Menu", callback_data="menu:home")]]
            ),
        )
        return

    if data == "menu:search":
        await query.edit_message_text(
            "🔎 Search ke liye message me use karo:\n\n"
            "<code>/search networking</code>\n"
            "<code>/search python</code>\n"
            "<code>/search encryption</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🏠 Menu", callback_data="menu:home")]]
            ),
        )
        return

    if data == "menu:help":
        await help_cmd(update, context)
        return

    if data.startswith("lesson:"):
        n = int(data.split(":")[1])
        set_progress(update.effective_user.id, n)
        await send_lesson(update, n)
        return

    if data.startswith("quiz:"):
        n = int(data.split(":")[1])
        await send_quiz(update, n)
        return

    if data.startswith("answer:"):
        _, n_text, answer_text = data.split(":")
        n = int(n_text)
        answer = int(answer_text)
        lesson = LESSONS[n]
        correct = answer == lesson["answer"]
        add_score(update.effective_user.id, n, int(correct))

        if correct:
            msg = "✅ Correct! / Sahi jawab."
        else:
            right = lesson["options"][lesson["answer"]]
            msg = f"❌ Incorrect. Correct answer: <b>{escape(right)}</b>"

        next_n = min(100, n + 1)
        set_progress(update.effective_user.id, next_n)
        await query.edit_message_text(
            f"<b>Lesson {n} Quiz</b>\n\n{msg}\n\n"
            f"Next lesson: {next_n}/100",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("📚 Next Lesson", callback_data=f"lesson:{next_n}")],
                    [InlineKeyboardButton("🏠 Menu", callback_data="menu:home")],
                ]
            ),
        )
        return


# ---------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------
async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Admin only.")
        return
    with db() as conn:
        users = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
        quizzes = conn.execute("SELECT COUNT(*) AS n FROM quiz_scores").fetchone()["n"]
    await update.message.reply_text(
        f"<b>📊 Admin Stats</b>\nUsers: {users}\nQuiz attempts: {quizzes}",
        parse_mode=ParseMode.HTML,
    )


async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Admin only.")
        return
    message = " ".join(context.args).strip()
    if not message:
        await update.message.reply_text("Use: /broadcast your message")
        return

    with db() as conn:
        rows = conn.execute("SELECT user_id FROM users").fetchall()

    sent = 0
    for row in rows:
        try:
            await context.bot.send_message(row["user_id"], message)
            sent += 1
        except Exception:
            pass

    await update.message.reply_text(f"Broadcast complete. Sent: {sent}")


# ---------------------------------------------------------------------
# Generic text handler
# ---------------------------------------------------------------------
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    upsert_user(update.effective_user)
    if not allowed(update.effective_user.id):
        await update.message.reply_text("⏳ Rate limit active. Thoda wait karo.")
        return

    text = (update.message.text or "").strip().lower()

    if text in {"hi", "hello", "hii", "hey", "start"}:
        await start(update, context)
        return

    if "telegram bot" in text:
        await update.message.reply_text(
            "<b>🤖 Telegram Bot Learning</b>\n\n"
            "Python se Telegram bot banana seekhne ke liye pehle "
            "<code>/learn 62</code> se Python basics karo, phir secure API "
            "design aur database lessons follow karo.\n\n"
            "Bot token ko kabhi public mat karo.",
            parse_mode=ParseMode.HTML,
        )
        return

    await update.message.reply_text(
        "Mujhe command do, jaise:\n"
        "/learn 1\n"
        "/learn 62\n"
        "/quiz 27\n"
        "/search web security\n"
        "/lab\n"
        "/progress",
    )


# ---------------------------------------------------------------------
# Error handler
# ---------------------------------------------------------------------
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.exception("Unhandled exception", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ Temporary error. Please try again."
            )
        except Exception:
            pass


def build_app():
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN environment variable missing. "
            "Set your NEW Telegram bot token first."
        )

    init_db()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("learn", learn_cmd))
    app.add_handler(CommandHandler("quiz", quiz_cmd))
    app.add_handler(CommandHandler("progress", progress_cmd))
    app.add_handler(CommandHandler("categories", categories_cmd))
    app.add_handler(CommandHandler("languages", languages_cmd))
    app.add_handler(CommandHandler("lab", lab_cmd))
    app.add_handler(CommandHandler("glossary", glossary_cmd))
    app.add_handler(CommandHandler("search", search_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))

    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_error_handler(error_handler)

    return app


def main():
    if ADMIN_ID <= 0:
        raise RuntimeError("ADMIN_ID invalid. Open the CONFIG section and enter your numeric Telegram ID.")
    log.info("%s v%s starting...", BOT_NAME, VERSION)
    log.info("Lessons loaded: %d", len(LESSONS))
    log.info("Database: %s", DB_PATH)
    build_app().run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
