import os
import logging
import asyncio
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

TOKEN = os.environ.get("BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)

WAITING_INPUT = range(1)
LOCK = asyncio.Lock()

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
    context.user_data['images_list'] = []
    
    keyboard = [["▶️ Boshlash"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)
    
    if update.message:
        await update.message.reply_text(
            "Salom! Mahsulot skrinshotlarini yuborish uchun **▶️ Boshlash** tugmasini bosing.",
            reply_markup=reply_markup
        )
    return ConversationHandler.END

async def ask_product_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['images_list'] = []
    
    keyboard = [["Done ✅"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)
    
    await update.message.reply_text(
        "📥 Iltimos, mahsulotga tegishli **skrinshotlarni** yuboring "
        "(albom yoki bittalab ko'rinishda).\n\n"
        "Barcha rasmlarni yuborib bo'lgach, pastdagi **Done ✅** tugmasini bosing.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return WAITING_INPUT

async def collect_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        img_bytes = await file.download_as_bytearray()
        
        async with LOCK:
            context.user_data.setdefault('images_list', []).append(bytes(img_bytes))

async def finish_and_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    images_list = context.user_data.get('images_list', [])
    total_sent = len(images_list)
    
    if total_sent == 0:
        await update.message.reply_text("⚠️ Siz hali hech qanday rasm yubormadingiz!")
        return WAITING_INPUT

    await update.message.reply_text(
        f"📊 **Hisobot:**\n"
        f"• Yuborilgan rasmlar: **{total_sent} ta**\n"
        f"• Qabul qilib olindi: **{total_sent} ta**\n\n"
        f"⏳ Ma'lumotlar tahlil qilinmoqda, iltimos kuting...",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )

    try:
        contents = [SYSTEM_PROMPT]
        for img_bytes in images_list:
            contents.append({
                "mime_type": "image/jpeg",
                "data": img_bytes
            })

        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None, 
            lambda: client.models.generate_content(
                model='gemini-2.5-flash',
                contents=contents,
            )
        )
        
        result_text = response.text

        await update.message.reply_text("✅ Ma'lumotlar muvaffaqiyatli ajratib olindi:")
        
        # Xabar hajmini xavfsiz (3000 belgidan) bo'laklarga bo'lib yuborish
        CHUNK_SIZE = 3000
        if len(result_text) > CHUNK_SIZE:
            for i in range(0, len(result_text), CHUNK_SIZE):
                chunk = result_text[i:i+CHUNK_SIZE]
                await update.message.reply_text(f"```json\n{chunk}\n```", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"```json\n{result_text}\n```", parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik yuz berdi: {str(e)}")

    restart_keyboard = [["▶️ Boshlash"]]
    await update.message.reply_text(
        "Yangi mahsulot kiritish uchun quyidagi tugmani bosing:",
        reply_markup=ReplyKeyboardMarkup(restart_keyboard, resize_keyboard=True, is_persistent=True)
    )
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Jarayon bekor qilindi.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def run_bot():
    application = ApplicationBuilder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(r"^▶️ Boshlash$"), ask_product_info),
            CommandHandler("start", ask_product_info)
        ],
        states={
            WAITING_INPUT: [
                MessageHandler(filters.Regex(r"^Done ✅$"), finish_and_process),
                MessageHandler(filters.PHOTO, collect_photos)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", start)],
        allow_reentry=True
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    
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
