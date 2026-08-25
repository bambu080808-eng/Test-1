import os
import logging
import asyncio
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# Loglarni sozlash
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Token
TOKEN = os.environ.get("BOT_TOKEN") or "7857867174:AAEghTH8fqeItdfZSFbxy1JP9KytrMdS6mgc"

def upload_to_catbox(img_bytes: bytes) -> str:
    url = "https://catbox.moe/user/api.php"
    payload = {'reqtype': 'fileupload'}
    files = {'fileToUpload': ('image.jpg', img_bytes, 'image/jpeg')}
    
    response = requests.post(url, data=payload, files=files, timeout=20)
    if response.status_code == 200 and response.text.startswith("http"):
        return response.text.strip()
    else:
        raise Exception(f"Catbox xatoligi: {response.text}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Salom! Menga rasm yuboring, men uni URL havolaga o'girib beraman.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    
    photo = message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    img_bytes = await file.download_as_bytearray()
    
    status_msg = await message.reply_text("⏳ Rasm URL ga o'girilmoqda...")
    
    try:
        image_url = upload_to_catbox(bytes(img_bytes))
        await status_msg.edit_text(f"✅ Tayyor! Rasm havolasi:\n\n{image_url}")
    except Exception as e:
        await status_msg.edit_text(f"❌ Xatolik yuz berdi: {str(e)}")

async def run_bot():
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    # Bot to'xtovsiz ishlashi uchun cheksiz kutish
    await asyncio.Event().wait()

def main():
    try:
        asyncio.run(run_bot())
    except (KeyboardInterrupt, SystemExit):
        pass

if __name__ == '__main__':
    main()
