import os
import logging
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# Loglarni sozlash
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Tokenni muhit o'zgaruvchisidan olish
TOKEN = os.environ.get("BOT_TOKEN")

def upload_to_catbox(img_bytes: bytes) -> str:
    """Rasmni Catbox'ga yuklab URL qaytaradi"""
    url = "https://catbox.moe/user/api.php"
    payload = {'reqtype': 'fileupload'}
    files = {'fileToUpload': ('image.jpg', img_bytes, 'image/jpeg')}
    
    response = requests.post(url, data=payload, files=files, timeout=20)
    if response.status_code == 200 and response.text.startswith("http"):
        return response.text.strip()
    else:
        raise Exception(f"Catbox xatoligi: {response.text}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Salom! Menga istalgan rasmni yuboring, men uni Catbox orqali URL havolaga o'girib beraman.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    
    # Rasmni yuklab olish
    photo = message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    img_bytes = await file.download_as_bytearray()
    
    status_msg = await message.reply_text("⏳ Rasm URL ga o'girilmoqda...")
    
    try:
        image_url = upload_to_catbox(bytes(img_bytes))
        await status_msg.edit_text(f"✅ Tayyor! Rasm havolasi:\n\n{image_url}")
    except Exception as e:
        await status_msg.edit_text(f"❌ Xatolik yuz berdi: {str(e)}")

def main():
    if not TOKEN:
        print("DIQQAT: BOT_TOKEN topilmadi!")
        return

    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    print("Oddiy Rasm-URL boti ishga tushdi...")
    application.run_polling()

if __name__ == '__main__':
    main()
