import os
import logging
import asyncio
import requests
import re
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from google import genai
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters,
)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = os.environ.get("BOT_TOKEN") or "7857867174:AAEghTH8fqeItdfZSFbxy1JP9KytrMdS6mgc"
FREEIMAGE_API_KEY = os.environ.get("FREEIMAGE_API_KEY") or "6d207e02198a847aa98d0a2a901485a5"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

STEP1, STEP2 = range(2)
LOCK = asyncio.Lock()

YUAN_RATE = 1780 

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot Active")

def run_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

def upload_to_freeimage(img_bytes: bytes) -> str:
    url = "https://freeimage.host/api/1/upload"
    payload = {
        'key': FREEIMAGE_API_KEY,
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

SYSTEM_PROMPT = """
Skrinshotdagi asosiy sotuv narxini toping.
FAQAT VA FAQAT raqamni qaytaring (masalan: 23.3). 
Hech qanday valyuta belgisi (¥, $), so'z yoki qo'shimcha text yozmang!
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['step1_images'] = []
    context.user_data['step2_images'] = []
    
    keyboard = [["▶️ Step 1 ni boshlash"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)
    
    await update.message.reply_text(
        "Salom! Mahsulot rasmlari va narxidan sodda HTML kod yaratuvchi botga xush kelibsiz.\n\n"
        "Boshlash uchun **▶️ Step 1 ni boshlash** tugmasini bosing.",
        reply_markup=reply_markup
    )
    return ConversationHandler.END

async def start_step1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['step1_images'] = []
    context.user_data['step2_images'] = []
    
    keyboard = [["Next ➡️"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)
    
    await update.message.reply_text(
        "📸 **Step 1:** Mahsulotning asl rasmlarini yuboring.\n\n"
        "Tugallagach, **Next ➡️** tugmasini bosing.",
        reply_markup=reply_markup
    )
    return STEP1

async def collect_step1_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        return
    photo = update.message.photo[-1]
    async with LOCK:
        file = await context.bot.get_file(photo.file_id)
        img_bytes = await file.download_as_bytearray()
        context.user_data.setdefault('step1_images', []).append(bytes(img_bytes))

async def to_step2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    count1 = len(context.user_data.get('step1_images', []))
    
    keyboard = [["Done ✅"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)
    
    await update.message.reply_text(
        f"✅ Step 1 uchun **{count1} ta** rasm qabul qilindi.\n\n"
        f"📸 **Step 2:** Endi narxi ko'ringan skrinshot rasmini yuboring.\n\n"
        f"Yuborib bo'lgach, **Done ✅** tugmasini bosing.",
        reply_markup=reply_markup
    )
    return STEP2

async def collect_step2_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        return
    photo = update.message.photo[-1]
    async with LOCK:
        file = await context.bot.get_file(photo.file_id)
        img_bytes = await file.download_as_bytearray()
        context.user_data.setdefault('step2_images', []).append(bytes(img_bytes))

async def finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ HTML kod tayyorlanmoqda...", reply_markup=ReplyKeyboardRemove())
    
    # 1. FreeImage rasmlarni yuklash
    step1_urls = []
    for img in context.user_data.get('step1_images', []):
        try:
            url = upload_to_freeimage(img)
            step1_urls.append(url)
        except Exception as e:
            logging.error(f"FreeImage xatosi: {e}")

    # 2. Gemini orqali narxni aniqlash
    price_in_som = "0"
    step2_imgs = context.user_data.get('step2_images', [])
    
    if step2_imgs and GEMINI_API_KEY:
        try:
            client = genai.Client(api_key=GEMINI_API_KEY)
            
            # Gemini'ga rasm va textni bitta massivda uzatamiz
            contents = [
                SYSTEM_PROMPT,
                {"mime_type": "image/jpeg", "data": step2_imgs[0]}
            ]
            
            loop = asyncio.get_running_loop()
            
            # Model orqali murojaat qilish
            response = await loop.run_in_executor(
                None, 
                lambda: client.models.generate_content(
                    model='gemini-2.5-flash', 
                    contents=contents
                )
            )

            if response and response.text:
                logging.info(f"Gemini javobi: {response.text}")
                # Raqamni ajratib olish (masalan 23.3)
                match = re.search(r"\d+(\.\d+)?", response.text.strip())
                if match:
                    price_val = float(match.group())
                    som_val = int(price_val * YUAN_RATE)
                    price_in_som = f"{som_val:,}".replace(",", " ")
        except Exception as e:
            logging.error(f"Gemini chaqirishda xatolik: {e}")

    images_html = "\n".join([f'    <img src="{url}">' for url in step1_urls])
    
    html_code = f"""<div class="product">
  <div class="images">
{images_html}
  </div>
  <span class="price">{price_in_som} so'm</span>
</div>"""

    final_response = f"```html\n{html_code}\n```"
    await update.message.reply_text(final_response, parse_mode="Markdown")

    restart_keyboard = [["▶️ Step 1 ni boshlash"]]
    await update.message.reply_text(
        "Yangi kartochka yaratish uchun tugmani bosing:",
        reply_markup=ReplyKeyboardMarkup(restart_keyboard, resize_keyboard=True, is_persistent=True)
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Jarayon bekor qilindi.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def main():
    threading.Thread(target=run_health_check_server, daemon=True).start()

    application = ApplicationBuilder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(r"^▶️ Step 1 ni boshlash$"), start_step1),
            CommandHandler("start", start_step1)
        ],
        states={
            STEP1: [
                MessageHandler(filters.Regex(r"^Next ➡️$"), to_step2),
                MessageHandler(filters.PHOTO, collect_step1_images)
            ],
            STEP2: [
                MessageHandler(filters.Regex(r"^Done ✅$"), finish),
                MessageHandler(filters.PHOTO, collect_step2_images)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", start)],
        allow_reentry=True
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    
    await application.initialize()
    await application.start()
    await application.updater.start_polling(drop_pending_updates=True)
    await asyncio.Event().wait()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
