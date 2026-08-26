import os
import logging
import asyncio
import requests
import json
import re
import io
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

STEP1, STEP2, STEP3 = range(3)
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
    payload = {'key': FREEIMAGE_API_KEY, 'action': 'upload', 'format': 'json'}
    files = {'source': ('image.jpg', img_bytes, 'image/jpeg')}
    
    response = requests.post(url, data=payload, files=files, timeout=20)
    data = response.json()
    if response.status_code == 200 and data.get("status_code") == 200:
        return data["image"]["url"]
    else:
        raise Exception(f"FreeImage ga yuklashda xatolik: {data.get('error', {}).get('message', 'Noma\\'lum xato')}")

SYSTEM_PROMPT = """
Sana yuborilayotgan ushbu rasmlar e-commerce platformasi (Taobao/Pinduoduo/1688) uchun mahsulotning xarakteristikalari va tavsiflaridir.
Rasmlardagi barcha matnlarni, jadvallarni va ma'lumotlarni sinchkovlik bilan o'qib chiqib, quyidagi qat'iy qoidalar bo'yicha JSON formatida javob ber:

QOIDALAR:
1. TIL VA TARJIMA: Barcha matnlar, xususiyatlar, tavsif va sharhlar faqat va faqat sof, ravon va tushunarli O'zbek tilida bo'lishi shart. Inglizcha yoki xitoycha so'z va atamalardan foydalanma (masalan: "Printed" -> "Naqshli", "Slip-on" -> "Yengil kiyiladigan poyabzal", "Rubber" -> "Kauchuk/Rezina").
2. VARIANT VA O'LCHAMLAR: Variant rasmlari yoki skrinshotlarini sinchkovlik bilan tahlil qil. Faqat sotuvda bor (faol, to'q shriftli) rang va o'lchamlarni ajratib ol. Xira, tugmasi faolsizlashtirilgan yoki tugagan variantlarni BUTUNLAY CHIQARIB TASHLA.
3. KATALOG VA TYPE: 'catalog' va 'type' qiymatlarini faqat tasdiqlangan standart ro'yxat bo'yicha belgilang (Poyabzallar, Kiyim-kechak, Sumka va Aksessuarlar, Uy-ro'zg'or buyumlari, Maishiy texnika va h.k.).
4. SHARHLAR (REVIEWS): Rasmlardagi ma'lumotlar va mahsulot xususiyatidan kelib chiqib, xaridori juda xursand bo'lgan 6-8 ta har xil va tabiiy chiroyli O'zbekcha sharhlar (text) generatsiya qilib ber.

JAVOBNI QAT'IYAN QUYIDAGI JSON FORMATIDA QAYTAR (ORTIQCHA MATN YOZMA):

{
  "price": "20.71",
  "name": "Mahsulotning o'zbekcha nomi",
  "catalog": "Poyabzallar",
  "type": "Ayollar poyabzali",
  "description": "Mahsulot haqida batafsil va jozibador O'zbekcha tavsif...",
  "variants": {
    "Rang": ["Oq", "Moviy", "Xaki"],
    "Olcham": ["35", "36", "37", "38", "39", "40"]
  },
  "stats": {
    "rating": "4.9",
    "reviews": "7000",
    "views": "15000",
    "likes": "7669",
    "sold": "9436"
  },
  "extras": {
    "Brend": "KaiQi",
    "Ustki material": "PU teri",
    "Taglik materiali": "Kauchuk / Rezina",
    "Uslub": "Kundalik / Sport",
    "Poshta balandligi": "3cm-5cm",
    "Yopilish turi": "Bog'ichli (Ipli)"
  },
  "reviews_text": [
    "Oq krossovkalarni qabul qilib oldim va kiyib ko'rdim. O'lchami juda mos keldi, dizayni ajoyib!",
    "Poyabzal juda bejirim va oyoqqa juda mos keladi. Qalin tagligi sirpanishga qarshi yaxshi...",
    "Bu poyabzallar juda go'zal va kiyishga juda qulay. Ajoyib juftlik!",
    "Bu poyabzalni olib hayratda qoldim! Sifatli tikilgan, ortiqcha iplari yo'q.",
    "Juda qulay va zamonaviy, tavsiya qilaman!",
    "Toza, yangi va kiyishga qulay. Narxiga to'liq arziydi!"
  ],
  "instagram_caption": "💣 Ayollar uchun yangi va zamonaviy krossovkalar!..."
}
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['step1_images'] = []
    context.user_data['step2_images'] = []
    context.user_data['step3_images'] = []
    
    keyboard = [["▶️ Step 1 ni boshlash"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)
    
    await update.message.reply_text(
        "Salom! Mahsulot kartochkalarini HTML shaklida yaratuvchi botga xush kelibsiz.\n\n"
        "Boshlash uchun **▶️ Step 1 ni boshlash** tugmasini bosing.",
        reply_markup=reply_markup
    )
    return ConversationHandler.END

async def start_step1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['step1_images'] = []
    context.user_data['step2_images'] = []
    context.user_data['step3_images'] = []
    
    keyboard = [["Next ➡️ (Step 2)"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)
    
    await update.message.reply_text(
        "📸 **Step 1:** Mahsulotning **ASOSIY RASMLARINI** yuboring (Gallereya uchun).\n\n"
        "Tugallagach, **Next ➡️ (Step 2)** tugmasini bosing.",
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
    
    keyboard = [["Next ➡️ (Step 3)"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)
    
    await update.message.reply_text(
        f"✅ Step 1: **{count1} ta** asosiy rasm qabul qilindi.\n\n"
        f"📸 **Step 2:** Endi **KOMMENTARIYA/XARIDORLAR RASMLARINI** yuboring.\n\n"
        f"Tugallagach, **Next ➡️ (Step 3)** tugmasini bosing.",
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

async def to_step3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    count2 = len(context.user_data.get('step2_images', []))
    
    keyboard = [["Done ✅"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)
    
    await update.message.reply_text(
        f"✅ Step 2: **{count2} ta** kommentariya rasmi qabul qilindi.\n\n"
        f"📸 **Step 3:** Endi mahsulot **MA'LUMOTLARI VA NARXI** aks etgan skrinshotlarni yuboring (Gemini uchun).\n\n"
        f"Yuborib bo'lgach, **Done ✅** tugmasini bosing.",
        reply_markup=reply_markup
    )
    return STEP3

async def collect_step3_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        return
    photo = update.message.photo[-1]
    async with LOCK:
        file = await context.bot.get_file(photo.file_id)
        img_bytes = await file.download_as_bytearray()
        context.user_data.setdefault('step3_images', []).append(bytes(img_bytes))

async def finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    restart_keyboard = [["▶️ Step 1 ni boshlash"]]
    reply_markup_restart = ReplyKeyboardMarkup(restart_keyboard, resize_keyboard=True, is_persistent=True)

    # 1. FreeImage ga yuklash jarayoni
    await update.message.reply_text("📸 Rasmlar FreeImage serveriga yuklanmoqda...", reply_markup=ReplyKeyboardRemove())
    
    product_urls = []
    for idx, img in enumerate(context.user_data.get('step1_images', []), 1):
        try:
            url = upload_to_freeimage(img)
            product_urls.append(url)
        except Exception as e:
            await update.message.reply_text(f"❌ Muammo: Step 1 dagi {idx}-rasmni yuklashda xatolik:\n`{e}`", reply_markup=reply_markup_restart)
            return ConversationHandler.END

    review_urls = []
    for idx, img in enumerate(context.user_data.get('step2_images', []), 1):
        try:
            url = upload_to_freeimage(img)
            review_urls.append(url)
        except Exception as e:
            await update.message.reply_text(f"❌ Muammo: Step 2 dagi {idx}-rasmni yuklashda xatolik:\n`{e}`", reply_markup=reply_markup_restart)
            return ConversationHandler.END

    # 2. AI (Gemini) ga yuborish
    step3_imgs = context.user_data.get('step3_images', [])
    if not step3_imgs:
        await update.message.reply_text("❌ Muammo: Step 3 da hech qanday skrinshot yuborilmadi!", reply_markup=reply_markup_restart)
        return ConversationHandler.END

    if not GEMINI_API_KEY:
        await update.message.reply_text("❌ Muammo: GEMINI_API_KEY o'zgaruvchisi o'rnatilmagan!", reply_markup=reply_markup_restart)
        return ConversationHandler.END

    await update.message.reply_text("🤖 Step 3 rasmlari Gemini AI ga jo'natildi. Javob kutilmoqda...")

    ai_data = {}
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        contents = []
        for img in step3_imgs:
            contents.append({"mime_type": "image/jpeg", "data": img})
        
        contents.append("Ushbu skrinshotlardagi barcha ma'lumotlarni ko'rsatilgan JSON formatida ajratib ber.")
        
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
            clean_json_str = re.sub(r'```json\s*|\s*```', '', response.text.strip())
            ai_data = json.loads(clean_json_str)
        else:
            raise Exception("Gemini API dan bo'sh javob qaytdi.")

    except Exception as e:
        await update.message.reply_text(f"❌ Muammo: Gemini AI tahlil qilishda xatolik berdi:\n`{e}`", reply_markup=reply_markup_restart)
        return ConversationHandler.END

    # 3. Javob keldi va HTML tayyorlanmoqda
    await update.message.reply_text("⚡ AI javob qaytardi! HTML shablon shakllantirilmoqda...")

    try:
        raw_price = float(ai_data.get("price", "0")) if ai_data.get("price") else 0
        price_in_som = f"{int(raw_price * YUAN_RATE):,}".replace(",", " ") if raw_price else "0"

        product_images_html = "\n".join([f'      <img src="{url}" alt="Mahsulot" class="prod-img">' for url in product_urls])
        review_images_html = "\n".join([f'      <img src="{url}" alt="Xaridor rasmi" class="rev-img">' for url in review_urls])
        reviews_list_html = "\n".join([f'      <li class="review-item">{rev}</li>' for rev in ai_data.get("reviews_text", [])])

        variants_html = ""
        for v_key, v_vals in ai_data.get("variants", {}).items():
            variants_html += f'      <div class="variant-group"><strong>{v_key}:</strong> {", ".join(v_vals)}</div>\n'

        extras_html = ""
        for e_key, e_val in ai_data.get("extras", {}).items():
            extras_html += f'      <div class="extra-item"><span>{e_key}:</span> <strong>{e_val}</strong></div>\n'

        stats = ai_data.get("stats", {})

        html_code = f"""<div class="product-card">
  <div class="product-header">
    <span class="catalog-badge">{ai_data.get("catalog", "Katalog")} / {ai_data.get("type", "Turi")}</span>
    <h1 class="product-title">{ai_data.get("name", "Mahsulot Nomi")}</h1>
    <div class="price-tag">{price_in_som} so'm</div>
  </div>

  <div class="product-gallery">
{product_images_html}
  </div>

  <div class="product-description">
    <h3>Mahsulot tavsifi</h3>
    <p>{ai_data.get("description", "")}</p>
  </div>

  <div class="product-variants">
    <h3>Mavjud variantlar:</h3>
{variants_html}  </div>

  <div class="product-extras">
    <h3>Xarakteristikalar:</h3>
{extras_html}  </div>

  <div class="product-stats">
    <span>⭐ Reiting: {stats.get("rating", "5.0")}</span> | 
    <span>💬 Sharhlar: {stats.get("reviews", "0")}</span> | 
    <span>🔥 Sotildi: {stats.get("sold", "0")}</span>
  </div>

  <div class="product-reviews">
    <h3>Xaridorlar fikri va foto-sharhlar:</h3>
    <ul class="reviews-list">
{reviews_list_html}
    </ul>
    <div class="review-gallery">
{review_images_html}
    </div>
  </div>
</div>"""

        # 4. PYTHON XOTIRASIDA (RAM) .HTML FAYL YARATISH VA YUBORISH
        html_file = io.BytesIO(html_code.encode('utf-8'))
        html_file.name = "product_card.html"
        
        await update.message.reply_document(
            document=html_file, 
            caption="📄 **Tayyor HTML faylingiz!**"
        )

        # Instagram post matnini alohida yuborish
        if ai_data.get("instagram_caption"):
            await update.message.reply_text(f"📱 **Instagram Caption:**\n\n{ai_data.get('instagram_caption')}")

        await update.message.reply_text(
            "✅ Kartochka muvaffaqiyatli yaratildi! Yangi kartochka uchun tugmani bosing:",
            reply_markup=reply_markup_restart
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Muammo: HTML kodni shakllantirishda xatolik:\n`{e}`", reply_markup=reply_markup_restart)

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
                MessageHandler(filters.Regex(r"^Next ➡️ \(Step 2\)$"), to_step2),
                MessageHandler(filters.PHOTO, collect_step1_images)
            ],
            STEP2: [
                MessageHandler(filters.Regex(r"^Next ➡️ \(Step 3\)$"), to_step3),
                MessageHandler(filters.PHOTO, collect_step2_images)
            ],
            STEP3: [
                MessageHandler(filters.Regex(r"^Done ✅$"), finish),
                MessageHandler(filters.PHOTO, collect_step3_images)
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
