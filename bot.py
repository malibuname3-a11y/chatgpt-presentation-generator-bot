import os
import subprocess
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters,
)

# 🔥 TOKEN avtomatik env dan olinadi
TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise Exception("❌ BOT_TOKEN topilmadi! Environment variables ga qo‘shing.")

os.makedirs("videos", exist_ok=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📹 Video yuboring ")

async def video_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video = update.message.video

    file = await context.bot.get_file(video.file_id)

    input_path = "videos/input.mp4"
    output_path = "videos/output.mp4"

    await file.download_to_drive(input_path)

    # 6–8 sekundni olib tashlash
    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-filter_complex",
        "[0:v]trim=0:6,setpts=PTS-STARTPTS[v1];"
        "[0:v]trim=8,setpts=PTS-STARTPTS[v2];"
        "[v1][v2]concat=n=2:v=1:a=0[v]",
        "-map", "[v]",
        "-an",
        output_path
    ]

    subprocess.run(cmd)

    await update.message.reply_video(video=open(output_path, "rb"))

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.VIDEO, video_handler))

print("Bot ishlayapti...")

app.run_polling(drop_pending_updates=True)
