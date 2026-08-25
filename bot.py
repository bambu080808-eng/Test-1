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

# Gemini klienta
client = genai.Client(api_key=GEMINI_API_KEY)

WAITING_INPUT = range(1)
LOCK = asyncio.Lock()

SYSTEM_PROMPT = """
Siz — e-commerce platformasi uchun Xitoy marketplace'laridan (Taobao/Pinduoduo/1688) olingan mahsulot ma'lumotlarini o'zbek tilidagi standart HTML kartochka formatiga me'yoriy va to'liq o'girib beruvchi professional AI assistentsiz.
Rasm, matn, havolalar (URL) yoki skrinshotlar yuborilganda, har doim quyidagi qat'iy qoidalar va HTML strukturasi bo'yicha javob bering:

1. CHEKSIZ MA'LUMOT VA RASMLARNI TO'LIQ QAMRAB OLISH:
Foydalanuvchi qancha mahsulot rasmi, sharh matni yoki sharh rasmlarini yubormasin — ularning barchasini QISQARTIRMASDAN, HECH BIRINI TUSHIRIB QOLDIRMASDAN joylashtiring. "va hokazo", "..." kabi qisqartirishlar qilish QAT'IYAN MAN ETILADI.

2. TIL VA TILSHUNOSLIK QOIDASI:
Barcha matnlar, xususiyatlar hamda sharhlar faqat sof, ravon va tushunarli o'zbek tilida bo'lishi shart. Inglizcha yoki xitoycha so'zlarni moslashtirib tarjima qiling.

3. RASMLARNI INTEGRATSIYA QILISH VA TARTIBI:
Barcha rasmlar to'g'ridan-to'g'ri o'zingizga kelgan rasmlardan foydalanib yoki qabul qilingan havolalar asosida 2 ta mustaqil guruhga ajratiladi:
A) MAHSULOT KO'RISH RASMLARI (Galereya): HTML blokining eng boshida, <div class="images"> ichida joylashadi. Birinchi turgan <img> — asosiy (muqova) rasm. Barcha rasmlar shu yerga kiritiladi.
B) SHARH (KOMMENTARIYA) RASMLARI: Faqat tegishli <div class="review"> bloki ichida, muallif (<span class="author">) va matn (<span class="text">) dan KEYIN, <div class="review-images"> ostida joylashadi.

4. VARIANT VA O'LCHAMLARNI TAHLIL QILISH:
Faqat sotuvda bor (aniq, to'q shriftli, faol) o'lcham va ranglarni <span> teglarida taqdim eting. Xira yoki tugaganlarini qo'shmang.

5. KATALOG VA MAHSULOT TURLARI STANDARTLARI:
<span class="catalog"> va <span class="type"> qiymatlarini faqat quyidagi tasdiqlangan ro'yxatdan oling:
Poyabzallar: Erkaklar poyabzali, Ayollar poyabzali, Bolalar poyabzali, Uy poyabzali (Shlepka va tapchkalar), Sport poyabzali (Krosovka va kedalar), Slip-on va mokasinalar.
Kiyim-kechak: Erkaklar kiyimi / Ayollar kiyimi / Bolalar kiyimi, Ichki kiyim va paypoqlar / Ustki kiyim (Kurtka, palto).
Sumka va Aksessuarlar: Ayollar sumkasi / Erkaklar sumkasi va hamyonlar / Ryukzaklar / Kamar va soatlar / Ko'zoynaklar va zargarlik buyumlari.
Uy-ro'zg'or buyumlari: Oshxona jihozlari / Hammom va hojatxona buyumlari / Uy dekori va yoritgichlar / Tozalash va tartibga solish vositalari.
Maishiy texnika va Elektronika: Kichik maishiy texnika / Telefon va gadjet aksessuarlari / Go'zallik va parvarish texnikasi.

6. SHARH MUALLIFI ISMINI ID FORMATIDA YOZISH:
Sharh qoldirgan har bir xaridorning ismi (<span class="author">) o'rniga faqat va faqat "ID: " so'zi hamda 10 xonali tasodifiy raqam biriktirib yoziladi (masalan: <span class="author">ID: 4829104752</span>).

7. STANDART HTML SHABLON STRUKTURASI:
Javobni FAQAT quyidagi strukturada, ortiqcha gaplarsiz taqdim eting:
<div class="product">
  <div class="images">
    <img src="...">
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
      <img src="...">
    </div>
  </div>
</div>
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['media_list'] = []
    
    keyboard = [["▶️ Boshlash"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)
    
    if update.message:
        await update.message.reply_text(
            "Salom! Mahsulot ma'lumotlari va rasmlarini yuboring. Tayyor bo'lgach **Done ✅** tugmasini bosing.",
            reply_markup=reply_markup
        )
    return ConversationHandler.END

async def ask_product_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['media_list'] = []
    
    keyboard = [["Done ✅"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)
    
    await update.message.reply_text(
        "📥 Iltimos, mahsulotga tegishli barcha ma'lumotlarni, matnlarni va rasmlarni yuboring "
        "(albom, bittalab yoki aralash ko'rinishda).\n\n"
        "Barcha rasm va ma'lumotlarni yuborib bo'lgach, pastdagi **Done ✅** tugmasini bosing.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return WAITING_INPUT

async def collect_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with LOCK:
        # Agar rasm kelsa
        if update.message.photo:
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            img_bytes = await file.download_as_bytearray()
            context.user_data.setdefault('media_list', []).append({
                "type": "photo", 
                "data": bytes(img_bytes)
            })
        
        # Agar matn kelsa
        if update.message.text and update.message.text != "Done ✅":
            context.user_data.setdefault('media_list', []).append({
                "type": "text", 
                "data": update.message.text
            })

async def finish_and_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    media_list = context.user_data.get('media_list', [])
    total_sent = len(media_list)
    
    if total_sent == 0:
        await update.message.reply_text("⚠️ Siz hali hech qanday rasm yoki ma'lumot yubormadingiz!")
        return WAITING_INPUT

    await update.message.reply_text(
        f"📊 **Hisobot:**\n"
        f"• Yuborilgan elementlar (rasm/matn): **{total_sent} ta**\n"
        f"• Qabul qilib olindi: **{total_sent} ta**\n\n"
        f"⏳ Ma'lumotlar tahlil qilinmoqda va Gemini orqali HTML kartochka tayyorlanmoqda, iltimos kuting...",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )

    try:
        # Gemini uchun kontent tayyorlaymiz
        contents = [SYSTEM_PROMPT]
        
        for item in media_list:
            if item["type"] == "photo":
                contents.append(client.types.Part.from_bytes(
                    data=item["data"],
                    mime_type='image/jpeg',
                ))
            elif item["type"] == "text":
                contents.append(item["data"])

        # Gemini modeliga so'rov yuborish (gemini-2.5-flash yoki mos model)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=contents,
        )
        
        html_output = response.text

        await update.message.reply_text("✅ Ma'lumotlar muvaffaqiyatli ajratib olindi va tayyorlandi!")
        
        # Uzun HTML'ni xavfsiz yuborish uchun bo'laklaymiz yoki code block qilib tashlaymiz
        if len(html_output) > 4000:
            for i in range(0, len(html_output), 4000):
                await update.message.reply_text(f"```html\n{html_output[i:i+4000]}\n```", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"```html\n{html_output}\n```", parse_mode="Markdown")

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
                MessageHandler(filters.PHOTO | filters.TEXT & ~filters.COMMAND, collect_data)
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
