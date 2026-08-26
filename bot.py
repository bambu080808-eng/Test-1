import os
import logging
import asyncio
import io
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from google import genai
from google.genai import types
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters,
)

# Logging sozlamalari
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Kalitlar
TOKEN = os.environ.get("BOT_TOKEN")
FREEIMAGE_API_KEY = os.environ.get("FREEIMAGE_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Gemini SDK klienti
client = genai.Client(api_key=GEMINI_API_KEY)

# Bosqichlar
STEP1, STEP2, STEP3 = range(3)
LOCK = asyncio.Lock()

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
Siz — e-commerce platformasi uchun Xitoy marketplace'laridan olingan mahsulot ma'lumotlarini o'zbek tilidagi standart HTML kartochka formatiga to'liq o'girib beruvchi professional AI assistentsiz.

Sizga foydalanuvchi matn shaklida "STEP 1 URL" va "STEP 2 URL" havolalarini beradi, hamda ma'lumotlarni o'qish uchun skrinshotlarni yuklaydi.

QAT'IY QOIDALAR:
1. BARCHA MA'LUMOTLARNI TO'LIQ QAMRAB OLING: "..." kabi qisqartirishlar QAT'IYAN MAN ETILADI.
2. RASMLARNI SHABLONGA QAT'IY JOYLASHTIRING:
   - "STEP 1 URL" dagi BARCHA havolalarni <div class="images"> ichiga <img src="URL"> ko'rinishida joylashtiring. HECH BIRI QOLIB KETMASIN.
   - "STEP 2 URL" dagi havolalarni sharhlarga mos ravishda <div class="review-images"> ichiga <img src="URL"> ko'rinishida joylashtiring.
3. TIL SIFATI: Sof, ravon o'zbek tilidan foydalaning.
4. Xira (sotuvdan chiqqan) variantlarni <div class="variant"> ichiga qo'shmang.
5. Sharh muallifiga tasodifiy "ID: 10 xonali raqam" bering.

STANDART HTML SHABLON STRUKTURASI (Faqat toza HTML kodi qaytaring, ortiqcha izoh yozmang):
<div class="product">
  <div class="images">
    <img src="STEP_1_URL_1">
    <img src="STEP_1_URL_2">
  </div>
  <span class="price">0.00</span>
  <h2 class="name">Mahsulot nomi (O'zbek tilida)</h2>
  <div class="variant" data-type="Rang">
    <span>Mavjud rang 1</span>
  </div>
  <div class="variant" data-type="Olcham">
    <span>Mavjud o'lcham</span>
  </div>
  <p class="desc">Mahsulot haqida batafsil ma'lumot...</p>
  <span class="catalog">Katalog nomi</span>
  <span class="type">Mahsulot turi</span>
  <div class="stats">
    <span data-key="rating">4.8</span>
    <span data-key="reviews">100</span>
    <span data-key="views">1000</span>
    <span data-key="likes">500</span>
    <span data-key="sold">200</span>
  </div>
  <div class="extra" data-key="Xususiyat">Qiymat</div>
  <div class="review">
    <span class="author">ID: 1234567890</span>
    <span class="text">Sharh matni...</span>
    <div class="review-images">
      <img src="STEP_2_URL_1">
    </div>
  </div>
</div>
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["▶️ Step 1 ni boshlash"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)
    
    await update.message.reply_text(
        "Salom! Men mahsulot rasmlarini URL'ga aylantirib, ma'lumotlardan to'liq HTML kartochka yasab beruvchi botman.\n\n"
        "Jarayonni boshlash uchun pastdagi **▶️ Step 1 ni boshlash** tugmasini bosing.",
        reply_markup=reply_markup
    )

async def start_step1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['step1_images'] = []
    context.user_data['step2_images'] = []
    context.user_data['step3_images'] = []
    
    keyboard = [["Next: Step 2 ➡️"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)
    
    await update.message.reply_text(
        "📸 **Step 1:** Asosiy mahsulot rasmlarini yuboring.\n\n"
        "Rasmlarni yuborib bo'lgach, **Next: Step 2 ➡️** tugmasini bosing.",
        reply_markup=reply_markup
    )
    return STEP1

async def collect_images(update: Update, context: ContextTypes.DEFAULT_TYPE, step_key: str):
    if not update.message.photo:
        return
    photo = update.message.photo[-1]
    async with LOCK:
        file = await context.bot.get_file(photo.file_id)
        img_bytes = await file.download_as_bytearray()
        context.user_data.setdefault(step_key, []).append(bytes(img_bytes))

async def collect_step1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await collect_images(update, context, 'step1_images')

async def start_step2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    count = len(context.user_data.get('step1_images', []))
    keyboard = [["Next: Step 3 ➡️"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)
    
    await update.message.reply_text(
        f"✅ Step 1 (Asosiy rasmlar): {count} ta rasm qabul qilindi.\n\n"
        "📸 **Step 2:** Sharh (otziv) rasmlarini yuboring.\n\n"
        "Rasmlarni yuborib bo'lgach, **Next: Step 3 ➡️** tugmasini bosing.",
        reply_markup=reply_markup
    )
    return STEP2

async def collect_step2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await collect_images(update, context, 'step2_images')

async def start_step3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    count = len(context.user_data.get('step2_images', []))
    keyboard = [["Done ✅"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)
    
    await update.message.reply_text(
        f"✅ Step 2 (Sharh rasmlari): {count} ta rasm qabul qilindi.\n\n"
        "📸 **Step 3:** Ma'lumotlarni o'qib olish uchun skrinshotlarni yuboring (xususiyatlar, narx, sharh matnlari).\n\n"
        "Rasmlarni yuborib bo'lgach, **Done ✅** tugmasini bosing.",
        reply_markup=reply_markup
    )
    return STEP3

async def collect_step3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await collect_images(update, context, 'step3_images')

async def finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    count3 = len(context.user_data.get('step3_images', []))
    
    await update.message.reply_text(
        f"✅ Step 3 (Skrinshotlar): {count3} ta rasm qabul qilindi.\n\n"
        "⏳ **1-qadam:** Rasmlar FreeImage host xizmatiga yuklanmoqda...",
        reply_markup=ReplyKeyboardRemove()
    )
    
    # Step 1 va 2 rasmlarini URL'ga aylantirish
    step1_urls, step2_urls = [], []
    for img in context.user_data.get('step1_images', []):
        try:
            step1_urls.append(upload_to_freeimage(img))
        except Exception as e:
            logging.error(f"Step 1 yuklash xatosi: {e}")

    for img in context.user_data.get('step2_images', []):
        try:
            step2_urls.append(upload_to_freeimage(img))
        except Exception as e:
            logging.error(f"Step 2 yuklash xatosi: {e}")

    await update.message.reply_text("⏳ **2-qadam:** Gemini API skrinshotlar va havolalarni tahlil qilmoqda...")

    try:
        contents = []
        
        urls_instruction = "SIZGA YUBORILAYOTGAN TAYYOR RASM HAVOLALARI:\n\n"
        urls_instruction += "STEP 1 URL (Asosiy rasmlar galereyasi uchun <div class=\"images\"> ichiga qo'ying):\n"
        urls_instruction += "\n".join(step1_urls) if step1_urls else "Mavjud emas"
        urls_instruction += "\n\nSTEP 2 URL (Sharhlar uchun <div class=\"review-images\"> ichiga qo'ying):\n"
        urls_instruction += "\n".join(step2_urls) if step2_urls else "Mavjud emas"
        
        urls_instruction += "\n\nDIQQAT: Yuqoridagi barcha URL'larni taqdim etilgan HTML strukturadagi tegishli <img> teglariga to'liq joylashtiring!"

        contents.append(urls_instruction)
        
        for img in context.user_data.get('step3_images', []):
            contents.append(types.Part.from_bytes(data=img, mime_type="image/jpeg"))

        config = types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT, temperature=0.1)
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None, lambda: client.models.generate_content(model='gemini-3.6-flash', contents=contents, config=config)
        )

        html_result = response.text.strip() if response.text else "Ma'lumot ajratib bo'lmadi."
        
        # ```html teglarni tozalash
        if html_result.startswith("```"):
            lines = html_result.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            html_result = "\n".join(lines).strip()

        # HTML javobni matn shaklida yuborish (parse_mode ishlatmasdan parsing xatosini oldini olamiz)
        if len(html_result) <= 4000:
            await update.message.reply_text(html_result)
        else:
            for i in range(0, len(html_result), 4000):
                await update.message.reply_text(html_result[i:i+4000])

        # HTML fayl ko'rinishida ham yuborish (saytga birdan ishlatish uchun qulay)
        html_bytes = io.BytesIO(html_result.encode('utf-8'))
        html_bytes.name = "product_card.html"
        await update.message.reply_document(document=html_bytes, caption="📄 Tayyor HTML fayl")

    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik yuz berdi: {str(e)}")

    restart_keyboard = [["▶️ Step 1 ni boshlash"]]
    await update.message.reply_text(
        "Yangi kartochka yaratish uchun tugmani bosing:",
        reply_markup=ReplyKeyboardMarkup(restart_keyboard, resize_keyboard=True, is_persistent=True)
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Jarayon bekor qilindi.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def main():
    threading.Thread(target=run_health_check_server, daemon=True).start()
    
    application = ApplicationBuilder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r"^▶️ Step 1 ni boshlash$"), start_step1)],
        states={
            STEP1: [
                MessageHandler(filters.Regex(r"^Next: Step 2 ➡️$"), start_step2),
                MessageHandler(filters.PHOTO, collect_step1)
            ],
            STEP2: [
                MessageHandler(filters.Regex(r"^Next: Step 3 ➡️$"), start_step3),
                MessageHandler(filters.PHOTO, collect_step2)
            ],
            STEP3: [
                MessageHandler(filters.Regex(r"^Done ✅$"), finish),
                MessageHandler(filters.PHOTO, collect_step3)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", start)],
        allow_reentry=True
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
