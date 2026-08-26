import os
import logging
import asyncio
import requests
import json
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

# Render port xatosi uchun background server
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
    payload = {'key': FREEIMAGE_API_KEY, 'action': 'upload', 'format': 'json'}
    files = {'source': ('image.jpg', img_bytes, 'image/jpeg')}
    
    response = requests.post(url, data=payload, files=files, timeout=20)
    data = response.json()
    if response.status_code == 200 and data.get("status_code") == 200:
        return data["image"]["url"]
    else:
        raise Exception(f"Yuklashda xatolik: {data}")

# AI uchun o'zgarmas qat'iy Prompt (Faqat JSON qaytaradi)
SYSTEM_PROMPT = """
Siz e-commerce (Taobao/Pinduoduo/1688) skrinshotlaridan ma'lumot ajratuvchi AI assistentsiz.
Rasmlardagi matnlarni sinchkovlik bilan o'qib, FAQAT qat'iy JSON formatida javob bering.

QOIDALAR:
1. TIL: Barcha matn va tavsiflar faqat va faqat sof O'zbek tilida bo'lishi shart.
2. VARIANTLAR: Faqat sotuvda bor (faol) rang va o'lchamlarni ajratib oling.
3. SHARHLAR: Skrinshot va mahsulotdan kelib chiqib 4-6 ta tabiiy O'zbekcha xaridor sharhlarini shakllantiring.
4. NARX: Skrinshotdagi asosiy narxni (Yuanda, faqat raqam, masalan "23.3") ajrating.

JAVOB QAT'IYAN SHU JSON FORMATIDA BO'LSHI SHART (HECH QANDAY O'RTACHA MATN/MARKDOWN YOZMANGA):
{
  "price": "23.3",
  "name": "Mahsulot nomi",
  "catalog": "Kategoriya nomi",
  "type": "Mahsulot turi",
  "description": "Mahsulot haqida batafsil tavsif...",
  "variants": {
    "Rang": ["Oq", "Qora"],
    "Olcham": ["36", "37", "38"]
  },
  "stats": {
    "rating": "4.9",
    "reviews": "1200",
    "sold": "3500"
  },
  "extras": {
    "Ustki material": "PU teri",
    "Taglik": "Kauchuk"
  },
  "reviews_text": [
    "Juda sifatli mahsulot, tavsiya qilaman!",
    "O'z vaqtida yetib keldi, oyoqqa juda qulay."
  ],
  "instagram_caption": "💣 Zamonaviy krossovkalar..."
}
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['product_images'] = []
    context.user_data['review_images'] = []
    
    keyboard = [["▶️ Step 1 ni boshlash"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)
    
    await update.message.reply_text(
        "Salom! Mahsulot kartochkalarini HTML shaklida yaratuvchi botga xush kelibsiz.\n\n"
        "Boshlash uchun **▶️ Step 1 ni boshlash** tugmasini bosing.",
        reply_markup=reply_markup
    )
    return ConversationHandler.END

async def start_step1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['product_images'] = []
    context.user_data['review_images'] = []
    
    keyboard = [["Next ➡️"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)
    
    await update.message.reply_text(
        "📸 **Step 1:** Mahsulotning **ASOSIY RASMLARINI** yuboring (Gallereya uchun).\n\n"
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
        context.user_data.setdefault('product_images', []).append(bytes(img_bytes))

async def to_step2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    count1 = len(context.user_data.get('product_images', []))
    
    keyboard = [["Done ✅"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)
    
    await update.message.reply_text(
        f"✅ Mahsulot uchun **{count1} ta** rasm saqlandi.\n\n"
        f"📸 **Step 2:** Endi narx va **KOMMENTARIYA/SKRINSHOT** rasmlarini yuboring.\n\n"
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
        context.user_data.setdefault('review_images', []).append(bytes(img_bytes))

async def finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ AI ma'lumotlarni tahlil qilmoqda...", reply_markup=ReplyKeyboardRemove())
    
    # 1. FreeImage'ga ikkala turdagi rasmlarni yuklaymiz
    product_urls = []
    for img in context.user_data.get('product_images', []):
        try:
            product_urls.append(upload_to_freeimage(img))
        except Exception as e:
            logging.error(f"Product Image upload error: {e}")

    review_urls = []
    for img in context.user_data.get('review_images', []):
        try:
            review_urls.append(upload_to_freeimage(img))
        except Exception as e:
            logging.error(f"Review Image upload error: {e}")

    # 2. Gemini API ga Step 2 (skrinshot) rasmlarini uzatib JSON olamiz
    ai_data = {}
    review_imgs = context.user_data.get('review_images', [])
    
    if review_imgs and GEMINI_API_KEY:
        try:
            client = genai.Client(api_key=GEMINI_API_KEY)
            
            contents = [{"mime_type": "image/jpeg", "data": review_imgs[0]}]
            contents.append("Ushbu skrinshotdagi ma'lumotlarni ko'rsatilgan JSON formatida ajratib ber.")
            
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None, 
                lambda: client.models.generate_content(
                    model='gemini-2.5-flash', 
                    contents=contents,
                    config={"system_instruction": SYSTEM_PROMPT, "temperature": 0.1}
                )
            )

            if response and response.text:
                # JSON ni tozalab olish
                clean_json_str = re.sub(r'```json\s*|\s*```', '', response.text.strip())
                ai_data = json.loads(clean_json_str)
        except Exception as e:
            logging.error(f"Gemini JSON Parsing error: {e}")

    # 3. Python ichida narxni so'mga o'giramiz
    raw_price = float(ai_data.get("price", "0")) if ai_data.get("price") else 0
    price_in_som = f"{int(raw_price * YUAN_RATE):,}".replace(",", " ") if raw_price else "0"

    # 4. Python o'zining HTML Shablonini hosil qiladi
    product_images_html = "\n".join([f'      <img src="{url}" class="prod-img">' for url in product_urls])
    review_images_html = "\n".join([f'      <img src="{url}" class="rev-img">' for url in review_urls])
    
    reviews_list_html = "\n".join([f'      <li>{rev}</li>' for rev in ai_data.get("reviews_text", [])])

    variants_html = ""
    for v_key, v_vals in ai_data.get("variants", {}).items():
        variants_html += f"      <p><b>{v_key}:</b> {', '.join(v_vals)}</p>\n"

    extras_html = ""
    for e_key, e_val in ai_data.get("extras", {}).items():
        extras_html += f"      <p><b>{e_key}:</b> {e_val}</p>\n"

    # YAKUNIY HTML KOD SHABLONI
    html_code = f"""<div class="product-card">
  <h2>{ai_data.get("name", "Mahsulot Nomi")}</h2>
  <span class="price">{price_in_som} so'm</span>
  
  <div class="product-gallery">
{product_images_html}
  </div>

  <div class="description">
    <p>{ai_data.get("description", "")}</p>
  </div>

  <div class="variants">
{variants_html}  </div>

  <div class="extras">
{extras_html}  </div>

  <div class="reviews-section">
    <h3>Xaridorlar fikri ({ai_data.get("stats", {}).get("rating", "5.0")} ⭐)</h3>
    <ul>
{reviews_list_html}
    </ul>
    <div class="review-gallery">
{review_images_html}
    </div>
  </div>
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
