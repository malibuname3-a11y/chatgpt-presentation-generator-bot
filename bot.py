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

# 🔥 TOKEN (environment variables dan)
TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise Exception("❌ BOT_TOKEN topilmadi!")

# 🔥 WINDOWS FFmpeg PATH (SENDA BOR)
FFMPEG = r"C:\ffmpeg\bin\ffmpeg.exe"

# tekshirish
if not os.path.exists(FFMPEG):
    raise Exception("❌ FFmpeg topilmadi: C:\\ffmpeg\\bin\\ffmpeg.exe")

# folder
os.makedirs("videos", exist_ok=True)


# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📹 Video yuboring\n"
        
    )


# video handler
async def video_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video = update.message.video

    input_path = "videos/input.mp4"
    output_path = "videos/output.mp4"

    file = await context.bot.get_file(video.file_id)
    await file.download_to_drive(input_path)

    # 🎬 6–8 sekundni olib tashlash
    cmd = [
        FFMPEG,
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

    try:
        subprocess.run(cmd, check=True)

        await update.message.reply_video(
            video=open(output_path, "rb"),
            supports_streaming=True
        )

    except Exception as e:
        await update.message.reply_text("❌ Video processing xatolik")
        print(e)


# app
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.VIDEO, video_handler))

print("🤖 Bot ishlayapti...")

app.run_polling(drop_pending_updates=True)
