import os
import logging
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)

# Logging sozlamalari
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = os.environ.get("BOT_TOKEN")

# Render Web Service port xatosini oldini olish uchun soxta server
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is active")

def run_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['photos'] = []
    context.user_data['total_received'] = 0
    context.user_data['collecting'] = True

    keyboard = [[KeyboardButton("✅ Done")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "Salom! Mahsulot rasmlarini (albom, bittalab yoki aralash) yuboring.\n\n"
        "Barcha rasmlarni yuborib bo'lgach, pastdagi **'✅ Done'** tugmasini bosing.",
        reply_markup=reply_markup
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('collecting', False):
        await update.message.reply_text("Rasmlarni qaytadan yuborish uchun /start tugmasini bosing.")
        return

    context.user_data['total_received'] = context.user_data.get('total_received', 0) + 1
    
    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        img_bytes = await file.download_as_bytearray()
        
        if 'photos' not in context.user_data:
            context.user_data['photos'] = []
            
        context.user_data['photos'].append(bytes(img_bytes))
        
    except Exception as e:
        logging.error(f"Rasm yuklashda xatolik: {e}")

async def handle_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('collecting', False):
        await update.message.reply_text("Yangi seans boshlash uchun /start buyrug'ini yuboring.", reply_markup=ReplyKeyboardRemove())
        return

    context.user_data['collecting'] = False
    
    total = context.user_data.get('total_received', 0)
    photos = context.user_data.get('photos', [])
    success_count = len(photos)

    if success_count == 0:
        await update.message.reply_text(
            "❌ Hech qanday rasm qabul qilinmadi. Iltimos, /start bosib rasmlarni qayta yuboring.",
            reply_markup=ReplyKeyboardRemove()
        )
        return

    report_msg = (
        f"📊 **Rasmlar qabul qilindi:**\n"
        f"• Jo'natilgan rasmlar: {total} ta\n"
        f"• Muvaffaqiyatli qabul qilindi: {success_count} ta\n\n"
        f"⏳ Ma'lumotlarni ajratib olish va tahlil qilish boshlanmoqda..."
    )
    
    await update.message.reply_text(report_msg, reply_markup=ReplyKeyboardRemove())

def main():
    threading.Thread(target=run_health_check_server, daemon=True).start()
    
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.Regex("^✅ Done$"), handle_done))
    
    # Standard va xatosiz polling usuli
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
