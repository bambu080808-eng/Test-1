"""Google Gemini API bilan ishlash: skrinshotlar + URL lardan HTML kartochka yasash."""
import re

from google import genai
from google.genai import types

from config import GEMINI_API_KEY, GEMINI_MODEL
from prompts import SYSTEM_PROMPT, build_user_message

_client = genai.Client(api_key=GEMINI_API_KEY)

_CODE_FENCE_RE = re.compile(r"^```(?:html)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


class AIGenerationError(Exception):
    pass


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = _CODE_FENCE_RE.sub("", text).strip()
    return text


def generate_product_html(
    info_images: list[bytes],
    gallery_urls: list[str],
    review_urls: list[str],
) -> str:
    """
    info_images: mahsulot ma'lumotlari ko'rsatilgan skrinshotlar (jpeg/png bytes)
    gallery_urls: imgbb'ga oldindan yuklangan mahsulot rasmlari URL lari
    review_urls: imgbb'ga oldindan yuklangan sharh rasmlari URL lari
    """
    if not info_images:
        raise AIGenerationError("Mahsulot ma'lumotlari skrinshotlari berilmagan.")

    parts = [
        types.Part.from_bytes(data=img, mime_type="image/jpeg") for img in info_images
    ]
    parts.append(types.Part.from_text(text=build_user_message(gallery_urls, review_urls)))

    try:
        resp = _client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[types.Content(role="user", parts=parts)],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=8000,
            ),
        )
    except Exception as e:  # google-genai SDK xatoliklari (rate limit, auth, va h.k.)
        raise AIGenerationError(f"Gemini API bilan bog'lanishda xatolik: {e}") from e

    html = _strip_fences(resp.text or "")

    if "<div" not in html or "product" not in html.split(">", 1)[0]:
        raise AIGenerationError(
            "AI kutilgan HTML formatida javob bermadi. Qayta urinib ko'ring yoki "
            "skrinshotlar aniqroq/to'liqroq bo'lishiga ishonch hosil qiling."
        )

    return html
