"""
Anshu AI Bot — Core Version + Voice Support
---------------------------------------------
Kya karta hai:
  - User /start kare -> 15 free messages milte hain
  - Free messages khatam hone ke baad -> paywall message (UPI details)
  - Admin /approve <user_id> se manually unlimited access de sakta hai
  - TEXT message -> AI text mein jawab deta hai
  - VOICE message -> bot sunta hai (Whisper se samajhta hai) aur
    VOICE mein hi jawab deta hai (un logo ke liye jo padh nahi paate)
  - Sab kuch FREE APIs se (Groq chat, Groq Whisper, Google TTS)

Zaroori setup (deploy karne se pehle):
  1. requirements.txt mein likho:
        python-telegram-bot==21.6
        groq
        gTTS

  2. .env file banao (isi folder mein, bot.py ke saath upload karo hoster ko):
        BOT_TOKEN=your_telegram_bot_token
        GROQ_API_KEY=your_groq_api_key
        ADMIN_ID=your_telegram_user_id
        UPI_ID=your_upi_id@bank
"""

import os
import sqlite3
import logging
from datetime import datetime

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from groq import Groq
from gtts import gTTS

# ---------------- Config (environment variables se aata hai) ----------------
BOT_TOKEN = os.getenv("8991270494:AAEzMXdXVWfVmZ7u-bMxUupokJLGx9XNX4g")
GROQ_API_KEY = os.getenv("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")
ADMIN_ID = os.getenv("6644342214")
UPI_ID = os.getenv("UPI_ID", "your-upi-id@bank")

FREE_MESSAGE_LIMIT = 15
PAYWALL_AMOUNT = "₹10"

GROQ_CHAT_MODEL = "llama-3.3-70b-versatile"
GROQ_WHISPER_MODEL = "whisper-large-v3"
TTS_LANG = "hi"  # Hindi voice reply. "en" karna ho toh yahan badlo.

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "users.db")
TEMP_DIR = os.path.join(BASE_DIR, "temp")
os.makedirs(TEMP_DIR, exist_ok=True)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("anshu_ai_bot")

if not BOT_TOKEN:
    raise SystemExit("❌ BOT_TOKEN missing! .env file mein BOT_TOKEN daalo.")
if not GROQ_API_KEY:
    raise SystemExit("❌ GROQ_API_KEY missing! .env file mein GROQ_API_KEY daalo.")

groq_client = Groq(api_key=GROQ_API_KEY)


# ---------------- Database ----------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            free_left INTEGER DEFAULT 15,
            is_paid INTEGER DEFAULT 0,
            joined_at TEXT,
            total_messages INTEGER DEFAULT 0
        )
        """
    )
    conn.commit()
    conn.close()


def get_user(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT user_id, free_left, is_paid, total_messages FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row


def create_user(user_id: int, username: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO users (user_id, username, free_left, is_paid, joined_at, total_messages) "
        "VALUES (?, ?, ?, 0, ?, 0)",
        (user_id, username, FREE_MESSAGE_LIMIT, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def decrement_free(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET free_left = free_left - 1, total_messages = total_messages + 1 WHERE user_id = ?",
        (user_id,),
    )
    conn.commit()
    conn.close()


def increment_total_only(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE users SET total_messages = total_messages + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def set_paid(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE users SET is_paid = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def get_stats():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*), SUM(is_paid), SUM(total_messages) FROM users")
    row = cur.fetchone()
    conn.close()
    return row


# ---------------- Shared AI logic (text aur voice dono isi ko use karte hain) ----------------
def get_paywall_text() -> str:
    return (
        f"🚫 Tumhare {FREE_MESSAGE_LIMIT} free messages khatam ho gaye.\n\n"
        f"💰 Aage unlimited use karne ke liye {PAYWALL_AMOUNT} pay karo:\n"
        f"📌 UPI ID: `{UPI_ID}`\n\n"
        f"✅ Payment ke baad, screenshot yahan bhejo — admin verify karke turant unlimited kar denge."
    )


async def get_ai_reply(user_id: int) -> tuple:
    """
    Return: (allowed: bool, remaining_after: int or None, is_paid: bool)
    Free-limit check karta hai aur counter manage karta hai.
    Actual AI call handler khud karega (taaki dono text/voice apna system prompt de sakein).
    """
    existing = get_user(user_id)
    if not existing:
        create_user(user_id, "unknown")
        existing = get_user(user_id)
    _, free_left, is_paid, _ = existing
    if not is_paid and free_left <= 0:
        return False, None, False
    return True, free_left, bool(is_paid)


async def send_voice_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, reply_text: str, user_id: int):
    """Har jawab ko VOICE mein bhi bhejta hai — taaki padhne mein dikkat waale bhi samajh sakein."""
    mp3_path = os.path.join(TEMP_DIR, f"out_{user_id}_{update.message.message_id}.mp3")
    try:
        tts = gTTS(text=reply_text, lang=TTS_LANG)
        tts.save(mp3_path)
        with open(mp3_path, "rb") as f:
            await update.message.reply_voice(voice=f)
    except Exception as e:
        log.error(f"TTS error: {e}")
        # Voice na ban paaye toh bhi text reply toh mil hi chuka hoga, isliye chup rehke aage badho
    finally:
        if os.path.exists(mp3_path):
            os.remove(mp3_path)


def call_groq_chat(user_text: str) -> str:
    response = groq_client.chat.completions.create(
        model=GROQ_CHAT_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "Tum ek helpful, friendly AI assistant ho. Hinglish (Hindi-English mix) mein "
                    "seedha aur saral jawab do, jaise kisi dost ko samjha rahe ho. Lamba answer mat do "
                    "jab tak zaroori na ho — clear aur seedha rakho, kyunki kabhi yeh jawab voice mein "
                    "bhi bola jayega."
                ),
            },
            {"role": "user", "content": user_text},
        ],
        max_tokens=600,
        temperature=0.7,
    )
    return response.choices[0].message.content


# ---------------- Handlers ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    existing = get_user(user.id)
    if not existing:
        create_user(user.id, user.username or user.first_name or "unknown")
        await update.message.reply_text(
            f"👋 Namaste {user.first_name}!\n\n"
            f"🤖 Main tumhara AI assistant hoon.\n"
            f"🎁 Tumhe {FREE_MESSAGE_LIMIT} FREE messages mile hain.\n\n"
            f"✍️ Type karke poocho, ya 🎤 Voice message bhejo — dono chalta hai!\n"
            f"Voice bhejoge toh main bhi VOICE mein hi jawab dunga."
        )
    else:
        _, free_left, is_paid, _ = existing
        if is_paid:
            await update.message.reply_text("👋 Wapas aane ka shukriya! Tumhare paas Unlimited access hai. Bolo, kya poochna hai?")
        else:
            await update.message.reply_text(f"👋 Wapas aane ka shukriya!\n📊 Free messages bache: {free_left}")


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != str(ADMIN_ID):
        return
    total_users, total_paid, total_msgs = get_stats()
    await update.message.reply_text(
        f"📊 **Bot Stats**\n\n"
        f"👥 Total Users: {total_users or 0}\n"
        f"💰 Paid Users: {total_paid or 0}\n"
        f"💬 Total Messages: {total_msgs or 0}"
    )


async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != str(ADMIN_ID):
        return
    if not context.args:
        await update.message.reply_text("Usage: /approve <user_id>")
        return
    try:
        target_id = int(context.args[0])
        set_paid(target_id)
        await update.message.reply_text(f"✅ User {target_id} ko unlimited access mil gaya.")
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text="🎉 Payment verify ho gaya! Ab tumhe Unlimited messages milenge. Dhanyavaad! 🙏",
            )
        except Exception:
            pass
    except ValueError:
        await update.message.reply_text("❌ Galat user_id. Number hona chahiye.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Normal TEXT message -> TEXT reply"""
    user = update.effective_user
    text = update.message.text

    allowed, free_left, is_paid = await get_ai_reply(user.id)
    if not allowed:
        await update.message.reply_text(get_paywall_text(), parse_mode="Markdown")
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        reply = call_groq_chat(text)
    except Exception as e:
        log.error(f"Groq chat error: {e}")
        await update.message.reply_text("⚠️ Abhi thoda issue aa raha hai, thodi der baad try karo.")
        return

    if not is_paid:
        decrement_free(user.id)
        remaining = free_left - 1
        footer = f"\n\n_({remaining} free messages bache)_" if remaining > 0 else "\n\n_(Yeh tumhara last free message tha)_"
    else:
        increment_total_only(user.id)
        footer = ""

    await update.message.reply_text(reply + footer, parse_mode="Markdown")

    # Yahi jawab VOICE mein bhi bhejo — jo padh nahi paate unke liye
    await send_voice_reply(update, context, reply, user.id)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """VOICE message -> sunta hai, samajhta hai, VOICE mein hi reply deta hai"""
    user = update.effective_user

    allowed, free_left, is_paid = await get_ai_reply(user.id)
    if not allowed:
        await update.message.reply_text(get_paywall_text(), parse_mode="Markdown")
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    ogg_path = os.path.join(TEMP_DIR, f"in_{user.id}_{update.message.message_id}.ogg")
    reply_text = None
    user_text = ""

    try:
        # Step 1: voice download karo
        tg_file = await update.message.voice.get_file()
        await tg_file.download_to_drive(custom_path=ogg_path)

        # Step 2: Groq Whisper se voice -> text (free, samajhne ke liye)
        with open(ogg_path, "rb") as f:
            transcription = groq_client.audio.transcriptions.create(
                file=(os.path.basename(ogg_path), f.read()),
                model=GROQ_WHISPER_MODEL,
            )
        user_text = transcription.text.strip()

        if not user_text:
            await update.message.reply_text("😕 Voice samajh nahi aaya, dobara bolo?")
            return

        # Step 3: AI se jawab lo (same brain jo text ke liye use hota hai)
        reply_text = call_groq_chat(user_text)

    except Exception as e:
        log.error(f"Voice handling error: {e}")
        await update.message.reply_text("⚠️ Voice process karne mein issue aaya, thodi der baad try karo.")
        return
    finally:
        if os.path.exists(ogg_path):
            os.remove(ogg_path)

    # Text bhi bhejo (jo padh sakte hain unke liye) aur voice bhi (jo nahi padh sakte unke liye)
    await update.message.reply_text(f"🗣️ Tumne poocha: {user_text[:150]}\n\n{reply_text}", parse_mode="Markdown")
    await send_voice_reply(update, context, reply_text, user.id)

    if not is_paid:
        decrement_free(user.id)
    else:
        increment_total_only(user.id)


# ---------------- Main ----------------
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("approve", approve))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    log.info("Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()
