"""
Bot 2 — mahsulot yuklash jarayonini soddalashtiruvchi Telegram bot.

Workflow:
  /start
   -> "Mahsulot rasimlarini yuklash" tugmasi
   -> mahsulot rasimlari (bittalab yoki albom)
   -> "Kamentariya rasimlariga o'tish" tugmasi
   -> kamentariya (sharh) rasimlari (ixtiyoriy)
   -> "Mahsulot ma'lumotlari rasimlariga o'tish" tugmasi
   -> mahsulot ma'lumotlari skrinshotlari
   -> "✅ Tayyor" tugmasi
   -> (fon jarayoni) imgbb ga yuklash -> Gemini AI -> HTML parse -> Supabase'ga yozish
   -> natija haqida xabar
"""
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

from config import TELEGRAM_BOT_TOKEN, ADMIN_CHAT_IDS, MAX_INFO_IMAGES
from imgbb_client import upload_images, ImgbbUploadError
from gemini_client import generate_product_html, AIGenerationError
from html_parser import parse_product_html, ParseError
from supabase_client import insert_product, SupabaseInsertError

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# --- Conversation states ---
MENU, PRODUCT_IMAGES, REVIEW_IMAGES, INFO_IMAGES = range(4)


def _is_allowed(update: Update) -> bool:
    if not ADMIN_CHAT_IDS:
        return True
    user = update.effective_user
    return bool(user and user.id in ADMIN_CHAT_IDS)


async def _get_photo_bytes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bytes | None:
    """Oddiy rasm (compressed photo) yoki fayl sifatida yuborilgan rasmni (Document.IMAGE) o'qiydi."""
    message = update.message
    file_id = None
    if message.photo:
        file_id = message.photo[-1].file_id  # eng katta o'lchamdagisi
    elif message.document and (message.document.mime_type or "").startswith("image/"):
        file_id = message.document.file_id

    if not file_id:
        return None

    tg_file = await context.bot.get_file(file_id)
    return bytes(await tg_file.download_as_bytearray())


# ------------------------------------------------------------------ /start --
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _is_allowed(update):
        await update.message.reply_text("⛔️ Sizda ushbu botdan foydalanish huquqi yo'q.")
        return ConversationHandler.END

    context.user_data.clear()
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🖼 Mahsulot rasimlarini yuklash", callback_data="start_product")]]
    )
    await update.message.reply_text(
        "Assalomu alaykum! Yangi mahsulot qo'shish uchun quyidagi tugmani bosing.",
        reply_markup=keyboard,
    )
    return MENU


# ------------------------------------------------------------- MENU state --
async def on_start_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["product_images"] = []
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("➡️ Kamentariya rasimlariga o'tish", callback_data="to_review")]]
    )
    await query.edit_message_text(
        "📦 Mahsulot rasimlarini yuboring (bittalab yoki albom holida yuborsangiz ham bo'ladi).\n"
        "Tugatgach, pastdagi tugmani bosing.",
        reply_markup=keyboard,
    )
    return PRODUCT_IMAGES


# ------------------------------------------------------ PRODUCT_IMAGES state --
async def on_product_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    photo_bytes = await _get_photo_bytes(update, context)
    if photo_bytes is None:
        await update.message.reply_text("Iltimos, rasm yuboring 🙂")
        return PRODUCT_IMAGES

    context.user_data.setdefault("product_images", []).append(photo_bytes)
    n = len(context.user_data["product_images"])
    await update.message.reply_text(f"✅ Qabul qilindi. Jami: {n} ta mahsulot rasmi.")
    return PRODUCT_IMAGES


async def on_product_other(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Iltimos, mahsulot rasmini yuboring yoki tugatgan bo'lsangiz "
        "'➡️ Kamentariya rasimlariga o'tish' tugmasini bosing."
    )
    return PRODUCT_IMAGES


async def on_to_review(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not context.user_data.get("product_images"):
        await query.answer("Kamida 1 ta mahsulot rasmi yuboring!", show_alert=True)
        return PRODUCT_IMAGES

    await query.answer()
    context.user_data["review_images"] = []
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("➡️ Mahsulot ma'lumotlari rasimlariga o'tish", callback_data="to_info")]]
    )
    await query.edit_message_text(
        "💬 Endi kamentariya (sharh) uchun rasimlarni yuboring.\n"
        "Agar sharh rasmlari bo'lmasa, shunchaki pastdagi tugmani bosing.",
        reply_markup=keyboard,
    )
    return REVIEW_IMAGES


# ------------------------------------------------------- REVIEW_IMAGES state --
async def on_review_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    photo_bytes = await _get_photo_bytes(update, context)
    if photo_bytes is None:
        await update.message.reply_text("Iltimos, rasm yuboring 🙂")
        return REVIEW_IMAGES

    context.user_data.setdefault("review_images", []).append(photo_bytes)
    n = len(context.user_data["review_images"])
    await update.message.reply_text(f"✅ Qabul qilindi. Jami: {n} ta kamentariya rasmi.")
    return REVIEW_IMAGES


async def on_review_other(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Iltimos, kamentariya rasmini yuboring yoki tugatgan bo'lsangiz "
        "'➡️ Mahsulot ma'lumotlari rasimlariga o'tish' tugmasini bosing."
    )
    return REVIEW_IMAGES


async def on_to_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["info_images"] = []
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Tayyor", callback_data="done")]])
    await query.edit_message_text(
        "🧾 Endi mahsulot ma'lumotlari ko'rsatilgan skrinshotlarni yuboring "
        "(narx, nomi, tavsifi, variantlari, sharhlar va h.k.).\n"
        "Tugatgach ✅ Tayyor tugmasini bosing.",
        reply_markup=keyboard,
    )
    return INFO_IMAGES


# --------------------------------------------------------- INFO_IMAGES state --
async def on_info_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    photo_bytes = await _get_photo_bytes(update, context)
    if photo_bytes is None:
        await update.message.reply_text("Iltimos, rasm yuboring 🙂")
        return INFO_IMAGES

    images = context.user_data.setdefault("info_images", [])
    if len(images) >= MAX_INFO_IMAGES:
        await update.message.reply_text(
            f"⚠️ Maksimal {MAX_INFO_IMAGES} ta ma'lumot skrinshoti qabul qilinadi. "
            f"Yetarli bo'lsa ✅ Tayyor tugmasini bosing."
        )
        return INFO_IMAGES

    images.append(photo_bytes)
    await update.message.reply_text(f"✅ Qabul qilindi. Jami: {len(images)} ta ma'lumot skrinshoti.")
    return INFO_IMAGES


async def on_info_other(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Iltimos, mahsulot ma'lumotlari skrinshotini yuboring yoki tugatgan bo'lsangiz "
        "✅ Tayyor tugmasini bosing."
    )
    return INFO_IMAGES


async def on_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query

    info_images = context.user_data.get("info_images", [])
    if not info_images:
        await query.answer("Kamida 1 ta ma'lumot skrinshoti yuboring!", show_alert=True)
        return INFO_IMAGES

    await query.answer()
    await query.edit_message_text("⏳ Mahsulot bazaga joylanmoqda, biroz kuting...")

    product_images = context.user_data.get("product_images", [])
    review_images = context.user_data.get("review_images", [])

    try:
        gallery_urls = upload_images(product_images)
        review_urls = upload_images(review_images) if review_images else []

        html = generate_product_html(info_images, gallery_urls, review_urls)
        parsed = parse_product_html(html)
        saved = insert_product(parsed)

        name = parsed.get("name") or "(nomsiz)"
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"✅ Mahsulot bazaga muvaffaqiyatli joylandi!\n\n📦 <b>{name}</b>",
            parse_mode=ParseMode.HTML,
        )
        logger.info("Product saved: id=%s name=%s", saved.get("id"), name)

    except ImgbbUploadError as e:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"❌ Rasmlarni yuklashda xatolik yuz berdi:\n{e}\n\nQaytadan /start bosib urinib ko'ring.",
        )
    except AIGenerationError as e:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"❌ AI mahsulot ma'lumotlarini ajratib ololmadi:\n{e}\n\nQaytadan /start bosib urinib ko'ring.",
        )
    except ParseError as e:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"❌ AI javobini o'qishda xatolik:\n{e}\n\nQaytadan /start bosib urinib ko'ring.",
        )
    except SupabaseInsertError as e:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"❌ Bazaga yozishda xatolik yuz berdi:\n{e}\n\nQaytadan /start bosib urinib ko'ring.",
        )
    except Exception as e:  # kutilmagan xatolik — foydalanuvchi jarayon "osilib qolmasligi" uchun
        logger.exception("Kutilmagan xatolik")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"❌ Kutilmagan xatolik yuz berdi: {e}\n\nQaytadan /start bosib urinib ko'ring.",
        )
    finally:
        context.user_data.clear()

    return ConversationHandler.END


# -------------------------------------------------------------- fallback ----
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("❌ Bekor qilindi. Qayta boshlash uchun /start bosing.")
    return ConversationHandler.END


async def unknown_in_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Boshlash uchun tugmani bosing yoki /start yuboring.")
    return MENU


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Update %s ishlov berishda xatolik: %s", update, context.error, exc_info=context.error)
    if isinstance(update, Update) and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ Kutilmagan texnik xatolik yuz berdi. Iltimos /start bilan qaytadan boshlang.",
            )
        except Exception:
            pass


def main() -> None:
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MENU: [
                CallbackQueryHandler(on_start_product, pattern="^start_product$"),
                MessageHandler(filters.ALL & ~filters.COMMAND, unknown_in_menu),
            ],
            PRODUCT_IMAGES: [
                MessageHandler(filters.PHOTO | filters.Document.IMAGE, on_product_photo),
                CallbackQueryHandler(on_to_review, pattern="^to_review$"),
                MessageHandler(filters.ALL & ~filters.COMMAND, on_product_other),
            ],
            REVIEW_IMAGES: [
                MessageHandler(filters.PHOTO | filters.Document.IMAGE, on_review_photo),
                CallbackQueryHandler(on_to_info, pattern="^to_info$"),
                MessageHandler(filters.ALL & ~filters.COMMAND, on_review_other),
            ],
            INFO_IMAGES: [
                MessageHandler(filters.PHOTO | filters.Document.IMAGE, on_info_photo),
                CallbackQueryHandler(on_done, pattern="^done$"),
                MessageHandler(filters.ALL & ~filters.COMMAND, on_info_other),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv)
    app.add_error_handler(error_handler)

    logger.info("Bot ishga tushdi (polling)...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()


import os
from threading import Thread
from flask import Flask

# Render portini aldamchi server bilan band qilish
flask_app = Flask('')

@flask_app.route('/')
def home():
    return "Bot status: Active"

def run_http():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_http)
    t.daemon = True
    t.start()

# Botni ishga tushirish qismi
if __name__ == '__main__':
    keep_alive()  # Soxta serverni yoqamiz
    
    # Shu yerdan pastda sizning mavjud botni run/polling qilish kodingiz turadi:
    # masalan: application.run_polling() yoki app.run_polling()

