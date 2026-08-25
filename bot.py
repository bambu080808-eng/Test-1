import os
import io
import logging
import asyncio
from PIL import Image
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from google import genai

# Loglarni sozlash
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Tokenlar
TELEGRAM_TOKEN = os.environ.get("BOT_TOKEN") or "7857867174:AAEghTH8fqeItdfZSFbxy1JP9KytrMdS6mgc"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or "SIZNING_GEMINI_API_KALITINGIZ"

# Gemini clientini yaratish
client = genai.Client(api_key=GEMINI_API_KEY)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Salom! Menga mahsulot rasmini yuboring, men uning nomini aniqlab beraman.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    
    # Telegram'dan rasmni yuklab olish
    photo = message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    img_bytes = await file.download_as_bytearray()
    
    status_msg = await message.reply_text("🔍 Gemini rasm tahlil qilmoqda...")
    
    try:
        # Byte formatdagi rasmni PIL Image obyektiga o'tkazish
        image = Image.open(io.BytesIO(img_bytes))
        
        # Gemini 2.5 Flash modeliga so'rov yuborish
        prompt = "Ushbu rasmdagi mahsulot nomini aniqlab ber. Faqat mahsulot nomini qisqa va aniq yoz, ortiqcha izoh berma."
        response = client.models.generate_content(
            model='gemini-3.6-flash',
            contents=[image, prompt]
        )
        
        product_name = response.text.strip()
        await status_msg.edit_text(f"📦 **Mahsulot nomi:**\n\n{product_name}", parse_mode="Markdown")
        
    except Exception as e:
        await status_msg.edit_text(f"❌ Gemini tahlilida xatolik yuz berdi: {str(e)}")

async def run_bot():
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
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
