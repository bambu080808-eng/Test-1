import os
import logging
import asyncio
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from google import genai
from google.genai import types
from telegram import Update
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
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Gemini SDK klienti
client = genai.Client(api_key=GEMINI_API_KEY)

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

SYSTEM_PROMPT = """
Sana e-commerce platformasidan olingan rasm yuboriladi.
Rasmdagi mahsulot narxini top (Yuan/¥ da) va uni O'zbekiston so'miga o'gir (1 Yuan = 1800 so'm nisbatida).
Javobni faqat va faqat JSON formatida qaytar:
{
  "yuan": "23.3",
  "som": "41,940",
  "found": true
}
Agar narx topilmasa:
{
  "found": false
}
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Salom! Menga mahsulot skrinshotini yuboring, men narxini so'mda hisoblab beraman.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_msg = await update.message.reply_text("⏳ Narx tahlil qilinmoqda...")
    
    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        img_bytes = await file.download_as_bytearray()

        contents = [
            types.Part.from_bytes(
                data=bytes(img_bytes),
                mime_type="image/jpeg",
            )
        ]

        # JSON structured output sozlamasi
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            temperature=0.1
        )

        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None, 
            lambda: client.models.generate_content(
                model='gemini-3.6-flash',
                contents=contents,
                config=config
            )
        )

        # JSON javobni qayta ishlash
        data = json.loads(response.text)
        
        if data.get("found"):
            yuan = data.get("yuan", "—")
            som = data.get("som", "—")
            
            result_text = f"💰 **Mahsulot narxi:**\n• Yuan: {yuan} ¥\n• So'mda: {som} so'm"
        else:
            result_text = "❌ Rasmda narx ko'rinmadi, iltimos narxi aniq ko'ringan rasm yuboring."

        await status_msg.edit_text(result_text, parse_mode="Markdown")

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
    threading.Thread(target=run_health_check_server, daemon=True).start()
    
    try:
        asyncio.run(run_bot())
    except (KeyboardInterrupt, SystemExit):
        pass

if __name__ == '__main__':
    main()
