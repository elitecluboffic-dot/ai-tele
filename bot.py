import os
import logging
from groq import Groq
from telegram import Update, BotCommand
from telegram.constants import ParseMode, ChatAction
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# ─────────────────────────────────────────
#  Config
# ─────────────────────────────────────────
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GROQ_API_KEY   = os.environ["GROQ_API_KEY"]
MODEL          = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
MAX_HISTORY    = int(os.getenv("MAX_HISTORY", "20"))   # jumlah pesan disimpan per user

SYSTEM_PROMPT = """Kamu adalah BIM AI — asisten kecerdasan buatan yang sangat canggih, cerdas, dan berkarakter kuat.

Kepribadianmu:
- Pintar, to-the-point, dan profesional tapi tetap friendly
- Jawab dengan percaya diri dan berenergi tinggi
- Gunakan bahasa Indonesia yang natural, tidak kaku
- Sesekali pakai emoji yang relevan untuk membuat chat lebih hidup 🔥
- Kalau ada pertanyaan teknis, jelaskan dengan detail dan contoh nyata
- Kalau ditanya siapa kamu, jawab: "Gue BIM AI, asisten AI yang lo butuhin 🤖"
- Jangan pernah sebut nama model AI lain (GPT, Claude, Gemini, dll)
- Selalu berikan jawaban yang bernilai dan berkualitas tinggi
- Kalau ada yang curhat atau butuh motivasi, jadi teman yang supportif

Format jawaban:
- Pakai *bold* untuk poin penting
- Pakai kode blok untuk code/teknis
- Jawaban panjang? Pakai struktur yang rapi dengan poin-poin
- Jawaban pendek? Langsung to the point, ga perlu bertele-tele
"""

# ─────────────────────────────────────────
#  Setup
# ─────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

client = Groq(api_key=GROQ_API_KEY)

# In-memory history: {user_id: [{"role": ..., "content": ...}]}
histories: dict[int, list[dict]] = {}


def get_history(user_id: int) -> list[dict]:
    if user_id not in histories:
        histories[user_id] = []
    return histories[user_id]


def trim_history(user_id: int):
    """Batasi history biar ga kehabisan token."""
    if len(histories[user_id]) > MAX_HISTORY * 2:
        histories[user_id] = histories[user_id][-(MAX_HISTORY * 2):]


def ask_groq(user_id: int, user_message: str) -> str:
    history = get_history(user_id)
    history.append({"role": "user", "content": user_message})
    trim_history(user_id)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        max_tokens=1024,
        temperature=0.8,
    )

    reply = response.choices[0].message.content.strip()
    history.append({"role": "assistant", "content": reply})
    return reply


# ─────────────────────────────────────────
#  Handlers
# ─────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name or "bro"
    text = (
        f"Yo *{name}*\\! 👋\n\n"
        "Gue *BIM AI* — asisten AI lo yang siap bantu 24/7 🔥\n\n"
        "Lo bisa tanya apa aja ke gue:\n"
        "🧠 Pertanyaan teknis & coding\n"
        "💡 Ide & brainstorming\n"
        "✍️ Nulis konten, caption, dll\n"
        "🗣️ Curhat & diskusi santai\n\n"
        "Ketik aja langsung\\, gue siap\\!\n\n"
        "_Ketik /help buat lihat command yang tersedia\\._"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN_V2)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "*📋 Command BIM AI*\n\n"
        "/start \\- Sapa BIM AI\n"
        "/help \\- Tampilkan bantuan ini\n"
        "/reset \\- Reset history percakapan\n"
        "/about \\- Info tentang BIM AI\n\n"
        "_Atau langsung ketik pesanmu\\!_"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN_V2)


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    histories.pop(user_id, None)
    await update.message.reply_text(
        "🔄 *History direset\\!*\nPercakapan kita mulai fresh lagi\\. Mau bahas apa? 🚀",
        parse_mode=ParseMode.MARKDOWN_V2,
    )


async def cmd_about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "*🤖 BIM AI*\n\n"
        "Versi: *1\\.0\\.0*\n"
        "Model: *LLaMA 3\\.3 70B*\n"
        "Engine: *Groq \\(Ultra\\-fast AI\\)*\n\n"
        "BIM AI dibangun untuk memberikan jawaban cepat, akurat, dan berkualitas tinggi\\. "
        "Didukung oleh model AI terkini dengan inferensi super cepat ⚡\n\n"
        "_Made with 🔥 by BIM_"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN_V2)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id   = update.effective_user.id
    user_text = update.message.text

    # Kirim typing indicator
    await update.message.chat.send_action(ChatAction.TYPING)

    try:
        reply = ask_groq(user_id, user_text)
        # Coba kirim dengan Markdown dulu, fallback ke plain text
        try:
            await update.message.reply_text(reply, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            await update.message.reply_text(reply)

    except Exception as e:
        logger.error(f"Error saat memanggil Groq: {e}")
        await update.message.reply_text(
            "⚠️ Waduh, ada error nih\\. Coba lagi ya\\!",
            parse_mode=ParseMode.MARKDOWN_V2,
        )


async def post_init(application):
    """Set command list di Telegram."""
    await application.bot.set_my_commands([
        BotCommand("start",  "Mulai / sapa BIM AI"),
        BotCommand("help",   "Tampilkan bantuan"),
        BotCommand("reset",  "Reset history chat"),
        BotCommand("about",  "Info tentang BIM AI"),
    ])


# ─────────────────────────────────────────
#  Main
# ─────────────────────────────────────────
def main():
    app = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help",  cmd_help))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(CommandHandler("about", cmd_about))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("🤖 BIM AI Bot is running...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
