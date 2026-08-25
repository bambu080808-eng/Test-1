import os
import logging
import asyncio
import requests
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
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

# /start bosilganda
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['step1_images'] = []
    context.user_data['step2_images'] = []
    
    # Klaviatura joyida "▶️ Step 1 ni boshlash" tugmasi
    keyboard = [["▶️ Step 1 ni boshlash"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "Salom! Mahsulot rasmlarini URL havolalarga aylantirish botiga xush kelibsiz.",
        reply_markup=reply_markup
    )
    return ConversationHandler.END

# Step 1 tugmasi bosilganda
async def start_step1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['step1_images'] = []
    
    # Klaviatura joyida "Next ➡️" tugmasi chiqadi
    keyboard = [["Next ➡️"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "📸 **Step 1:** Iltimos, birinchi bosqich rasmlarini yuboring (bittalab yoki albom shaklida).\n\n"
        "Rasmlarni yuborib bo'lgach, pastdagi **Next ➡️** tugmasini bosing.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return STEP1

# Step 1 rasmlarini yig'ish
async def collect_step1_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    img_bytes = await file.download_as_bytearray()
    
    context.user_data['step1_images'].append(bytes(img_bytes))

# Next ➡️ tugmasi bosilganda (Step 2 ga o'tish)
async def to_step2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    count1 = len(context.user_data.get('step1_images', []))
    context.user_data['step2_images'] = []
    
    # Klaviatura joyida "Done ✅" tugmasi chiqadi
    keyboard = [["Done ✅"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        f"✅ Step 1 uchun **{count1} ta** rasm qabul qilindi!\n\n"
        f"📸 **Step 2:** Endi ikkinchi bosqich rasmlarini yuboring.\n\n"
        f"Rasmlarni yuborib bo'lgach, pastdagi **Done ✅** tugmasini bosing.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return STEP2

# Step 2 rasmlarini yig'ish
async def collect_step2_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    img_bytes = await file.download_as_bytearray()
    
    context.user_data['step2_images'].append(bytes(img_bytes))

# Done ✅ tugmasi bosilganda
async def finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    count1 = len(context.user_data.get('step1_images', []))
    count2 = len(context.user_data.get('step2_images', []))
    total = count1 + count2
    
    # Klaviaturani yopish
    reply_markup = ReplyKeyboardRemove()
    
    status_msg = await update.message.reply_text(
        f"🎉 Jami **{total} ta** rasm qabul qilindi (Step 1: {count1} ta, Step 2: {count2} ta).\n\n"
        f"⏳ Barcha rasmlar uchun URL havolalar tayyorlanmoqda, kuting...",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    
    # Step 1 URL lari
    step1_urls = []
    for img in context.user_data.get('step1_images', []):
        try:
            url = upload_to_freeimage(img)
            step1_urls.append(url)
        except Exception as e:
            step1_urls.append(f"Xatolik: {str(e)}")
            
    # Step 2 URL lari
    step2_urls = []
    for img in context.user_data.get('step2_images', []):
        try:
            url = upload_to_freeimage(img)
            step2_urls.append(url)
        except Exception as e:
            step2_urls.append(f"Xatolik: {str(e)}")
            
    res_text1 = "🔹 **STEP 1 URLs:**\n" + ("\n".join(step1_urls) if step1_urls else "Rasm yuborilmadi.")
    res_text2 = "🔹 **STEP 2 URLs:**\n" + ("\n".join(step2_urls) if step2_urls else "Rasm yuborilmadi.")
    
    await status_msg.edit_text("✅ Barcha havolalar tayyor bo'ldi!")
    await update.message.reply_text(res_text1, disable_web_page_preview=True, parse_mode="Markdown")
    await update.message.reply_text(res_text2, disable_web_page_preview=True, parse_mode="Markdown")
    
    # Qayta boshlash uchun tugma
    restart_keyboard = [["▶️ Step 1 ni boshlash"]]
    await update.message.reply_text(
        "Yangi rasmlar yuklash uchun tugmani bosing:",
        reply_markup=ReplyKeyboardMarkup(restart_keyboard, resize_keyboard=True)
    )
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Jarayon bekor qilindi.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def run_bot():
    application = ApplicationBuilder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^▶️ Step 1 ni boshlash$"), start_step1)],
        states={
            STEP1: [
                MessageHandler(filters.PHOTO, collect_step1_images),
                MessageHandler(filters.Regex("^Next ➡️$"), to_step2)
            ],
            STEP2: [
                MessageHandler(filters.PHOTO, collect_step2_images),
                MessageHandler(filters.Regex("^Done ✅$"), finish)
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
