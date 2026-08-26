import os
import logging
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from google import genai
from google.genai import types
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

# Qat'iy tahlil va HTML kartochka chiqarish uchun System Prompt
SYSTEM_PROMPT = """
Siz — e-commerce platformasi uchun Xitoy marketplace'laridan (Taobao/Pinduoduo/1688) olingan mahsulot ma'lumotlarini o'zbek tilidagi standart HTML kartochka formatiga to'liq o'girib beruvchi professional AI assistentsiz.

Rasm va skrinshotlar yuborilganda, har doim quyidagi qat'iy qoidalar va HTML strukturasi bo'yicha javob bering:

1. BARCHA MA'LUMOT VA RASMLARNI TO'LIQ QAMRAB OLISH:
   - Yuborilgan rasmlardagi ma'lumotlarni qisqartirmasdan, hech birini tushirib qoldirmasdan joylashtiring. "..." yoki "va hokazo" ishlatish QAT'IYAN MAN ETILADI.

2. TIL SIFATI:
   - Sof, ravon va tushunarli o'zbek tilidan foydalaning.
   - Inglizcha va xitoycha so'zlarni moslashtirib tarjima qiling (masalan: "Printed" -> "Naqshli", "Slip-on" -> "Yengil kiyiladigan poyabzal", "Rubber" -> "Kauchuk/Rezina").

3. RASMLAR TARTIBI:
   - Rasmlar direct link formatida bo'lsin.
   - A) MAHSULOT KO'RISH RASMLARI: <div class="images"> ichida joylashadi. Birinchi rasm asosiy (muqova) rasm.
   - B) SHARH RASMLARI: Faqat tegishli <div class="review"> bloki ichidagi <div class="review-images"> ostida joylashadi (asosiy galereyaga qo'shilmaydi).

4. VARIANT VA O'LCHAMLAR (SOTUVDAN CHIQGANLAR CHEKLOVI):
   - Xira (kulrang, faolsizlashtirilgan / tugagan) variant va o'lchamlarni <div class="variant"> ichiga QO'SHMANG. Faqat sotuvda bor faol o'lcham va ranglarni <span> teglarida taqdim eting.

5. KATALOG VA MAHSULOT TURLARI:
   - <span class="catalog"> va <span class="type"> qiymatlarini faqat standart ro'yxatdan olib ishlating (masalan: Erkaklar poyabzali, Ayollar poyabzali, Sport poyabzali, Kiyim-kechak, Elektronika va h.k.).

6. SHARH MUALLIFI ISMI:
   - <span class="author"> o'rniga faqat "ID: " hamda 10 xonali tasodifiy raqam yoziladi (masalan: <span class="author">ID: 4829104752</span>). Real ismlarni ishlatish taqiqlanadi.

7. STANDART HTML SHABLON STRUKTURASI (Faqat ushbu koddantashkil topgan toza javob qaytaring, ortiqcha izoh yozmang):

<div class="product">
  <div class="images">
    <img src="https://i.ibb.co/.../main.jpg">
    <img src="https://i.ibb.co/.../detail1.jpg">
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
    <span class="text">Sharh matni (O'zbek tilida)...</span>
    <div class="review-images">
      <img src="https://i.ibb.co/.../review_img.jpg">
    </div>
  </div>
</div>
"""

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
        f"⏳ Ma'lumotlarni ajratib olish va HTML kartochka yaratish boshlanmoqda..."
    )
    
    status_msg = await update.message.reply_text(report_msg, reply_markup=ReplyKeyboardRemove())

    # Gemini 3.6-Flash'ga barcha rasmlarni yuborib tahlil qilish
    try:
        contents = []
        for img in photos:
            contents.append(
                types.Part.from_bytes(
                    data=img,
                    mime_type="image/jpeg",
                )
            )

        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.2
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

        html_result = response.text.strip() if response.text else "Ma'lumot ajratib bo'lmadi."

        # Telegram kodi sifatida chiroyli ko'rinishi uchun HTML formatda yuboramiz
        final_text = f"```html\n{html_result}\n```"
        
        # Telegram xabar limiti (4096 belgi) dan oshsa bo'lib yuborish
        if len(final_text) <= 4000:
            await update.message.reply_text(final_text, parse_mode="Markdown")
        else:
            for i in range(0, len(final_text), 4000):
                await update.message.reply_text(final_text[i:i+4000], parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Tahlil jarayonida xatolik yuz berdi: {str(e)}")

def main():
    threading.Thread(target=run_health_check_server, daemon=True).start()
    
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.Regex("^✅ Done$"), handle_done))
    
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
