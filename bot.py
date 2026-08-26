import os
import logging
import asyncio
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

# Logging sozlamalari[span_2](start_span)[span_2](end_span)[span_3](start_span)[span_3](end_span)
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Kalitlar[span_4](start_span)[span_4](end_span)[span_5](start_span)[span_5](end_span)
TOKEN = os.environ.get("BOT_TOKEN")
FREEIMAGE_API_KEY = os.environ.get("FREEIMAGE_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Gemini SDK klienti[span_6](start_span)[span_6](end_span)
client = genai.Client(api_key=GEMINI_API_KEY)

# Bosqichlar
STEP1, STEP2, STEP3 = range(3)
LOCK = asyncio.Lock()

# Render Web Service port xatosini oldini olish uchun soxta server[span_7](start_span)[span_7](end_span)
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
Siz — e-commerce platformasi uchun Xitoy marketplace'laridan olingan mahsulot ma'lumotlarini o'zbek tilidagi standart HTML kartochka formatiga to'liq o'girib beruvchi professional AI assistentsiz[span_8](start_span)[span_8](end_span).

Sizga foydalanuvchi tomonidan tayyor rasmlar havolalari (URL) va ma'lumotlarni ajratib olish uchun skrinshotlar beriladi.

QAT'IY QOIDALAR:
1. BARCHA MA'LUMOTLARNI TO'LIQ QAMRAB OLING. "..." kabi qisqartirishlar QAT'IYAN MAN ETILADI[span_9](start_span)[span_9](end_span).
2. TIL SIFATI: Sof o'zbek tilidan foydalaning[span_10](start_span)[span_10](end_span).
3. RASMLAR TARTIBI:
   - Foydalanuvchi matn orqali yuborgan "STEP 1 URL" havolalarini asosiy mahsulot rasmlari sifatida `<div class="images">` ichiga joylashtiring[span_11](start_span)[span_11](end_span).
   - Foydalanuvchi matn orqali yuborgan "STEP 2 URL" havolalarini sharh rasmlari sifatida `<div class="review-images">` ichiga joylashtiring[span_12](start_span)[span_12](end_span).
4. Xira (sotuvdan chiqqan) variantlarni <div class="variant"> ichiga qo'shmang[span_13](start_span)[span_13](end_span).
5. Sharh muallifiga tasodifiy "ID: 10 xonali raqam" bering[span_14](start_span)[span_14](end_span).

STANDART HTML SHABLON STRUKTURASI (Faqat toza HTML qaytaring):
<div class="product">
  <div class="images">
    <img src="STEP_1_URL_1_SHU_YERGA">
    <img src="STEP_1_URL_2_SHU_YERGA">
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
      <img src="STEP_2_URL_1_SHU_YERGA">
    </div>
  </div>
</div>
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["▶️ Step 1 ni boshlash"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)
    
    await update.message.reply_text(
        "Salom! Men mahsulot rasmlarini URL'ga aylantirib, ma'lumotlardan to'liq HTML kartochka yasab beruvchi botman. Jarayonni boshlash uchun pastdagi tugmani bosing.",
        reply_markup=reply_markup
    )

async def start_step1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['step1_images'] = []
    context.user_data['step2_images'] = []
    context.user_data['step3_images'] = []
    
    keyboard = [["Next: Step 2 ➡️"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)
    
    await update.message.reply_text(
        "📸 **Step 1:** Asosiy mahsulot rasmlarini yuboring.\nRasmlarni yuborib bo'lgach, **Next: Step 2 ➡️** tugmasini bosing.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
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
        "📸 **Step 2:** Sharh (otziv) rasmlarini yuboring.\nRasmlarni yuborib bo'lgach, **Next: Step 3 ➡️** tugmasini bosing.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
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
        "📸 **Step 3:** Ma'lumotlarni o'qib olish uchun skrinshotlarni yuboring (xususiyatlar, narx, sharh matnlari).\nRasmlarni yuborib bo'lgach, **Done ✅** tugmasini bosing.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return STEP3

async def collect_step3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await collect_images(update, context, 'step3_images')

async def finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    count3 = len(context.user_data.get('step3_images', []))
    
    await update.message.reply_text(
        f"✅ Step 3 (Skrinshotlar): {count3} ta rasm qabul qilindi.\n\n"
        "⏳ **1-qadam:** Rasmlar URL havolaga aylantirilmoqda...",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )
    
    # Step 1 va 2 rasmlarini URL'ga aylantirish
    step1_urls, step2_urls = [], []
    for img in context.user_data.get('step1_images', []):
        try: step1_urls.append(upload_to_freeimage(img))
        except: pass
    for img in context.user_data.get('step2_images', []):
        try: step2_urls.append(upload_to_freeimage(img))
        except: pass

    await update.message.reply_text("⏳ **2-qadam:** Gemini API orqali skrinshotlar tahlil qilinib, HTML tayyorlanmoqda...", parse_mode="Markdown")

    try:
        contents = []
        user_prompt_text = (
            f"Foydalanilishi kerak bo'lgan tayyor URL havolalar:\n\n"
            f"STEP 1 URL (Asosiy rasmlar):\n{chr(10).join(step1_urls) if step1_urls else 'Yoq'}\n\n"
            f"STEP 2 URL (Sharh rasmlari):\n{chr(10).join(step2_urls) if step2_urls else 'Yoq'}\n\n"
            f"Biriktirilgan rasmlardan (skrinshotlardan) barcha tekst ma'lumotlarini ajratib olib shablonga joylang."
        )
        
        contents.append(user_prompt_text)
        
        # Step 3 rasmlarini Gemini ga yuborish
        for img in context.user_data.get('step3_images', []):
            contents.append(types.Part.from_bytes(data=img, mime_type="image/jpeg"))

        config = types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT, temperature=0.2)
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None, lambda: client.models.generate_content(model='gemini-3.6-flash', contents=contents, config=config)
        )

        html_result = response.text.strip() if response.text else "Ma'lumot ajratib bo'lmadi."
        final_text = f"```html\n{html_result}\n```"
        
        if len(final_text) <= 4000:
            await update.message.reply_text(final_text, parse_mode="Markdown")
        else:
            for i in range(0, len(final_text), 4000):
                await update.message.reply_text(final_text[i:i+4000], parse_mode="Markdown")

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
