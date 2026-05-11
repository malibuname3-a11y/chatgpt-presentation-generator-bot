import os
import sys
import logging
import subprocess
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# .env faylini yuklash (agar python-dotenv o'rnatilgan bo'lsa)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv yo'q bo'lsa, faqat environment variable ishlatiladi

# Logging sozlash
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Token qidiruv tartibi:
# 1. BOT_TOKEN environment variable
# 2. TELEGRAM_BOT_TOKEN environment variable
# 3. .env fayli (yuqorida load_dotenv orqali)
BOT_TOKEN = (
    os.environ.get("BOT_TOKEN") or
    os.environ.get("TELEGRAM_BOT_TOKEN")
)

if not BOT_TOKEN:
    logger.error(
        "Token topilmadi!\n"
        "Quyidagilardan birini qiling:\n"
        "  1) .env fayl yarating: BOT_TOKEN=your_token\n"
        "  2) Environment variable qo'ying: export BOT_TOKEN=your_token\n"
        "  3) Ishga tushirishda bering: BOT_TOKEN=your_token python video_trim_bot.py"
    )
    sys.exit(1)

logger.info("✅ Token muvaffaqiyatli topildi.")

# Conversation holatlari
WAITING_VIDEO = 1
WAITING_START_TIME = 2
WAITING_END_TIME = 3

# Foydalanuvchi ma'lumotlarini saqlash
user_data_store = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Botni boshlash"""
    await update.message.reply_text(
        "🎬 *Video Trim Bot*ga xush kelibsiz!\n\n"
        "Bu bot sizga video qismini qirqib olishga yordam beradi.\n\n"
        "📌 *Qanday ishlaydi:*\n"
        "1. Video yuboring\n"
        "2. Boshlanish vaqtini kiriting (masalan: `0:30` yoki `30`)\n"
        "3. Tugash vaqtini kiriting (masalan: `1:30` yoki `90`)\n"
        "4. Qirqilgan videoni oling!\n\n"
        "Video yuborishni boshlang 👇",
        parse_mode="Markdown"
    )
    return WAITING_VIDEO


async def receive_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Videoni qabul qilish"""
    message = update.message
    user_id = update.effective_user.id

    # Video yoki document sifatida yuborilgan bo'lishi mumkin
    video = message.video or message.document

    if not video:
        await message.reply_text("❌ Iltimos, video yuboring!")
        return WAITING_VIDEO

    # Fayl hajmini tekshirish (50MB limit)
    if video.file_size > 50 * 1024 * 1024:
        await message.reply_text(
            "❌ Video hajmi 50MB dan katta!\n"
            "Iltimos, kichikroq video yuboring."
        )
        return WAITING_VIDEO

    await message.reply_text("⏳ Video yuklanmoqda...")

    try:
        # Videoni yuklab olish
        file = await context.bot.get_file(video.file_id)
        os.makedirs("downloads", exist_ok=True)
        file_path = f"downloads/{user_id}_input.mp4"
        await file.download_to_drive(file_path)

        # Foydalanuvchi ma'lumotlarini saqlash
        user_data_store[user_id] = {
            "video_path": file_path,
            "duration": video.duration if hasattr(video, 'duration') else None
        }

        duration_text = ""
        if hasattr(video, 'duration') and video.duration:
            minutes = video.duration // 60
            seconds = video.duration % 60
            duration_text = f"\n📏 *Video davomiyligi:* {minutes}:{seconds:02d}"

        await message.reply_text(
            f"✅ Video yuklandi!{duration_text}\n\n"
            "⏱ *Boshlanish vaqtini kiriting:*\n"
            "Formatlar:\n"
            "• Soniyalar: `30`\n"
            "• Daqiqa:Soniya: `1:30`\n"
            "• Soat:Daqiqa:Soniya: `0:01:30`",
            parse_mode="Markdown"
        )
        return WAITING_START_TIME

    except Exception as e:
        logger.error(f"Video yuklashda xato: {e}")
        await message.reply_text("❌ Video yuklashda xato yuz berdi. Qayta urinib ko'ring.")
        return WAITING_VIDEO


def parse_time(time_str: str) -> float | None:
    """Vaqt satrini soniyalarga aylantirish"""
    try:
        time_str = time_str.strip()
        parts = time_str.split(":")

        if len(parts) == 1:
            return float(parts[0])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        else:
            return None
    except (ValueError, IndexError):
        return None


async def receive_start_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Boshlanish vaqtini qabul qilish"""
    user_id = update.effective_user.id
    text = update.message.text

    start_time = parse_time(text)

    if start_time is None or start_time < 0:
        await update.message.reply_text(
            "❌ Noto'g'ri vaqt formati!\n"
            "Misol: `30` yoki `1:30` yoki `0:01:30`",
            parse_mode="Markdown"
        )
        return WAITING_START_TIME

    user_data_store[user_id]["start_time"] = start_time

    await update.message.reply_text(
        f"✅ Boshlanish vaqti: *{text}*\n\n"
        "⏱ *Tugash vaqtini kiriting:*\n"
        "Formatlar:\n"
        "• Soniyalar: `90`\n"
        "• Daqiqa:Soniya: `1:30`\n"
        "• Soat:Daqiqa:Soniya: `0:01:30`",
        parse_mode="Markdown"
    )
    return WAITING_END_TIME


async def receive_end_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tugash vaqtini qabul qilish va videoni qirqish"""
    user_id = update.effective_user.id
    text = update.message.text

    end_time = parse_time(text)
    data = user_data_store.get(user_id, {})
    start_time = data.get("start_time", 0)

    if end_time is None or end_time <= 0:
        await update.message.reply_text(
            "❌ Noto'g'ri vaqt formati!\n"
            "Misol: `90` yoki `1:30`",
            parse_mode="Markdown"
        )
        return WAITING_END_TIME

    if end_time <= start_time:
        await update.message.reply_text(
            "❌ Tugash vaqti boshlanish vaqtidan katta bo'lishi kerak!"
        )
        return WAITING_END_TIME

    duration = end_time - start_time
    if duration > 600:  # 10 daqiqadan oshsa
        await update.message.reply_text(
            "⚠️ Qirqiladigan qism 10 daqiqadan ko'p.\n"
            "Bu biroz vaqt olishi mumkin..."
        )

    await update.message.reply_text("✂️ Video qirqilmoqda, iltimos kuting...")

    input_path = data.get("video_path")
    output_path = f"downloads/{user_id}_output.mp4"

    try:
        # FFmpeg bilan videoni qirqish
        cmd = [
            "ffmpeg",
            "-i", input_path,
            "-ss", str(start_time),
            "-to", str(end_time),
            "-c:v", "libx264",      # Video codec
            "-c:a", "aac",          # Audio codec
            "-preset", "fast",      # Tezlik
            "-crf", "23",           # Sifat (18-28, past = yaxshi)
            "-y",                   # Ustiga yozish
            output_path
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 daqiqa timeout
        )

        if result.returncode != 0:
            logger.error(f"FFmpeg xatosi: {result.stderr}")
            await update.message.reply_text(
                "❌ Video qirqishda xato yuz berdi!\n"
                "Iltimos, qayta urinib ko'ring."
            )
            return ConversationHandler.END

        # Natija faylini yuborish
        file_size = os.path.getsize(output_path)
        if file_size > 50 * 1024 * 1024:
            await update.message.reply_text(
                "❌ Qirqilgan video 50MB dan katta, Telegram yuborishga ruxsat bermaydi.\n"
                "Qisqaroq vaqt oralig'ini tanlang."
            )
        else:
            start_fmt = f"{int(start_time//60)}:{int(start_time%60):02d}"
            end_fmt = f"{int(end_time//60)}:{int(end_time%60):02d}"

            with open(output_path, "rb") as video_file:
                await update.message.reply_video(
                    video=video_file,
                    caption=(
                        f"✅ *Video muvaffaqiyatli qirqildi!*\n"
                        f"⏱ {start_fmt} → {end_fmt} ({duration:.0f} soniya)"
                    ),
                    parse_mode="Markdown",
                    supports_streaming=True
                )

    except subprocess.TimeoutExpired:
        await update.message.reply_text(
            "❌ Video qirqish vaqti tugadi (5 daqiqa).\n"
            "Qisqaroq video yoki vaqt oralig'ini tanlang."
        )
    except Exception as e:
        logger.error(f"Xato: {e}")
        await update.message.reply_text("❌ Kutilmagan xato yuz berdi.")
    finally:
        # Vaqtinchalik fayllarni o'chirish
        for path in [input_path, output_path]:
            if path and os.path.exists(path):
                os.remove(path)
        user_data_store.pop(user_id, None)

    # Yangi video uchun taklif
    keyboard = [[InlineKeyboardButton("🎬 Yangi video qirqish", callback_data="new_video")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Yana video qirqmoqchimisiz?",
        reply_markup=reply_markup
    )
    return ConversationHandler.END


async def new_video_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Yangi video boshlash"""
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "🎬 Yangi video yuboring:",
    )
    return WAITING_VIDEO


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bekor qilish"""
    user_id = update.effective_user.id

    # Fayllarni tozalash
    data = user_data_store.pop(user_id, {})
    if "video_path" in data and os.path.exists(data["video_path"]):
        os.remove(data["video_path"])

    await update.message.reply_text(
        "❌ Bekor qilindi.\n"
        "/start - qaytadan boshlash"
    )
    return ConversationHandler.END


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Xatolarni qayta ishlash"""
    logger.error("Xato:", exc_info=context.error)


def main():
    """Botni ishga tushirish"""
    app = Application.builder().token(BOT_TOKEN).build()

    # Conversation handler
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.VIDEO | filters.Document.VIDEO, receive_video),
        ],
        states={
            WAITING_VIDEO: [
                MessageHandler(filters.VIDEO | filters.Document.VIDEO, receive_video),
            ],
            WAITING_START_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_start_time),
            ],
            WAITING_END_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_end_time),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", start),
        ],
    )

    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(new_video_callback, pattern="^new_video$"))
    app.add_error_handler(error_handler)

    print("🤖 Bot ishga tushdi!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
