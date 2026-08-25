import os
import logging
import asyncio
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
)

# Log sozlamalari
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = os.environ.get("BOT_TOKEN") or "7857867174:AAEghTH8fqeItdfZSFbxy1JP9KytrMdS6mgc"
FREEIMAGE_API_KEY = os.environ.get("FREEIMAGE_API_KEY") or "6d207e02198a847aa98d0a2a901485a5"

# Holatlar (States)
STEP1, STEP2 = range(2)

def upload_to_freeimage(img_bytes: bytes) -> str:
    """FreeImage.host API orqali yuklash"""
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

# /start komandasi
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Foydalanuvchi ma'lumotlarini tozalash
    context.user_data['step1_images'] = []
    context.user_data['step2_images'] = []
    
    keyboard = [[InlineKeyboardButton("▶️ Step 1 ni boshlash", callback_data="start_step1")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Salom! Mahsulot rasmlarini URL havolalarga aylantirish botiga xush kelibsiz.",
        reply_markup=reply_markup
    )
    return ConversationHandler.END

# Step 1 boshlanishi
async def start_step1_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    context.user_data['step1_images'] = []
    
    await query.message.reply_text(
        "📸 **Step 1:** Iltimos, birinchi bosqich rasmlarini yuboring (bittalab yoki albom shaklida).\n\n"
        "Rasmlarni yuborib bo'lgach, pastdagi **Next ➡️** tugmasini bosing."
    )
    return STEP1

# Step 1 rasmlarini qabul qilish
async def collect_step1_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    img_bytes = await file.download_as_bytearray()
    
    context.user_data['step1_images'].append(bytes(img_bytes))
    
    # Tugma faqat bir marta ko'rinishi uchun (agar albom bo'lsa)
    if not context.user_data.get('step1_msg_sent'):
        keyboard = [[InlineKeyboardButton("Next ➡️", callback_data="to_step2")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Rasmlar qabul qilinmoqda... Tugagach Next tugmasini bosing:", reply_markup=reply_markup)
        context.user_data['step1_msg_sent'] = True

# Step 2 ga o'tish
async def to_step2_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    count1 = len(context.user_data.get('step1_images', []))
    context.user_data['step1_msg_sent'] = False
    context.user_data['step2_images'] = []
    
    await query.message.reply_text(
        f"✅ Step 1 uchun **{count1} ta** rasm qabul qilindi!\n\n"
        f"📸 **Step 2:** Endi ikkinchi bosqich rasmlarini yuboring.\n\n"
        f"Rasmlarni yuborib bo'lgach, **Done ✅** tugmasini bosing."
    )
    return STEP2

# Step 2 rasmlarini qabul qilish
async def collect_step2_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    img_bytes = await file.download_as_bytearray()
    
    context.user_data['step2_images'].append(bytes(img_bytes))
    
    if not context.user_data.get('step2_msg_sent'):
        keyboard = [[InlineKeyboardButton("Done ✅", callback_data="finish")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Rasmlar qabul qilinmoqda... Tugagach Done tugmasini bosing:", reply_markup=reply_markup)
        context.user_data['step2_msg_sent'] = True

# Yakunlash va URL'larni generatsiya qilish
async def finish_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    count1 = len(context.user_data.get('step1_images', []))
    count2 = len(context.user_data.get('step2_images', []))
    total = count1 + count2
    
    status_msg = await query.message.reply_text(
        f"🎉 Jami **{total} ta** rasm qabul qilindi (Step 1: {count1} ta, Step 2: {count2} ta).\n\n"
        f"⏳ Barcha rasmlar uchun URL havolalar tayyorlanmoqda, kuting..."
    )
    
    # Step 1 URL larini yuklash
    step1_urls = []
    for img in context.user_data.get('step1_images', []):
        try:
            url = upload_to_freeimage(img)
            step1_urls.append(url)
        except Exception as e:
            step1_urls.append(f"Xatolik: {str(e)}")
            
    # Step 2 URL larini yuklash
    step2_urls = []
    for img in context.user_data.get('step2_images', []):
        try:
            url = upload_to_freeimage(img)
            step2_urls.append(url)
        except Exception as e:
            step2_urls.append(f"Xatolik: {str(e)}")
            
    # Natijalarni chiqarish
    res_text1 = "🔹 **STEP 1 URLs:**\n" + ("\n".join(step1_urls) if step1_urls else "Rasm yuborilmadi.")
    res_text2 = "🔹 **STEP 2 URLs:**\n" + ("\n".join(step2_urls) if step2_urls else "Rasm yuborilmadi.")
    
    await status_msg.edit_text("✅ Barcha havolalar tayyor bo'ldi!")
    await query.message.reply_text(res_text1, disable_web_page_preview=True)
    await query.message.reply_text(res_text2, disable_web_page_preview=True)
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Jarayon bekor qilindi.")
    return ConversationHandler.END

async def run_bot():
    application = ApplicationBuilder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_step1_callback, pattern="^start_step1$")],
        states={
            STEP1: [
                MessageHandler(filters.PHOTO, collect_step1_images),
                CallbackQueryHandler(to_step2_callback, pattern="^to_step2$")
            ],
            STEP2: [
                MessageHandler(filters.PHOTO, collect_step2_images),
                CallbackQueryHandler(finish_callback, pattern="^finish$")
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", start)]
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
