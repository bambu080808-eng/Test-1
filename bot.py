import os
import logging
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from google import genai
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = os.environ.get("BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Gemini SDK klienti
client = genai.Client(api_key=GEMINI_API_KEY)

# Render port xatosi bermasligi uchun soxta server
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is active")

def run_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

SYSTEM_PROMPT = """
Sana e-commerce platformasidan (Taobao/Pinduoduo/1688) olingan mahsulot rasmi yuboriladi.
Sening yagona vazifang:
1. Rasmdagi mahsulot narxini topish (odatda Yuan/¥ da berilgan bo'ladi).
2. Ushbu narxni O'zbekiston so'miga taxminiy o'girish (1 Yuan = 1800 so'm nisbatida).
3. Faqat va faqat quyidagi formatda qisqa javob berish:

💰 **Mahsulot narxi:**
• Yuan: [topilgan narx] ¥
• So'mda: [hisoblangan narx] so'm

Misol uchun:
💰 **Mahsulot narxi:**
• Yuan: 23.3 ¥
• So'mda: 41,940 so'm

Agar rasmda narx topilmasa: "❌ Rasmda narx ko'rinmadi, iltimos narxi aniq ko'ringan rasm yuboring." deb javob ber.
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Salom! Menga mahsulot skrinshotini yuboring, men narxini so'mda hisoblab beraman.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_msg = await update.message.reply_text("⏳ Narx tahlil qilinmoqda...")
    
    try:
        # Eng yuqori sifatdagi rasmni olish
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        img_bytes = await file.download_as_bytearray()

        contents = [
            SYSTEM_PROMPT,
            {
                "mime_type": "image/jpeg",
                "data": bytes(img_bytes)
            }
        ]

        # Gemini so'rovini fonda bajaramiz
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None, 
            lambda: client.models.generate_content(
                model='gemini-2.5-flash',
                contents=contents,
            )
        )

        await status_msg.edit_text(response.text, parse_mode="Markdown")

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
    # Render port tekshiruvi uchun serverni ishga tushirish
    threading.Thread(target=run_health_check_server, daemon=True).start()
    
    try:
        asyncio.run(run_bot())
    except (KeyboardInterrupt, SystemExit):
        pass

if __name__ == '__main__':
    main()
