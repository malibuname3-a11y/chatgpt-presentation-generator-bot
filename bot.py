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
    found = shutil.which("ffmpeg")
    if found:
        return found
    for path in ["/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg",
                 "/opt/homebrew/bin/ffmpeg", "/snap/bin/ffmpeg"]:
        if os.path.isfile(path):
            return path
    userprofile = os.environ.get("USERPROFILE", "")
    for path in [
        "C:\\ffmpeg\\bin\\ffmpeg.exe",
        os.path.join(userprofile, "ffmpeg", "bin", "ffmpeg.exe"),
    ]:
        if os.path.isfile(path):
            return path
    return None


# Conversation holatlari
WAITING_VIDEO      = 1
WAITING_MODE       = 2
WAITING_START_TIME = 3
WAITING_END_TIME   = 4

user_data_store = {}


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


def fmt(seconds):
    m, s = divmod(int(seconds), 60)
    return "%d:%02d" % (m, s)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Video Bot ga xush kelibsiz!\n\n"
        "Video yuboring, keyin rejim tanlaysiz."
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

        duration = getattr(video, "duration", None)
        user_data_store[user_id] = {
            "video_path": file_path,
            "duration": duration,
        }

        dur_text = ""
        if duration:
            dur_text = "\nVideo davomiyligi: %s" % fmt(duration)

        keyboard = [
            [InlineKeyboardButton("✂️ Qirqib olish", callback_data="mode_trim")],
            [InlineKeyboardButton("🗑 O'chirib tashlash", callback_data="mode_cut")],
        ]
        await message.reply_text(
            "Video yuklandi!%s\n\nQaysi rejimni tanlaysiz?\n\n"
            "✂️ Qirqib olish — belgilangan qismni oladi\n"
            "🗑 O'chirib tashlash — belgilangan qismni olib, qolganini yuboradi" % dur_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return WAITING_MODE

    except Exception as e:
        logger.error("Video yuklashda xato: %s", e)
        await message.reply_text("Xato yuz berdi. Qayta urinib ko'ring.")
        return WAITING_VIDEO


async def mode_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    mode = query.data  # "mode_trim" yoki "mode_cut"
    user_data_store[user_id]["mode"] = mode

    if mode == "mode_trim":
        await query.message.reply_text(
            "✂️ Qirqib olish rejimi\n\n"
            "Boshlanish vaqtini kiriting:\n"
            "Misol: 30  yoki  1:30  yoki  0:01:30"
        )
    else:
        await query.message.reply_text(
            "🗑 O'chirib tashlash rejimi\n\n"
            "O'chiriladigan qismning BOSHLANISH vaqtini kiriting:\n"
            "Misol: 30  yoki  1:30  yoki  0:01:30"
        )
    return WAITING_START_TIME


async def receive_start_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    start_time = parse_time(text)

    if start_time is None or start_time < 0:
        await update.message.reply_text("Noto'g'ri vaqt! Misol: 30 yoki 1:30")
        return WAITING_START_TIME

    data = user_data_store.get(user_id, {})
    duration = data.get("duration")
    if duration and start_time >= duration:
        await update.message.reply_text(
            "Vaqt video davomiyligidan (%s) katta! Qayta kiriting." % fmt(duration)
        )
        return WAITING_START_TIME

    user_data_store[user_id]["start_time"] = start_time

    mode = data.get("mode")
    if mode == "mode_trim":
        await update.message.reply_text(
            "Boshlanish: %s\n\nTugash vaqtini kiriting:" % fmt(start_time)
        )
    else:
        await update.message.reply_text(
            "O'chirish boshlanishi: %s\n\nO'chirish TUGASH vaqtini kiriting:" % fmt(start_time)
        )
    return WAITING_END_TIME


async def receive_end_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    end_time = parse_time(text)
    data = user_data_store.get(user_id, {})
    start_time = data.get("start_time", 0)
    duration = data.get("duration")
    mode = data.get("mode")

    if end_time is None or end_time <= 0:
        await update.message.reply_text("Noto'g'ri vaqt! Misol: 90 yoki 1:30")
        return WAITING_END_TIME

    if end_time <= start_time:
        await update.message.reply_text("Tugash vaqti boshlanishdan katta bo'lishi kerak!")
        return WAITING_END_TIME

    if duration and end_time > duration:
        end_time = duration

    await update.message.reply_text("Ishlanmoqda, iltimos kuting...")

    input_path = data.get("video_path")
    output_path = "downloads/%s_output.mp4" % user_id

    try:
        ffmpeg = find_ffmpeg()
        if not ffmpeg:
            await update.message.reply_text("FFmpeg topilmadi! Server xatosi.")
            return ConversationHandler.END

        if mode == "mode_trim":
            # Qirqib olish — faqat start..end orasini oladi
            cmd = [
                ffmpeg,
                "-i", input_path,
                "-ss", str(start_time),
                "-to", str(end_time),
                "-c:v", "libx264", "-c:a", "aac",
                "-preset", "fast", "-crf", "23", "-y",
                output_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                logger.error("FFmpeg xato: %s", result.stderr)
                raise Exception("trim failed")

            caption = "%s --> %s qismi olindi." % (fmt(start_time), fmt(end_time))

        else:
            # O'chirib tashlash — start..end orasini o'chirib, ikki qismni birlashtiradi
            part1_path = "downloads/%s_part1.mp4" % user_id
            part2_path = "downloads/%s_part2.mp4" % user_id
            list_path  = "downloads/%s_list.txt" % user_id

            has_part1 = start_time > 0
            has_part2 = (duration is None) or (end_time < duration)

            if has_part1:
                r1 = subprocess.run([
                    ffmpeg, "-i", input_path,
                    "-ss", "0", "-to", str(start_time),
                    "-c:v", "libx264", "-c:a", "aac",
                    "-preset", "fast", "-crf", "23", "-y", part1_path
                ], capture_output=True, text=True, timeout=300)
                if r1.returncode != 0:
                    raise Exception("part1 failed")

            if has_part2:
                r2 = subprocess.run([
                    ffmpeg, "-i", input_path,
                    "-ss", str(end_time),
                    "-c:v", "libx264", "-c:a", "aac",
                    "-preset", "fast", "-crf", "23", "-y", part2_path
                ], capture_output=True, text=True, timeout=300)
                if r2.returncode != 0:
                    raise Exception("part2 failed")

            if has_part1 and has_part2:
                with open(list_path, "w") as f:
                    f.write("file '%s'\n" % os.path.abspath(part1_path))
                    f.write("file '%s'\n" % os.path.abspath(part2_path))
                r3 = subprocess.run([
                    ffmpeg, "-f", "concat", "-safe", "0",
                    "-i", list_path, "-c", "copy", "-y", output_path
                ], capture_output=True, text=True, timeout=300)
                if r3.returncode != 0:
                    raise Exception("concat failed")
            elif has_part1:
                os.rename(part1_path, output_path)
            elif has_part2:
                os.rename(part2_path, output_path)
            else:
                await update.message.reply_text("Butun video o'chirildi, yuboradigan narsa qolmadi!")
                return ConversationHandler.END

            # Temp fayllarni tozalash
            for p in [part1_path, part2_path, list_path]:
                if os.path.exists(p):
                    os.remove(p)

            caption = "%s - %s oraligi o'chirildi." % (fmt(start_time), fmt(end_time))

        # Natijani yuborish
        file_size = os.path.getsize(output_path)
        if file_size > 50 * 1024 * 1024:
            await update.message.reply_text("Natija 50MB dan katta, Telegram qabul qilmaydi.")
        else:
            with open(output_path, "rb") as vf:
                await update.message.reply_video(
                    video=vf,
                    caption=caption,
                    supports_streaming=True
                )

    except subprocess.TimeoutExpired:
        await update.message.reply_text("Vaqt tugadi (5 daqiqa). Qisqaroq video yuboring.")
    except Exception as e:
        logger.error("Xato: %s", e)
        await update.message.reply_text("Xato yuz berdi. Qayta urinib ko'ring.")
    finally:
        for path in [input_path, output_path]:
            if path and os.path.exists(path):
                os.remove(path)
        user_data_store.pop(user_id, None)

    keyboard = [[InlineKeyboardButton("Yangi video", callback_data="new_video")]]
    await update.message.reply_text("Yana ishlashni xohlaysizmi?", reply_markup=InlineKeyboardMarkup(keyboard))
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
            WAITING_MODE: [
                CallbackQueryHandler(mode_callback, pattern="^mode_"),
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

    ffmpeg = find_ffmpeg()
    logger.info("FFmpeg: %s", ffmpeg or "TOPILMADI")
    print("Bot ishga tushdi!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
