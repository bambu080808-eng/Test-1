"""
Barcha muhit o'zgaruvchilari (environment variables) shu yerda o'qiladi.
Render'da "Environment" bo'limiga shu nomlar bilan qiymatlarni kiritasiz.
"""
import os

def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"'{name}' muhit o'zgaruvchisi topilmadi. Render dashboard -> Environment "
            f"bo'limiga uni qo'shing."
        )
    return value


# --- Majburiy (shularsiz bot ishga tushmaydi) ---
TELEGRAM_BOT_TOKEN = _require("TELEGRAM_BOT_TOKEN")
IMGBB_API_KEY = _require("IMGBB_API_KEY")
GEMINI_API_KEY = _require("GEMINI_API_KEY")
SUPABASE_URL = _require("SUPABASE_URL")
SUPABASE_KEY = _require("SUPABASE_KEY")

# --- Ixtiyoriy (default qiymatlar bilan) ---
# Gemini modeli. Kerak bo'lsa Render Environment'da GEMINI_MODEL bilan almashtirishingiz mumkin
# (masalan "gemini-3.5-flash" yangiroq va kuchliroq model uchun).
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# Botdan faqat ma'lum foydalanuvchilar foydalansin desangiz, telegram user_id larni
# vergul bilan ajratib shu yerga yozing (masalan: "123456789,987654321").
# Bo'sh qoldirilsa — hammaga ochiq bo'ladi.
_admin_raw = os.environ.get("ADMIN_CHAT_IDS", "").strip()
ADMIN_CHAT_IDS = [int(x) for x in _admin_raw.split(",") if x.strip()] if _admin_raw else []

# Bitta AI so'roviga qancha "ma'lumot skrinshoti" yuborish mumkinligi (xarajat/token nazorati uchun)
MAX_INFO_IMAGES = int(os.environ.get("MAX_INFO_IMAGES", "12"))
