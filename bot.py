import os
import logging
import asyncio
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = os.environ.get("BOT_TOKEN") or "7857867174:AAEghTH8fqeItdfZSFbxy1JP9KytrMdS6mgc"

def upload_to_freeimage(img_bytes: bytes) -> str:
    """FreeImage.host ochiq API orqali yuklash (API key va blokirovkasiz)"""
    url = "https://freeimage.host/api/1/upload"
    payload = {
        'key': '6d207e02198a847aa98d0a2a901485a5',  # Ochiq public key
        'action': 'upload',
        'format': 'json'
    }
    files = {'source': ('image.jpg', img_bytes, 'image/jpeg')}
    
    response = requests.post(url, data=payload, files=files, timeout=20)
    data = response.json()
    
    if response.status_code == 200 and data.get("status_code") == 200:
        return data["image"]["url"]
    else:
        raise Exception(f"Yuklashda xatolik: {data}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Salom! Menga rasm yuboring, men uni URL havolaga o'girib beraman.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    
    photo = message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    img_bytes = await file.download_as_bytearray()
    
    status_msg = await message.reply_text("⏳ Rasm URL ga o'girilmoqda...")
    
    try:
        image_url = upload_to_freeimage(bytes(img_bytes))
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
    
    await asyncio.Event().wait()

def main():
    try:
        asyncio.run(run_bot())
    except (KeyboardInterrupt, SystemExit):
        pass

if __name__ == '__main__':
    main()
