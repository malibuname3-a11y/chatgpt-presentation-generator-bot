import os
import subprocess
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# 🔥 TOKEN
TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise Exception("❌ BOT_TOKEN topilmadi")

# 🔥 FFmpeg path (Windows)
FFMPEG = r"C:\ffmpeg\bin\ffmpeg.exe"

if not os.path.isfile(FFMPEG):
    raise Exception("❌ FFmpeg topilmadi")

os.makedirs("videos", exist_ok=True)

user_state = {}


# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📹 Video yuboring\n"
        "Keyin start end yozing (masalan: 5 12)\n"
        "Men o‘rtasini olib tashlayman"
    )


# video qabul qilish
async def video_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    input_path = f"videos/{user_id}_input.mp4"

    file = await context.bot.get_file(update.message.video.file_id)
    await file.download_to_drive(input_path)

    user_state[user_id] = input_path

    await update.message.reply_text("⏱ Start va end yozing (masalan: 5 12)")


# text handler
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    if user_id not in user_state:
        await update.message.reply_text("❌ Avval video yuboring")
        return

    try:
        start_time, end_time = map(float, text.split())
    except:
        await update.message.reply_text("❌ Format: 5 12")
        return

    input_path = user_state[user_id]
    output_path = f"videos/{user_id}_output.mp4"

    try:
        # 🔥 FAST FFmpeg (timeout yo‘q)
        cmd = [
            FFMPEG,
            "-y",
            "-i", input_path,

            "-filter_complex",
            "[0:v]trim=0:{0},setpts=PTS-STARTPTS[v1];"
            "[0:v]trim={1},setpts=PTS-STARTPTS[v2];"
            "[v1][v2]concat=n=2:v=1:a=0[v]".format(start_time, end_time),

            "-map", "[v]",
            "-map", "0:a?",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-c:a", "aac",

            output_path
        ]

        subprocess.run(cmd, check=True)

        await update.message.reply_video(
            video=open(output_path, "rb"),
            supports_streaming=True
        )

    except Exception as e:
        await update.message.reply_text("❌ Video error")
        print("ERROR:", e)


# app
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.VIDEO, video_handler))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

print("🤖 Bot ishlayapti...")

app.run_polling(drop_pending_updates=True)
