#!/usr/bin/env python3
"""
CYBER FRAUD REPORT ASSISTANT
Basic -> Advanced | Telegram + Gemini + PDF + Evidence

Install:
    pip install -U python-telegram-bot google-genai reportlab

Environment:
    BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
    GEMINI_API_KEY=YOUR_GEMINI_API_KEY
    GEMINI_MODEL=gemini-3.8-flash

Run:
    python bot.py

Safety:
- Never collect OTP, PIN, CVV, passwords, or recovery codes.
- This bot prepares a complaint draft; it does not impersonate government
  services or claim to submit a complaint without an authorized API.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import secrets
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from google import genai


# ========================= CONFIG =========================

BOT_TOKEN = os.getenv("BOT_TOKEN", "8991270494:AAEzMXdXVWfVmZ7u-bMxUupokJLGx9XNX4g")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AQ.Ab8RN6KL1UcwjTWV5-kK98B9SklLX5m2noL36WiEUgLTx7gANw")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

PORTAL_URL = "https://cybercrime.gov.in/"
HELPLINE = "1930"

MAX_FILE_BYTES = 15 * 1024 * 1024
MAX_EVIDENCE = 8
MAX_TEXT = 5000

BASE_DIR = Path(__file__).resolve().parent
TEMP_ROOT = BASE_DIR / "tmp_cases"
TEMP_ROOT.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("cyber-fraud-bot")


# ========================= STATES =========================

(
    CONSENT,
    LANGUAGE,
    AMOUNT,
    DATE,
    PLATFORM,
    DESCRIPTION,
    EVIDENCE,
    REVIEW,
) = range(8)


# ========================= DATA =========================

@dataclass
class FraudCase:
    case_id: str
    user_id: int
    language: str = "hi"
    amount: str = ""
    date: str = ""
    platform: str = ""
    description: str = ""
    voice_transcript: str = ""
    evidence: list[str] = field(default_factory=list)
    evidence_meta: list[dict] = field(default_factory=list)
    ai_observations: list[str] = field(default_factory=list)
    ai_report: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


ACTIVE_CASES: dict[int, FraudCase] = {}


# ========================= SECURITY =========================

SENSITIVE_WORDS = (
    "otp", "one time password", "cvv", "upi pin", "pin",
    "password", "passwd", "passcode", "recovery code",
    "login password", "banking password",
)

ALLOWED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".pdf",
    ".txt", ".csv",
}


def is_sensitive_request(text: str) -> bool:
    lowered = (text or "").lower()
    return any(word in lowered for word in SENSITIVE_WORDS)


def clean_text(text: str, limit: int = MAX_TEXT) -> str:
    return (text or "").strip()[:limit]


def create_case(user_id: int) -> FraudCase:
    case_id = (
        "CYB-"
        + datetime.now().strftime("%Y%m%d")
        + "-"
        + secrets.token_hex(3).upper()
    )
    case = FraudCase(case_id=case_id, user_id=user_id)
    ACTIVE_CASES[user_id] = case
    (TEMP_ROOT / case_id).mkdir(parents=True, exist_ok=True)
    return case


def get_case(update: Update) -> Optional[FraudCase]:
    user = update.effective_user
    if not user:
        return None
    return ACTIVE_CASES.get(user.id)


def get_case_dir(case: FraudCase) -> Path:
    return TEMP_ROOT / case.case_id


def cleanup_case(case: FraudCase) -> None:
    ACTIVE_CASES.pop(case.user_id, None)
    shutil.rmtree(get_case_dir(case), ignore_errors=True)


# ========================= KEYBOARDS =========================

def home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚨 Report Fraud", callback_data="start_report")],
        [InlineKeyboardButton("🔐 Privacy", callback_data="privacy")],
        [InlineKeyboardButton("🌐 Official Portal", url=PORTAL_URL)],
    ])


def consent_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Continue", callback_data="consent_yes"),
            InlineKeyboardButton("❌ Cancel", callback_data="consent_no"),
        ]
    ])


def language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇮🇳 हिंदी", callback_data="lang_hi"),
            InlineKeyboardButton("🇺🇸 English", callback_data="lang_en"),
        ]
    ])


def evidence_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Done with Evidence", callback_data="evidence_done")],
        [InlineKeyboardButton("🗑 Cancel & Delete", callback_data="cancel_case")],
    ])


def review_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🤖 Generate Complaint", callback_data="generate_report")],
        [InlineKeyboardButton("🗑 Cancel & Delete", callback_data="cancel_case")],
    ])


def portal_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 Official Cyber Crime Portal", url=PORTAL_URL)],
        [InlineKeyboardButton("📞 1930", url="tel:1930")],
    ])


def lang(case: FraudCase, hi: str, en: str) -> str:
    return hi if case.language == "hi" else en


# ========================= GEMINI =========================

def get_gemini_client() -> genai.Client:
    if (
        not GEMINI_API_KEY
        or GEMINI_API_KEY.startswith("PASTE_")
    ):
        raise RuntimeError("GEMINI_API_KEY is not configured.")
    return genai.Client(api_key=GEMINI_API_KEY)


def generate_text(prompt: str) -> str:
    client = get_gemini_client()
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
    )
    return (response.text or "").strip()


def analyze_evidence(path: Path) -> str:
    """
    Gemini multimodal analysis.
    Only factual observations are requested.
    """
    client = get_gemini_client()

    uploaded = client.files.upload(file=str(path))

    prompt = """
You are assisting with a cyber-fraud complaint.

Analyze this evidence only for facts visibly present in it.

Rules:
- Do NOT guess.
- Do NOT invent missing information.
- Do NOT expose or repeat OTP, PIN, CVV, passwords, recovery codes,
  or authentication secrets.
- If sensitive credentials appear, say that sensitive credentials are present
  without reproducing them.
- Return concise factual observations only.
"""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[uploaded, prompt],
    )
    return (response.text or "").strip()


def build_ai_report(case: FraudCase) -> str:
    evidence_list = "\n".join(
        f"- {item.get('name', 'Evidence')}: "
        f"{item.get('observation', 'No observation')}"
        for item in case.evidence_meta
    ) or "- No evidence supplied"

    prompt = f"""
Prepare a professional cyber-fraud complaint DRAFT.

Case ID: {case.case_id}
Language: {case.language}

Victim-provided information:
Amount: {case.amount or "Not provided"}
Date: {case.date or "Not provided"}
Platform/payment method: {case.platform or "Not provided"}
Narrative:
{case.description or "Not provided"}

Voice transcript:
{case.voice_transcript or "Not provided"}

Evidence observations:
{evidence_list}

Strict requirements:
1. Never invent facts.
2. Never guess names, phone numbers, UTRs, account numbers, dates,
   addresses, locations, transaction IDs, or perpetrators.
3. Never include OTP, PIN, CVV, password, or recovery codes.
4. Mark missing information as "Not provided".
5. Clearly label this as a complaint draft.
6. Provide:
   - Incident summary
   - Amount
   - Date
   - Platform/payment method
   - Victim narrative
   - Evidence summary
   - Missing information
   - Suggested information to enter into the official portal
   - Safety reminder
"""

    return generate_text(prompt)


# ========================= PDF =========================

def make_pdf(case: FraudCase, report: str) -> Path:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.units import mm

    output = get_case_dir(case) / f"{case.case_id}_complaint_draft.pdf"

    font_name = "Helvetica"

    font_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/system/fonts/NotoSans-Regular.ttf",
    ]

    for font_path in font_candidates:
        if Path(font_path).exists():
            try:
                pdfmetrics.registerFont(
                    TTFont("CaseUnicode", font_path)
                )
                font_name = "CaseUnicode"
                break
            except Exception:
                pass

    styles = getSampleStyleSheet()

    normal = ParagraphStyle(
        "CaseNormal",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=9.5,
        leading=14,
        spaceAfter=6,
    )

    heading = ParagraphStyle(
        "CaseHeading",
        parent=styles["Heading2"],
        fontName=font_name,
        fontSize=13,
        leading=16,
        spaceBefore=8,
        spaceAfter=6,
    )

    title = ParagraphStyle(
        "CaseTitle",
        parent=styles["Title"],
        fontName=font_name,
        fontSize=17,
        leading=21,
        spaceAfter=12,
    )

    def esc(value: object) -> str:
        return (
            str(value)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    doc = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Cyber Fraud Complaint Draft {case.case_id}",
    )

    story = [
        Paragraph("Cyber Fraud Complaint Draft", title),
        Paragraph(f"<b>Case ID:</b> {esc(case.case_id)}", normal),
        Paragraph(f"<b>Created:</b> {esc(case.created_at)}", normal),
        Paragraph(
            "<b>Important:</b> This is a preparation draft, "
            "not an official government submission.",
            normal,
        ),
        Paragraph("Incident Details", heading),
        Paragraph(f"<b>Amount:</b> {esc(case.amount or 'Not provided')}", normal),
        Paragraph(f"<b>Date:</b> {esc(case.date or 'Not provided')}", normal),
        Paragraph(
            f"<b>Platform:</b> {esc(case.platform or 'Not provided')}",
            normal,
        ),
        Paragraph("Victim Narrative", heading),
        Paragraph(
            esc(case.description or "Not provided").replace("\n", "<br/>"),
            normal,
        ),
    ]

    if case.voice_transcript:
        story.extend([
            Paragraph("Voice Transcript", heading),
            Paragraph(
                esc(case.voice_transcript).replace("\n", "<br/>"),
                normal,
            ),
        ])

    story.append(Paragraph("Evidence", heading))

    if case.evidence_meta:
        for index, item in enumerate(case.evidence_meta, 1):
            story.append(
                Paragraph(
                    f"{index}. <b>{esc(item.get('name', 'Evidence'))}</b>",
                    normal,
                )
            )
            observation = item.get("observation", "")
            if observation:
                story.append(
                    Paragraph(
                        esc(observation).replace("\n", "<br/>"),
                        normal,
                    )
                )
    else:
        story.append(Paragraph("No evidence supplied.", normal))

    story.extend([
        Paragraph("AI-Assisted Complaint Draft", heading),
    ])

    for line in report.splitlines():
        if line.strip():
            story.append(Paragraph(esc(line), normal))

    story.extend([
        Paragraph("Official Reporting", heading),
        Paragraph(
            f"Official portal: {esc(PORTAL_URL)}<br/>"
            f"Cyber fraud helpline: {HELPLINE}",
            normal,
        ),
        Paragraph(
            "Do not send OTP, PIN, CVV, passwords, or recovery codes.",
            normal,
        ),
    ])

    doc.build(story)
    return output


# ========================= COMMANDS =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return ConversationHandler.END

    await update.message.reply_text(
        "🚨 <b>Cyber Fraud Report Assistant</b>\n\n"
        "मैं cyber-fraud complaint draft तैयार करने में मदद करता हूँ।\n\n"
        "❌ OTP / PIN / CVV / password मत भेजें।\n"
        "📞 Financial cyber fraud में 1930 पर तुरंत संपर्क करें।\n"
        "🌐 Official portal नीचे है।",
        parse_mode="HTML",
        reply_markup=home_keyboard(),
    )
    return ConversationHandler.END


async def privacy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔐 <b>Privacy</b>\n\n"
        "• Application permanent complaint database नहीं रखता।\n"
        "• Evidence processing के लिए temporary files बन सकती हैं।\n"
        "• Completed/cancelled cases की temporary files delete की जाती हैं।\n"
        "• Telegram और AI provider की अपनी policies हो सकती हैं।\n"
        "• OTP/PIN/CVV/password कभी न भेजें।",
        parse_mode="HTML",
    )


async def privacy_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    q = update.callback_query
    await q.answer()
    await q.message.reply_text(
        "🔐 <b>Privacy</b>\n\n"
        "यह bot complaint preparation के लिए है। "
        "Temporary evidence processing के बाद हटाने की कोशिश की जाती है।\n\n"
        "OTP, PIN, CVV या password कभी न भेजें।",
        parse_mode="HTML",
    )


async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    case = get_case(update)
    if case:
        cleanup_case(case)
        await update.message.reply_text(
            "🗑 Active case और temporary evidence हटाने की कोशिश की गई।"
        )
    else:
        await update.message.reply_text("कोई active case नहीं है।")


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    case = get_case(update)
    if case:
        cleanup_case(case)
    await update.message.reply_text("❌ Case cancelled.")


# ========================= FLOW =========================

async def start_report(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    q = update.callback_query
    await q.answer()

    case = create_case(q.from_user.id)

    await q.message.reply_text(
        "⚠️ <b>Safety & Privacy Notice</b>\n\n"
        "Complaint बनाने के लिए incident details और evidence लिए जाएंगे.\n\n"
        "❌ OTP / PIN / CVV / password बिल्कुल मत भेजें.\n\n"
        "Continue?",
        parse_mode="HTML",
        reply_markup=consent_keyboard(),
    )
    return CONSENT


async def consent_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    q = update.callback_query
    await q.answer()

    case = ACTIVE_CASES.get(q.from_user.id)
    if not case:
        await q.message.reply_text("Session expired. /start करें.")
        return ConversationHandler.END

    if q.data == "consent_no":
        cleanup_case(case)
        await q.message.reply_text("Case cancelled.")
        return ConversationHandler.END

    await q.message.reply_text(
        "भाषा चुनें:",
        reply_markup=language_keyboard(),
    )
    return LANGUAGE


async def language_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    q = update.callback_query
    await q.answer()

    case = ACTIVE_CASES.get(q.from_user.id)
    if not case:
        return ConversationHandler.END

    case.language = "hi" if q.data == "lang_hi" else "en"

    await q.message.reply_text(
        lang(
            case,
            "💰 कितनी राशि का fraud हुआ? उदाहरण: 20000",
            "💰 How much money was lost? Example: 20000",
        )
    )
    return AMOUNT


async def amount_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    case = get_case(update)
    if not case:
        return ConversationHandler.END

    text = clean_text(update.message.text, 100)

    if is_sensitive_request(text):
        await update.message.reply_text(
            "⚠️ OTP/PIN/CVV/password जैसी sensitive जानकारी मत भेजें। "
            "केवल fraud amount भेजें."
        )
        return AMOUNT

    case.amount = text

    await update.message.reply_text(
        lang(
            case,
            "📅 घटना/transaction की तारीख बताएं।",
            "📅 Enter the incident/transaction date.",
        )
    )
    return DATE


async def date_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    case = get_case(update)
    if not case:
        return ConversationHandler.END

    case.date = clean_text(update.message.text, 100)

    await update.message.reply_text(
        lang(
            case,
            "💳 किस platform/payment method से fraud हुआ?",
            "💳 Which platform/payment method was involved?",
        )
    )
    return PLATFORM


async def platform_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    case = get_case(update)
    if not case:
        return ConversationHandler.END

    case.platform = clean_text(update.message.text, 300)

    await update.message.reply_text(
        lang(
            case,
            "📝 अब पूरा incident अपने शब्दों में बताएं। "
            "OTP/PIN/password न भेजें।",
            "📝 Describe what happened in your own words. "
            "Do not send OTP/PIN/password.",
        )
    )
    return DESCRIPTION


async def description_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    case = get_case(update)
    if not case:
        return ConversationHandler.END

    text = clean_text(update.message.text)

    if is_sensitive_request(text):
        await update.message.reply_text(
            "⚠️ Message में sensitive credential information लग रही है. "
            "OTP/PIN/CVV/password हटाकर incident फिर लिखें."
        )
        return DESCRIPTION

    case.description = text

    await update.message.reply_text(
        lang(
            case,
            "📎 अब evidence भेज सकते हैं: screenshot/photo/PDF/document.\n"
            "काम पूरा होने पर नीचे Done दबाएं.",
            "📎 Send evidence: screenshot/photo/PDF/document.\n"
            "Press Done when finished.",
        ),
        reply_markup=evidence_keyboard(),
    )
    return EVIDENCE


# ========================= EVIDENCE =========================

async def save_telegram_file(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> Optional[Path]:
    case = get_case(update)
    if not case:
        return None

    if len(case.evidence) >= MAX_EVIDENCE:
        await update.message.reply_text(
            f"Maximum {MAX_EVIDENCE} evidence files allowed."
        )
        return None

    message = update.message
    tg_file = None
    original_name = "evidence"

    if message.photo:
        photo = message.photo[-1]
        tg_file = await context.bot.get_file(photo.file_id)
        original_name = "photo.jpg"

    elif message.document:
        document = message.document
        if document.file_size and document.file_size > MAX_FILE_BYTES:
            await message.reply_text("❌ File is too large.")
            return None

        original_name = document.file_name or "document"
        suffix = Path(original_name).suffix.lower()

        if suffix not in ALLOWED_EXTENSIONS:
            await message.reply_text(
                "❌ Unsupported file type. Allowed: JPG, PNG, WEBP, PDF, TXT, CSV."
            )
            return None

        tg_file = await context.bot.get_file(document.file_id)

    else:
        return None

    target_dir = get_case_dir(case)
    suffix = Path(original_name).suffix.lower() or ".bin"

    safe_name = (
        secrets.token_hex(8) + suffix
    )
    target = target_dir / safe_name

    await tg_file.download_to_drive(custom_path=str(target))

    if target.stat().st_size > MAX_FILE_BYTES:
        target.unlink(missing_ok=True)
        await message.reply_text("❌ File is too large.")
        return None

    case.evidence.append(str(target))
    case.evidence_meta.append({
        "name": original_name[:150],
        "type": suffix,
        "observation": "",
    })

    return target


async def evidence_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    case = get_case(update)
    if not case:
        return ConversationHandler.END

    if update.message.text and is_sensitive_request(update.message.text):
        await update.message.reply_text(
            "⚠️ Sensitive credentials मत भेजें. "
            "Evidence में OTP/PIN/password हो तो उसे crop/redact करें."
        )
        return EVIDENCE

    path = await save_telegram_file(update, context)

    if not path:
        await update.message.reply_text(
            "📎 Evidence के लिए photo/document भेजें.",
            reply_markup=evidence_keyboard(),
        )
        return EVIDENCE

    await update.message.chat.send_action(ChatAction.TYPING)

    # Multimodal analysis for images/PDFs. If AI fails, the evidence remains
    # attached but no fabricated observation is added.
    try:
        if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".pdf"}:
            observation = await asyncio.to_thread(
                analyze_evidence, path
            )
            case.evidence_meta[-1]["observation"] = clean_text(
                observation, 3000
            )
    except Exception:
        log.exception("Evidence analysis failed for case %s", case.case_id)

    await update.message.reply_text(
        "✅ Evidence received.\n"
        "और भेजना हो तो भेजें, वरना Done दबाएं.",
        reply_markup=evidence_keyboard(),
    )
    return EVIDENCE


async def evidence_done(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    q = update.callback_query
    await q.answer()

    case = ACTIVE_CASES.get(q.from_user.id)
    if not case:
        return ConversationHandler.END

    await q.message.reply_text(
        lang(
            case,
            "🔎 Review:\n"
            f"Case: {case.case_id}\n"
            f"Amount: {case.amount}\n"
            f"Date: {case.date}\n"
            f"Platform: {case.platform}\n"
            f"Evidence: {len(case.evidence)}\n\n"
            "Report generate करें?",
            "🔎 Review:\n"
            f"Case: {case.case_id}\n"
            f"Amount: {case.amount}\n"
            f"Date: {case.date}\n"
            f"Platform: {case.platform}\n"
            f"Evidence: {len(case.evidence)}\n\n"
            "Generate the report?",
        ),
        reply_markup=review_keyboard(),
    )
    return REVIEW


# ========================= REPORT =========================

async def generate_report(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    q = update.callback_query
    await q.answer()

    case = ACTIVE_CASES.get(q.from_user.id)
    if not case:
        await q.message.reply_text("Session expired.")
        return ConversationHandler.END

    await q.message.reply_text("🤖 Complaint draft तैयार हो रहा है...")

    try:
        report = await asyncio.to_thread(build_ai_report, case)
        case.ai_report = report

        pdf = await asyncio.to_thread(
            make_pdf, case, report
        )

        with pdf.open("rb") as document:
            await q.message.reply_document(
                document=document,
                filename=pdf.name,
                caption=(
                    f"📄 Complaint draft\n"
                    f"Case ID: {case.case_id}\n\n"
                    "इसे official portal पर review करके submit करें."
                ),
            )

        await q.message.reply_text(
            "✅ Draft तैयार है.\n\n"
            "⚠️ यह official submission नहीं है.\n"
            "Financial cyber fraud में 1930 पर तुरंत संपर्क करें.\n\n"
            "Temporary evidence cleanup किया जा रहा है.",
            reply_markup=portal_keyboard(),
        )

        # Cleanup AFTER PDF has been sent.
        cleanup_case(case)
        return ConversationHandler.END

    except Exception:
        log.exception("Report generation failed for case %s", case.case_id)

        await q.message.reply_text(
            "❌ Report generation में error आया.\n"
            "आपका active case अभी रखा गया है। /delete से delete कर सकते हैं."
        )
        return REVIEW


async def cancel_case(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    q = update.callback_query
    await q.answer()

    case = ACTIVE_CASES.get(q.from_user.id)
    if case:
        cleanup_case(case)

    await q.message.reply_text(
        "🗑 Case cancelled. Temporary data हटाने की कोशिश की गई."
    )
    return ConversationHandler.END


# ========================= ERROR HANDLER =========================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):
    log.exception("Unhandled bot error", exc_info=context.error)


# ========================= APPLICATION =========================

def build_application() -> Application:
    if not BOT_TOKEN or BOT_TOKEN.startswith("PASTE_"):
        raise RuntimeError(
            "BOT_TOKEN is not configured. "
            "Set BOT_TOKEN environment variable."
        )

    app = Application.builder().token(BOT_TOKEN).build()

    conversation = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                start_report,
                pattern=r"^start_report$",
            )
        ],
        states={
            CONSENT: [
                CallbackQueryHandler(
                    consent_handler,
                    pattern=r"^consent_(yes|no)$",
                )
            ],
            LANGUAGE: [
                CallbackQueryHandler(
                    language_handler,
                    pattern=r"^lang_(hi|en)$",
                )
            ],
            AMOUNT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    amount_handler,
                )
            ],
            DATE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    date_handler,
                )
            ],
            PLATFORM: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    platform_handler,
                )
            ],
            DESCRIPTION: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    description_handler,
                )
            ],
            EVIDENCE: [
                MessageHandler(
                    filters.PHOTO | filters.Document.ALL,
                    evidence_handler,
                ),
                CallbackQueryHandler(
                    evidence_done,
                    pattern=r"^evidence_done$",
                ),
                CallbackQueryHandler(
                    cancel_case,
                    pattern=r"^cancel_case$",
                ),
            ],
            REVIEW: [
                CallbackQueryHandler(
                    generate_report,
                    pattern=r"^generate_report$",
                ),
                CallbackQueryHandler(
                    cancel_case,
                    pattern=r"^cancel_case$",
                ),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_command),
            CommandHandler("delete", delete_command),
        ],
        allow_reentry=True,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("privacy", privacy))
    app.add_handler(CommandHandler("delete", delete_command))
    app.add_handler(conversation)
    app.add_handler(
        CallbackQueryHandler(
            privacy_callback,
            pattern=r"^privacy$",
        )
    )
    app.add_error_handler(error_handler)

    return app


def main() -> None:
    log.info("Starting Cyber Fraud Report Assistant")
    application = build_application()
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
