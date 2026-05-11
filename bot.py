import os
import sys
import shutil
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

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = (
    os.environ.get("BOT_TOKEN") or
    os.environ.get("TELEGRAM_BOT_TOKEN")
)

if not BOT_TOKEN:
    logger.error("Token topilmadi! BOT_TOKEN environment variable o'rnating.")
    sys.exit(1)

logger.info("Token topildi.")


def find_ffmpeg():
    # 1. imageio-ffmpeg (Railway/server uchun, o'zi yuklab oladi)
    try:
        import imageio_ffmpeg
        path = imageio_ffmpeg.get_ffmpeg_exe()
        if path and os.path.isfile(path):
            return path
    except ImportError:
        pass

    # 2. PATH
    found = shutil.which("ffmpeg")
    if found:
        return found

    # 3. Linux/Mac
    for path in ["/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg",
                 "/opt/homebrew/bin/ffmpeg", "/snap/bin/ffmpeg"]:
        if os.path.isfile(path):
            return path

    # 4. Windows
    userprofile = os.environ.get("USERPROFILE", "")
    for path in [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        os.path.join(userprofile, "ffmpeg", "bin", "ffmpeg.exe"),
    ]:
        if os.path.isfile(path):
            return path

    return None


FFMPEG_PATH = find_ffmpeg()
if not FFMPEG_PATH:
    logger.error(
        "FFmpeg topilmadi! "
        "Railway uchun: requirements.txt ga 'imageio-ffmpeg' qo'shing. "
        "Ubuntu: sudo apt install ffmpeg"
    )
    sys.exit(1)

logger.info("FFmpeg topildi: %s", FFMPEG_PATH)

WAITING_VIDEO = 1
WAITING_START_TIME = 2
WAITING_END_TIME = 3

user_data_store = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Video Trim Bot ga xush kelibsiz!\n\n"
        "1. Video yuboring\n"
        "2. Boshlanish vaqtini kiriting (masalan: 0:30 yoki 30)\n"
        "3. Tugash vaqtini kiriting (masalan: 1:30 yoki 90)\n"
        "4. Qirqilgan videoni oling!\n\n"
        "Video yuborishni boshlang."
    )
    return WAITING_VIDEO


async def receive_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    user_id = update.effective_user.id
    video = message.video or message.document

    if not video:
        await message.reply_text("Iltimos, video yuboring!")
        return WAITING_VIDEO

    if video.file_size > 50 * 1024 * 1024:
        await message.reply_text("Video hajmi 50MB dan katta! Kichikroq video yuboring.")
        return WAITING_VIDEO

    await message.reply_text("Video yuklanmoqda...")

    try:
        file = await context.bot.get_file(video.file_id)
        os.makedirs("downloads", exist_ok=True)
        file_path = "downloads/%s_input.mp4" % user_id
        await file.download_to_drive(file_path)

        user_data_store[user_id] = {
            "video_path": file_path,
            "duration": getattr(video, "duration", None),
        }

        duration_text = ""
        if getattr(video, "duration", None):
            m, s = divmod(video.duration, 60)
            duration_text = "\nVideo davomiyligi: %d:%02d" % (m, s)

        await message.reply_text(
            "Video yuklandi!%s\n\n"
            "Boshlanish vaqtini kiriting:\n"
            "Formatlar: 30  yoki  1:30  yoki  0:01:30" % duration_text
        )
        return WAITING_START_TIME

    except Exception as e:
        logger.error("Video yuklashda xato: %s", e)
        await message.reply_text("Video yuklashda xato yuz berdi. Qayta urinib ko'ring.")
        return WAITING_VIDEO


def parse_time(time_str):
    try:
        parts = time_str.strip().split(":")
        if len(parts) == 1:
            return float(parts[0])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    except (ValueError, IndexError):
        pass
    return None


async def receive_start_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    start_time = parse_time(text)

    if start_time is None or start_time < 0:
        await update.message.reply_text("Noto'g'ri vaqt! Misol: 30 yoki 1:30")
        return WAITING_START_TIME

    user_data_store[user_id]["start_time"] = start_time
    await update.message.reply_text(
        "Boshlanish vaqti: %s\n\nTugash vaqtini kiriting:" % text
    )
    return WAITING_END_TIME


async def receive_end_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    end_time = parse_time(text)
    data = user_data_store.get(user_id, {})
    start_time = data.get("start_time", 0)

    if end_time is None or end_time <= 0:
        await update.message.reply_text("Noto'g'ri vaqt! Misol: 90 yoki 1:30")
        return WAITING_END_TIME

    if end_time <= start_time:
        await update.message.reply_text("Tugash vaqti boshlanish vaqtidan katta bo'lishi kerak!")
        return WAITING_END_TIME

    duration = end_time - start_time
    await update.message.reply_text("Video qirqilmoqda, iltimos kuting...")

    input_path = data.get("video_path")
    output_path = "downloads/%s_output.mp4" % user_id

    try:
        cmd = [
            FFMPEG_PATH,          # <-- avtomatik topilgan yo'l
            "-i", input_path,
            "-ss", str(start_time),
            "-to", str(end_time),
            "-c:v", "libx264",
            "-c:a", "aac",
            "-preset", "fast",
            "-crf", "23",
            "-y",
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode != 0:
            logger.error("FFmpeg xatosi: %s", result.stderr)
            await update.message.reply_text("Video qirqishda xato! Qayta urinib ko'ring.")
            return ConversationHandler.END

        file_size = os.path.getsize(output_path)
        if file_size > 50 * 1024 * 1024:
            await update.message.reply_text("Qirqilgan video 50MB dan katta. Qisqaroq vaqt tanlang.")
        else:
            start_fmt = "%d:%02d" % (int(start_time // 60), int(start_time % 60))
            end_fmt = "%d:%02d" % (int(end_time // 60), int(end_time % 60))
            with open(output_path, "rb") as vf:
                await update.message.reply_video(
                    video=vf,
                    caption="Video qirqildi! %s --> %s (%d soniya)" % (start_fmt, end_fmt, duration),
                    supports_streaming=True
                )

    except subprocess.TimeoutExpired:
        await update.message.reply_text("Vaqt tugadi (5 daqiqa). Qisqaroq vaqt tanlang.")
    except Exception as e:
        logger.error("Xato: %s", e)
        await update.message.reply_text("Kutilmagan xato yuz berdi.")
    finally:
        for path in [input_path, output_path]:
            if path and os.path.exists(path):
                os.remove(path)
        user_data_store.pop(user_id, None)

    keyboard = [[InlineKeyboardButton("Yangi video qirqish", callback_data="new_video")]]
    await update.message.reply_text("Yana video qirqmoqchimisiz?", reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END


async def new_video_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Yangi video yuboring:")
    return WAITING_VIDEO


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = user_data_store.pop(user_id, {})
    if "video_path" in data and os.path.exists(data["video_path"]):
        os.remove(data["video_path"])
    await update.message.reply_text("Bekor qilindi. /start - qaytadan boshlash")
    return ConversationHandler.END


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Xato:", exc_info=context.error)


def main():
    app = Application.builder().token(BOT_TOKEN).build()

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

    print("Bot ishga tushdi! FFmpeg: %s" % FFMPEG_PATH)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
