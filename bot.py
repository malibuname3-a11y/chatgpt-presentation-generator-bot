import os
from moviepy.video.io.VideoFileClip import VideoFileClip
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise Exception("❌ BOT_TOKEN topilmadi")

os.makedirs("videos", exist_ok=True)

# user state (start/end saqlash uchun)
user_state = {}


# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📹 Video yuboring\n"
        "Keyin start va end vaqtni yuborasiz (masalan: 5 12)"
    )


# video handler
async def video_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    video = update.message.video

    input_path = f"videos/{user_id}_input.mp4"

    file = await context.bot.get_file(video.file_id)
    await file.download_to_drive(input_path)

    user_state[user_id] = {"path": input_path}

    await update.message.reply_text(
        "⏱ Endi start va end yozing\n"
        "Masalan: 5 12"
    )


# text handler (start/end olish)
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    if user_id not in user_state:
        await update.message.reply_text("Avval video yuboring 📹")
        return

    try:
        start_time, end_time = map(float, text.split())
    except:
        await update.message.reply_text("Format: start end (masalan: 5 12)")
        return

    path = user_state[user_id]["path"]
    output_path = f"videos/{user_id}_output.mp4"

    try:
        clip = VideoFileClip(path)

        # xatolikdan himoya
        if start_time < 0:
            start_time = 0
        if end_time > clip.duration:
            end_time = clip.duration
        if start_time >= end_time:
            await update.message.reply_text("❌ noto‘g‘ri vaqt")
            return

        # 🎬 kesish
        part1 = clip.subclip(0, start_time)
        part2 = clip.subclip(end_time, clip.duration)

        final_clip = part1.concatenate_videoclips([part2])

        final_clip.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            verbose=False,
            logger=None
        )

        await update.message.reply_video(
            video=open(output_path, "rb"),
            supports_streaming=True
        )

    except Exception as e:
        await update.message.reply_text("❌ Xatolik yuz berdi")
        print(e)


# bot app
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.VIDEO, video_handler))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

print("🤖 Bot ishlayapti...")

app.run_polling(drop_pending_updates=True)
