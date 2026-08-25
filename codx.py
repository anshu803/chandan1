import io
import uuid
import threading
from urllib.parse import quote

import qrcode
import telebot
from telebot import types
from flask import Flask


# ============================================================
#                    🔧 YOUR SETTINGS
# ============================================================

BOT_TOKEN = "8827214752:AAGeObND4pSDeztVmj8A6dhNqisAlI4XX10"

ADMIN_CHANNEL_ID = -1004309680225

UPI_ID = "8303721228@ibl"


# ============================================================
#                    ⚙️ BASIC SETTINGS
# ============================================================

PRICE = 20
MERCHANT_NAME = "Code Store"

WAIT_TIME = "लगभग 3 घंटे"


# ============================================================
#                    🤖 BOT
# ============================================================

bot = telebot.TeleBot(BOT_TOKEN)

orders = {}
user_orders = {}


# ============================================================
#                    🌐 RENDER WEB SERVER
# ============================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "CODE STORE BOT IS RUNNING", 200


@app.route("/health")
def health():
    return "OK", 200


# ============================================================
#                    💻 LANGUAGE MENU
# ============================================================

def language_menu():

    keyboard = types.InlineKeyboardMarkup(row_width=2)

    keyboard.add(
        types.InlineKeyboardButton(
            "🐍 PYTHON",
            callback_data="language:Python"
        ),
        types.InlineKeyboardButton(
            "☕ JAVA",
            callback_data="language:Java"
        ),
        types.InlineKeyboardButton(
            "⚙️ C / C++",
            callback_data="language:C/C++"
        ),
        types.InlineKeyboardButton(
            "🌐 JAVASCRIPT",
            callback_data="language:JavaScript"
        ),
        types.InlineKeyboardButton(
            "🎨 HTML / CSS",
            callback_data="language:HTML/CSS"
        ),
    )

    return keyboard


# ============================================================
#                    👨‍💻 ADMIN BUTTONS
# ============================================================

def admin_buttons(order_id):

    keyboard = types.InlineKeyboardMarkup(row_width=1)

    keyboard.add(
        types.InlineKeyboardButton(
            "✅ APPROVE",
            callback_data=f"approve:{order_id}"
        )
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "❌ PAYMENT NOT VERIFIED",
            callback_data=f"payment_bad:{order_id}"
        )
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "🚫 CODE NOT AVAILABLE",
            callback_data=f"code_unavailable:{order_id}"
        )
    )

    return keyboard


# ============================================================
#                    💳 UPI QR
# ============================================================

def create_upi_qr():

    upi_url = (
        "upi://pay?"
        f"pa={quote(UPI_ID)}&"
        f"pn={quote(MERCHANT_NAME)}&"
        f"am={PRICE}&"
        "cu=INR"
    )

    qr = qrcode.QRCode(
        version=1,
        box_size=10,
        border=4
    )

    qr.add_data(upi_url)
    qr.make(fit=True)

    image = qr.make_image()

    buffer = io.BytesIO()
    buffer.name = "payment_qr.png"

    image.save(buffer, format="PNG")
    buffer.seek(0)

    return buffer


# ============================================================
#                    🚀 START
# ============================================================

@bot.message_handler(commands=["start"])
def start(message):

    bot.send_message(
        message.chat.id,

        """
<b>━━━━━━━━━━━━━━━━━━━━</b>
<b>💻 CODE STORE</b>
<b>━━━━━━━━━━━━━━━━━━━━</b>

<b>👋 WELCOME</b>

<b>💰 सभी Codes की Price: ₹20</b>

<b>👇 अपनी Language चुनें:</b>
""",

        parse_mode="HTML",
        reply_markup=language_menu()
    )


# ============================================================
#                    🐍 LANGUAGE SELECT
# ============================================================

@bot.callback_query_handler(
    func=lambda call: call.data.startswith("language:")
)
def select_language(call):

    user_id = call.from_user.id

    language = call.data.split(":", 1)[1]

    order_id = uuid.uuid4().hex[:8].upper()

    orders[order_id] = {
        "user_id": user_id,
        "username": call.from_user.username or "No Username",
        "language": language,
        "requirement": "",
        "screenshot": None,
        "status": "waiting_requirement",
        "delivery": None
    }

    user_orders[user_id] = order_id

    bot.answer_callback_query(call.id)

    bot.send_message(
        user_id,

        f"""
<b>━━━━━━━━━━━━━━━━━━━━</b>
<b>💻 {language}</b>
<b>━━━━━━━━━━━━━━━━━━━━</b>

<b>📝 अब बताइए आपको किस काम का Code चाहिए?</b>

<b>Example:</b>

<code>Python Telegram Bot</code>

<code>Java Calculator</code>

<code>HTML Website</code>

<b>अपनी पूरी requirement लिखें।</b>

<b>🆔 ORDER ID:</b>
<code>{order_id}</code>
""",

        parse_mode="HTML"
    )


# ============================================================
#                    📝 REQUIREMENT
# ============================================================

@bot.message_handler(
    func=lambda message:
    message.from_user.id in user_orders
)
def receive_requirement(message):

    user_id = message.from_user.id
    order_id = user_orders.get(user_id)

    if not order_id:
        return

    order = orders.get(order_id)

    if not order:
        return

    if order["status"] != "waiting_requirement":
        return

    if not message.text:
        return

    order["requirement"] = message.text
    order["status"] = "waiting_payment"

    bot.send_message(
        user_id,

        f"""
<b>━━━━━━━━━━━━━━━━━━━━</b>
<b>📦 ORDER CREATED</b>
<b>━━━━━━━━━━━━━━━━━━━━</b>

<b>🆔 ORDER ID:</b>
<code>{order_id}</code>

<b>💻 LANGUAGE:</b>
{order["language"]}

<b>📝 REQUIREMENT:</b>
{order["requirement"]}

<b>💰 PRICE:</b>
₹{PRICE}

<b>━━━━━━━━━━━━━━━━━━━━</b>
<b>💳 PAYMENT</b>
<b>━━━━━━━━━━━━━━━━━━━━</b>

<b>नीचे QR scan करके ₹20 payment करें।</b>

<b>📸 Payment के बाद screenshot भेजें।</b>
""",

        parse_mode="HTML"
    )

    qr = create_upi_qr()

    bot.send_photo(
        user_id,
        qr,
        caption=(
            f"💳 <b>PAYMENT ₹{PRICE}</b>\n\n"
            "📱 QR Scan करके payment करें।\n\n"
            "📸 Payment के बाद screenshot भेजें।"
        ),
        parse_mode="HTML"
    )


# ============================================================
#                    📸 PAYMENT SCREENSHOT
# ============================================================

@bot.message_handler(content_types=["photo"])
def receive_screenshot(message):

    user_id = message.from_user.id
    order_id = user_orders.get(user_id)

    if not order_id:

        bot.send_message(
            user_id,
            "❌ पहले /start करके Code order बनाइए।"
        )

        return

    order = orders.get(order_id)

    if not order:
        return

    if order["status"] != "waiting_payment":

        bot.send_message(
            user_id,
            "⚠️ इस order में अभी screenshot की आवश्यकता नहीं है।"
        )

        return

    photo_id = message.photo[-1].file_id

    order["screenshot"] = photo_id
    order["status"] = "pending_verification"

    username = order["username"]

    if username != "No Username":
        username = "@" + username

    admin_text = f"""
<b>━━━━━━━━━━━━━━━━━━━━</b>
<b>🔔 NEW CODE ORDER</b>
<b>━━━━━━━━━━━━━━━━━━━━</b>

<b>🆔 ORDER ID:</b>
<code>{order_id}</code>

<b>👤 USER ID:</b>
<code>{user_id}</code>

<b>👤 USERNAME:</b>
{username}

<b>💻 LANGUAGE:</b>
{order["language"]}

<b>📝 REQUIREMENT:</b>
{order["requirement"]}

<b>💰 AMOUNT:</b>
₹{PRICE}

<b>⏳ STATUS:</b>
PAYMENT VERIFICATION

<b>━━━━━━━━━━━━━━━━━━━━</b>
"""

    bot.send_photo(
        ADMIN_CHANNEL_ID,
        photo_id,
        caption=admin_text,
        parse_mode="HTML",
        reply_markup=admin_buttons(order_id)
    )

    bot.send_message(
        user_id,

        f"""
<b>━━━━━━━━━━━━━━━━━━━━</b>
<b>📸 SCREENSHOT RECEIVED</b>
<b>━━━━━━━━━━━━━━━━━━━━</b>

<b>🆔 ORDER ID:</b>
<code>{order_id}</code>

<b>⏳ आपका payment verification में है।</b>

<b>कृपया {WAIT_TIME} तक प्रतीक्षा करें।</b>

<b>Verification के बाद आपको update मिलेगा।</b>
""",

        parse_mode="HTML"
    )


# ============================================================
#                    👨‍💻 ADMIN ACTIONS
# ============================================================

@bot.callback_query_handler(
    func=lambda call:
    call.data.startswith("approve:")
    or call.data.startswith("payment_bad:")
    or call.data.startswith("code_unavailable:")
)
def admin_action(call):

    if call.message.chat.id != ADMIN_CHANNEL_ID:

        bot.answer_callback_query(
            call.id,
            "❌ Unauthorized",
            show_alert=True
        )

        return

    action, order_id = call.data.split(":", 1)

    order = orders.get(order_id)

    if not order:

        bot.answer_callback_query(
            call.id,
            "Order नहीं मिला।",
            show_alert=True
        )

        return

    user_id = order["user_id"]


    # ========================================================
    #                    ✅ APPROVE
    # ========================================================

    if action == "approve":

        order["status"] = "approved"

        bot.answer_callback_query(
            call.id,
            "✅ APPROVED"
        )

        bot.send_message(
            user_id,

            f"""
<b>━━━━━━━━━━━━━━━━━━━━</b>
<b>✅ PAYMENT APPROVED</b>
<b>━━━━━━━━━━━━━━━━━━━━</b>

<b>🆔 ORDER:</b>
<code>{order_id}</code>

<b>💻 LANGUAGE:</b>
{order["language"]}

<b>📦 आपका Code/File तैयार किया जा रहा है।</b>

<b>जल्द ही आपको file/link भेज दिया जाएगा।</b>
""",

            parse_mode="HTML"
        )

        bot.edit_message_reply_markup(
            ADMIN_CHANNEL_ID,
            call.message.message_id,
            reply_markup=None
        )


    # ========================================================
    #                ❌ PAYMENT NOT VERIFIED
    # ========================================================

    elif action == "payment_bad":

        order["status"] = "payment_not_verified"

        bot.answer_callback_query(
            call.id,
            "❌ PAYMENT NOT VERIFIED"
        )

        bot.send_message(
            user_id,

            f"""
<b>━━━━━━━━━━━━━━━━━━━━</b>
<b>❌ PAYMENT NOT VERIFIED</b>
<b>━━━━━━━━━━━━━━━━━━━━</b>

<b>🆔 ORDER:</b>
<code>{order_id}</code>

Payment verify नहीं हो पाया।

कृपया सही payment proof के साथ
Admin से संपर्क करें।
""",

            parse_mode="HTML"
        )

        bot.edit_message_reply_markup(
            ADMIN_CHANNEL_ID,
            call.message.message_id,
            reply_markup=None
        )


    # ========================================================
    #                 🚫 CODE NOT AVAILABLE
    # ========================================================

    elif action == "code_unavailable":

        order["status"] = "code_unavailable"

        bot.answer_callback_query(
            call.id,
            "🚫 CODE NOT AVAILABLE"
        )

        bot.send_message(
            user_id,

            f"""
<b>━━━━━━━━━━━━━━━━━━━━</b>
<b>🚫 CODE NOT AVAILABLE</b>
<b>━━━━━━━━━━━━━━━━━━━━</b>

<b>🆔 ORDER:</b>
<code>{order_id}</code>

माफ़ कीजिए, आपकी requested
requirement का Code उपलब्ध नहीं है।

कृपया दूसरी requirement भेजें।
""",

            parse_mode="HTML"
        )

        bot.edit_message_reply_markup(
            ADMIN_CHANNEL_ID,
            call.message.message_id,
            reply_markup=None
        )


# ============================================================
#              📦 ADMIN SEND FILE / LINK
#
# Private channel में:
#
# /deliver ORDER_ID FILE_LINK
#
# Example:
# /deliver A1B2C3D4 https://example.com/file.zip
# ============================================================

@bot.channel_post_handler(
    commands=["deliver"]
)
def deliver_from_channel(message):

    if message.chat.id != ADMIN_CHANNEL_ID:
        return

    parts = message.text.split(maxsplit=2)

    if len(parts) < 3:

        bot.send_message(
            ADMIN_CHANNEL_ID,
            """
<b>❌ WRONG FORMAT</b>

<code>/deliver ORDER_ID FILE_LINK</code>
""",
            parse_mode="HTML"
        )

        return

    order_id = parts[1]
    file_link = parts[2]

    order = orders.get(order_id)

    if not order:

        bot.send_message(
            ADMIN_CHANNEL_ID,
            "❌ Order ID नहीं मिला।"
        )

        return

    if order["status"] != "approved":

        bot.send_message(
            ADMIN_CHANNEL_ID,
            "❌ पहले APPROVE button दबाएँ।"
        )

        return

    user_id = order["user_id"]

    order["delivery"] = file_link
    order["status"] = "delivered"

    bot.send_message(
        user_id,

        f"""
<b>━━━━━━━━━━━━━━━━━━━━</b>
<b>🎉 CODE READY</b>
<b>━━━━━━━━━━━━━━━━━━━━</b>

<b>🆔 ORDER:</b>
<code>{order_id}</code>

<b>💻 LANGUAGE:</b>
{order["language"]}

<b>📦 YOUR CODE / FILE:</b>

{file_link}

<b>✅ ORDER COMPLETED</b>
""",

        parse_mode="HTML"
    )

    bot.send_message(
        ADMIN_CHANNEL_ID,

        f"""
<b>✅ DELIVERY SUCCESSFUL</b>

<b>ORDER:</b>
<code>{order_id}</code>

<b>User को file/link भेज दिया गया।</b>
""",

        parse_mode="HTML"
    )


# ============================================================
#                    ▶️ RUN BOT
# ============================================================

def run_bot():

    print("━━━━━━━━━━━━━━━━━━━━")
    print("🤖 CODE STORE BOT")
    print("🚀 TELEGRAM BOT STARTED")
    print("━━━━━━━━━━━━━━━━━━━━")

    bot.infinity_polling(
        skip_pending=True,
        timeout=30,
        long_polling_timeout=30
    )


if __name__ == "__main__":

    bot_thread = threading.Thread(
        target=run_bot,
        daemon=True
    )

    bot_thread.start()

    # Render Web Service port
    port = 10000

    app.run(
        host="0.0.0.0",
        port=port
    )