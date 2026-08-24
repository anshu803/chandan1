"""
═══════════════════════════════════════════════════════════════
𝐀𝐍𝐒𝐇𝐔 𝐄𝐓𝐇𝐈𝐂𝐀𝐋𝐗 — ULTIMATE POWER v4.0 (FULLY FIXED)

✅ 250+ COMMANDS
✅ ANDROID HACKING
✅ SOCIAL MEDIA HACKING (ALL PLATFORMS)
✅ CLEAR WARNINGS — Educational Purpose Only
✅ FLASH WARNINGS — Har illegal command ke saath
✅ HINDI + ENGLISH
✅ SEARCH + FILTER + PAGINATION
✅ ERROR HANDLING — Sab fix
✅ RATE LIMITING
✅ DATABASE — Auto create
✅ ALL IMPORTS — Correct

JUST ADD: BOT_TOKEN + ADMIN_ID
═══════════════════════════════════════════════════════════════
"""

import os
import sqlite3
import logging
import time
import sys
import re
from datetime import datetime
from collections import defaultdict
from typing import List, Tuple, Optional, Dict, Any

# Telegram imports
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    CallbackQueryHandler
)

# ============================================================
# 1) CONFIG — SIRF YAHAN CHANGE KARO
# ============================================================
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # ← APNA TOKEN DAALO
ADMIN_ID = 123456789  # ← APNA TELEGRAM ID DAALO (integer)

BOT_NAME = "𝐀𝐍𝐒𝐇𝐔 𝐄𝐓𝐇𝐈𝐂𝐀𝐋𝐗"
CREATOR = "Anshu"
DB_PATH = "anshu_ultimate.db"
VERSION = "4.0"
RESULTS_PER_PAGE = 10

# ============================================================
# 2) SETUP LOGGING
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger(__name__)

# ============================================================
# 3) RATE LIMITING
# ============================================================
rate_limit = defaultdict(list)

def check_rate(user_id: int) -> bool:
    """Check if user is rate limited (30 requests per minute)"""
    now = time.time()
    rate_limit[user_id] = [t for t in rate_limit[user_id] if now - t < 60]
    if len(rate_limit[user_id]) >= 30:
        return False
    rate_limit[user_id].append(now)
    return True

# ============================================================
# 4) DATABASE FUNCTIONS
# ============================================================
def init_db() -> bool:
    """Initialize database with required tables"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Users table
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_seen TEXT,
                questions_asked INTEGER DEFAULT 0
            )
        """)
        
        # Commands table
        c.execute("""
            CREATE TABLE IF NOT EXISTS commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT,
                command TEXT,
                hindi_desc TEXT,
                english_desc TEXT,
                how_to_use TEXT,
                what_it_does TEXT,
                is_illegal INTEGER DEFAULT 0,
                consequences TEXT,
                warning TEXT
            )
        """)
        
        # Logs table
        c.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                query TEXT,
                timestamp TEXT
            )
        """)
        
        conn.commit()
        conn.close()
        log.info("✅ Database initialized")
        return True
    except Exception as e:
        log.error(f"❌ Database init error: {e}")
        return False

def get_user(user_id: int) -> Optional[Tuple]:
    """Get user from database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        conn.close()
        return result
    except Exception as e:
        log.error(f"❌ Get user error: {e}")
        return None

def add_user(user_id: int, username: str) -> bool:
    """Add user to database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute(
            "INSERT OR IGNORE INTO users (user_id, username, first_seen) VALUES (?, ?, ?)",
            (user_id, username or "Unknown", now)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        log.error(f"❌ Add user error: {e}")
        return False

def log_query(user_id: int, query: str) -> bool:
    """Log user query"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute(
            "INSERT INTO logs (user_id, query, timestamp) VALUES (?, ?, ?)",
            (user_id, query, now)
        )
        c.execute(
            "UPDATE users SET questions_asked = questions_asked + 1 WHERE user_id = ?",
            (user_id,)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        log.error(f"❌ Log query error: {e}")
        return False

def search_commands(query: str, lang: str = 'hindi', category: Optional[str] = None) -> List[Tuple]:
    """Search commands in database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        if lang == 'hindi':
            search_col = 'hindi_desc'
        else:
            search_col = 'english_desc'
        
        sql = f"""
            SELECT category, command, {search_col} as desc_text, how_to_use, what_it_does, 
                   is_illegal, consequences, warning
            FROM commands 
            WHERE {search_col} LIKE ? OR command LIKE ? OR what_it_does LIKE ?
        """
        params = [f"%{query}%", f"%{query}%", f"%{query}%"]
        
        if category:
            sql += " AND category = ?"
            params.append(category)
        
        c.execute(sql, params)
        results = c.fetchall()
        conn.close()
        return results
    except Exception as e:
        log.error(f"❌ Search error: {e}")
        return []

def get_categories() -> List[str]:
    """Get all categories"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT DISTINCT category FROM commands ORDER BY category")
        results = [row[0] for row in c.fetchall()]
        conn.close()
        return results
    except Exception as e:
        log.error(f"❌ Categories error: {e}")
        return []

def get_commands_by_category(category: str) -> List[Tuple]:
    """Get commands by category"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "SELECT command, hindi_desc, is_illegal FROM commands WHERE category = ? LIMIT 20",
            (category,)
        )
        results = c.fetchall()
        conn.close()
        return results
    except Exception as e:
        log.error(f"❌ Category commands error: {e}")
        return []

# ============================================================
# 5) COMPLETE DATABASE SEED — 250+ COMMANDS
# ============================================================
def seed_database() -> bool:
    """Seed database with 250+ commands"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Check if already seeded
        c.execute("SELECT COUNT(*) FROM commands")
        if c.fetchone()[0] > 0:
            conn.close()
            log.info("✅ Commands already seeded")
            return True
        
        # Warning templates
        WARNING_EDUCATIONAL = "⚠️ EDUCATIONAL PURPOSE ONLY — Sirf apne systems pe practice karo. Doosron ka hack karna ILLEGAL hai."
        WARNING_ILLEGAL = "🔴 ILLEGAL — 3-10 saal jail + 5-20 lakh fine. Sirf apne lab mein practice karo."
        WARNING_SOCIAL = "🔴 SOCIAL MEDIA HACKING — 5-10 saal jail + 10-20 lakh fine. Identity theft ka case ban sakta hai."
        WARNING_2FA = "🔴 2FA BYPASS — 7-10 saal jail + 15-20 lakh fine. SIM swap fraud ka case."
        WARNING_PHISHING = "🔴 PHISHING — 5-10 saal jail + 10-15 lakh fine. Cyber fraud ka case."
        WARNING_CARDING = "🔴 CARDING — 7-10 saal jail + 20-50 lakh fine. Financial fraud ka case."
        WARNING_OSINT = "⚠️ OSINT — Sirf legal intelligence gathering ke liye. Stalking illegal hai."
        
        commands = [
            # =========================================================
            # SETUP (15)
            # =========================================================
            ("Setup", "pkg update && pkg upgrade", "Termux packages update", "Update packages", "pkg update && pkg upgrade → Enter", "Sab packages latest version mein", 0, "", WARNING_EDUCATIONAL),
            ("Setup", "pkg install python", "Python install", "Install Python", "pkg install python → Enter", "Python scripts chalane ke liye", 0, "", WARNING_EDUCATIONAL),
            ("Setup", "pkg install git", "Git install", "Install Git", "pkg install git → Enter", "GitHub se tools clone", 0, "", WARNING_EDUCATIONAL),
            ("Setup", "pkg install nmap", "Nmap scanner", "Install Nmap", "pkg install nmap → Enter", "Network scan", 0, "", WARNING_EDUCATIONAL),
            ("Setup", "pkg install hydra", "Hydra brute force", "Install Hydra", "pkg install hydra → Enter", "Password brute force", 0, "", WARNING_EDUCATIONAL),
            ("Setup", "pkg install sqlmap", "SQL injection tool", "Install SQLmap", "pkg install sqlmap → Enter", "SQL injection", 0, "", WARNING_EDUCATIONAL),
            ("Setup", "pkg install metasploit", "Metasploit framework", "Install Metasploit", "pkg install metasploit → Enter", "Exploitation framework", 0, "", WARNING_EDUCATIONAL),
            ("Setup", "pkg install aircrack-ng", "WiFi hacking suite", "Install Aircrack-ng", "pkg install aircrack-ng → Enter", "WiFi password cracking", 0, "", WARNING_EDUCATIONAL),
            ("Setup", "pkg install john", "John the Ripper", "Install John", "pkg install john → Enter", "Password hash cracking", 0, "", WARNING_EDUCATIONAL),
            ("Setup", "pkg install tor", "Tor anonymity", "Install Tor", "pkg install tor → Enter", "Dark web access", 0, "", WARNING_EDUCATIONAL),
            ("Setup", "pkg install proxychains", "Proxy chain", "Install Proxychains", "pkg install proxychains → Enter", "Traffic proxy through", 0, "", WARNING_EDUCATIONAL),
            ("Setup", "pkg install wget", "Wget downloader", "Install Wget", "pkg install wget → Enter", "Download files", 0, "", WARNING_EDUCATIONAL),
            ("Setup", "pkg install curl", "Curl HTTP tool", "Install Curl", "pkg install curl → Enter", "HTTP requests", 0, "", WARNING_EDUCATIONAL),
            ("Setup", "pkg install ruby", "Ruby language", "Install Ruby", "pkg install ruby → Enter", "Ruby scripts", 0, "", WARNING_EDUCATIONAL),
            ("Setup", "termux-setup-storage", "Phone storage access", "Storage access", "termux-setup-storage → Enter", "Phone files access", 0, "", WARNING_EDUCATIONAL),
            
            # =========================================================
            # BASICS (12)
            # =========================================================
            ("Basics", "ls", "Files dikhata hai", "Shows files", "ls → Enter", "File list", 0, "", WARNING_EDUCATIONAL),
            ("Basics", "cd foldername", "Folder mein jao", "Navigate to folder", "cd Downloads → Enter", "Folder change", 0, "", WARNING_EDUCATIONAL),
            ("Basics", "pwd", "Current path", "Show current path", "pwd → Enter", "GPS jaise location", 0, "", WARNING_EDUCATIONAL),
            ("Basics", "mkdir foldername", "Folder banayein", "Create folder", "mkdir mytools → Enter", "Naya folder", 0, "", WARNING_EDUCATIONAL),
            ("Basics", "rm filename", "File delete", "Delete file", "rm old.txt → Enter", "Permanent delete", 0, "", WARNING_EDUCATIONAL),
            ("Basics", "cp file1 file2", "File copy", "Copy file", "cp a.txt b.txt → Enter", "Duplicate banayein", 0, "", WARNING_EDUCATIONAL),
            ("Basics", "mv file1 file2", "File rename/move", "Rename/move file", "mv old.txt new.txt → Enter", "Rename ya move", 0, "", WARNING_EDUCATIONAL),
            ("Basics", "cat filename", "File content dikhayein", "Show file content", "cat data.txt → Enter", "Content dikhayein", 0, "", WARNING_EDUCATIONAL),
            ("Basics", "clear", "Screen saaf", "Clear screen", "clear → Enter", "Screen refresh", 0, "", WARNING_EDUCATIONAL),
            ("Basics", "chmod +x filename", "Executable banayein", "Make executable", "chmod +x script.sh → Enter", "Script run karein", 0, "", WARNING_EDUCATIONAL),
            ("Basics", "echo 'text'", "Text print", "Print text", "echo Hello → Enter", "Text dikhayein", 0, "", WARNING_EDUCATIONAL),
            ("Basics", "whoami", "Username dikhayein", "Show username", "whoami → Enter", "Current user", 0, "", WARNING_EDUCATIONAL),
            
            # =========================================================
            # RECON (15)
            # =========================================================
            ("Recon", "nmap -sV 192.168.1.1", "Apne router ka scan", "Scan your router", "nmap -sV 192.168.1.1 → Enter", "Open ports", 0, "", WARNING_EDUCATIONAL),
            ("Recon", "nmap -sn 192.168.1.0/24", "Network scan", "Scan network", "nmap -sn 192.168.1.0/24 → Enter", "Devices list", 0, "", WARNING_EDUCATIONAL),
            ("Recon", "nmap -O 192.168.1.1", "OS detection", "OS detection", "nmap -O 192.168.1.1 → Enter", "OS pata chale", 0, "", WARNING_EDUCATIONAL),
            ("Recon", "whois google.com", "Domain info", "Domain info", "whois google.com → Enter", "Owner, date, email", 0, "", WARNING_EDUCATIONAL),
            ("Recon", "nslookup google.com", "DNS lookup", "DNS lookup", "nslookup google.com → Enter", "IP address", 0, "", WARNING_EDUCATIONAL),
            ("Recon", "dig google.com", "Advanced DNS", "Advanced DNS", "dig google.com → Enter", "Detailed DNS", 0, "", WARNING_EDUCATIONAL),
            ("Recon", "traceroute google.com", "Network path", "Network path", "traceroute google.com → Enter", "Route dikhayein", 0, "", WARNING_EDUCATIONAL),
            ("Recon", "nmap -sS -A -T4 target.com", "Stealth scan", "Stealth scan", "nmap -sS -A -T4 target.com → Enter", "Full target info", 1, "3-7 saal jail + 5 lakh fine", WARNING_ILLEGAL),
            ("Recon", "nmap -p 1-65535 -sV target.com", "Full port scan", "Full port scan", "nmap -p 1-65535 -sV target.com → Enter", "All 65535 ports", 1, "3-5 saal jail", WARNING_ILLEGAL),
            ("Recon", "masscan -p1-65535 target.com", "Mass scanner", "Mass scanner", "masscan -p1-65535 target.com → Enter", "10x faster", 1, "5 saal jail", WARNING_ILLEGAL),
            ("Recon", "theHarvester -d domain.com -b google", "Email harvest", "Email harvest", "theHarvester -d target.com -b google → Enter", "Emails, subdomains", 0, "", WARNING_EDUCATIONAL),
            ("Recon", "sherlock username", "Social media search", "Social media search", "sherlock anshu → Enter", "300+ platforms", 0, "", WARNING_OSINT),
            ("Recon", "phoneinfoga -n 9876543210", "Phone OSINT", "Phone OSINT", "phoneinfoga -n 9876543210 → Enter", "Carrier, location", 0, "", WARNING_OSINT),
            ("Recon", "recon-ng", "Recon framework", "Recon framework", "recon-ng → Enter", "Complete OSINT", 0, "", WARNING_OSINT),
            ("Recon", "shodan host IP", "Shodan lookup", "Shodan lookup", "shodan host 8.8.8.8 → Enter", "Device intelligence", 0, "", WARNING_OSINT),
            
            # =========================================================
            # WIFI (12)
            # =========================================================
            ("WiFi", "airmon-ng start wlan0", "Monitor mode on", "Monitor mode on", "airmon-ng start wlan0 → Enter", "WiFi special mode", 0, "", WARNING_EDUCATIONAL),
            ("WiFi", "airodump-ng wlan0mon", "WiFi scan", "WiFi scan", "airodump-ng wlan0mon → Enter", "Nearby networks", 0, "", WARNING_EDUCATIONAL),
            ("WiFi", "aircrack-ng -w wordlist.txt -b MAC capture.cap", "WiFi crack", "WiFi crack", "aircrack-ng -w passwords.txt -b 00:11:22:33:44:55 capture.cap → Enter", "WiFi password todna", 1, "5-7 saal jail + 10 lakh fine", WARNING_ILLEGAL),
            ("WiFi", "aireplay-ng -0 0 -a MAC wlan0mon", "Deauth attack", "Deauth attack", "aireplay-ng -0 0 -a 00:11:22:33:44:55 wlan0mon → Enter", "WiFi disconnect", 1, "5 saal jail", WARNING_ILLEGAL),
            ("WiFi", "wash -i wlan0mon", "WPS networks", "WPS networks", "wash -i wlan0mon → Enter", "WPS enabled", 0, "", WARNING_EDUCATIONAL),
            ("WiFi", "reaver -i wlan0mon -b MAC", "WPS brute", "WPS brute", "reaver -i wlan0mon -b 00:11:22:33:44:55 → Enter", "WPS PIN guess", 1, "5-7 saal jail", WARNING_ILLEGAL),
            ("WiFi", "wifite --wpa --wps", "Auto WiFi hack", "Auto WiFi hack", "wifite --wpa --wps → Enter", "Auto crack", 1, "5-7 saal jail", WARNING_ILLEGAL),
            ("WiFi", "aircrack-ng -w wordlist.txt capture.cap", "Crack capture", "Crack capture", "aircrack-ng -w rockyou.txt capture.cap → Enter", "Handshake crack", 1, "5 saal jail", WARNING_ILLEGAL),
            ("WiFi", "airmon-ng stop wlan0mon", "Monitor mode off", "Monitor mode off", "airmon-ng stop wlan0mon → Enter", "Normal mode", 0, "", WARNING_EDUCATIONAL),
            ("WiFi", "iwconfig", "WiFi config", "WiFi config", "iwconfig → Enter", "Adapter info", 0, "", WARNING_EDUCATIONAL),
            ("WiFi", "ifconfig", "Network interfaces", "Network interfaces", "ifconfig → Enter", "IP, MAC", 0, "", WARNING_EDUCATIONAL),
            ("WiFi", "arp-scan -l", "ARP scan", "ARP scan", "arp-scan -l → Enter", "Network devices", 0, "", WARNING_EDUCATIONAL),
            
            # =========================================================
            # BRUTE FORCE (10)
            # =========================================================
            ("Brute Force", "hydra -l admin -P wordlist.txt ssh://target.com", "SSH brute", "SSH brute", "hydra -l admin -P passwords.txt ssh://target.com → Enter", "SSH password todna", 1, "3-7 saal jail + 10 lakh fine", WARNING_ILLEGAL),
            ("Brute Force", "hydra -l root -P wordlist.txt ftp://target.com", "FTP brute", "FTP brute", "hydra -l root -P passwords.txt ftp://target.com → Enter", "FTP password todna", 1, "3-5 saal jail", WARNING_ILLEGAL),
            ("Brute Force", "hydra -L users.txt -P pass.txt rdp://target.com", "RDP brute", "RDP brute", "hydra -L users.txt -P pass.txt rdp://target.com → Enter", "Windows RDP brute", 1, "5-7 saal jail", WARNING_ILLEGAL),
            ("Brute Force", "hydra -l admin -P pass.txt http-post-form", "Web brute", "Web brute", "hydra -l admin -P pass.txt http-post-form → Enter", "Website login brute", 1, "3-5 saal jail", WARNING_ILLEGAL),
            ("Brute Force", "ncrack -p ssh target.com", "Ncrack SSH", "Ncrack SSH", "ncrack -p ssh target.com → Enter", "SSH brute", 1, "5 saal jail", WARNING_ILLEGAL),
            ("Brute Force", "medusa -h target.com -U users.txt -P pass.txt -M ssh", "Medusa SSH", "Medusa SSH", "medusa -h target.com -U users.txt -P pass.txt -M ssh → Enter", "SSH brute", 1, "5 saal jail", WARNING_ILLEGAL),
            ("Brute Force", "crowbar -b ssh -u admin -C pass.txt target.com", "Crowbar SSH", "Crowbar SSH", "crowbar -b ssh -u admin -C pass.txt target.com → Enter", "SSH brute", 1, "5 saal jail", WARNING_ILLEGAL),
            ("Brute Force", "patator ssh_login host=target.com user=admin password=FILE0 0=pass.txt", "Patator SSH", "Patator SSH", "patator ssh_login host=target.com user=admin password=FILE0 0=pass.txt → Enter", "SSH brute", 1, "5 saal jail", WARNING_ILLEGAL),
            ("Brute Force", "hydra -l admin -P pass.txt ftp://targ