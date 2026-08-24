"""imgbb.com ga rasm yuklab, to'g'ridan-to'g'ri (direct) URL olish."""
import base64
import requests

from config import IMGBB_API_KEY

IMGBB_ENDPOINT = "https://api.imgbb.com/1/upload"


class ImgbbUploadError(Exception):
    pass


def upload_image(image_bytes: bytes, timeout: int = 60) -> str:
    """Bitta rasmni imgbb ga yuklaydi va uning direct-link URL ini qaytaradi."""
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    try:
        resp = requests.post(
            IMGBB_ENDPOINT,
            data={"key": IMGBB_API_KEY, "image": b64},
            timeout=timeout,
        )
    except requests.RequestException as e:
        raise ImgbbUploadError(f"imgbb ga ulanishda xatolik: {e}") from e

    if resp.status_code != 200:
        raise ImgbbUploadError(f"imgbb xatolik qaytardi (status {resp.status_code}): {resp.text[:300]}")

    data = resp.json()
    if not data.get("success"):
        raise ImgbbUploadError(f"imgbb rasmni qabul qilmadi: {data}")

    # "url" — https://i.ibb.co/... ko'rinishidagi direct link
    return data["data"]["url"]


def upload_images(images_bytes: list[bytes]) -> list[str]:
    """Bir nechta rasmni ketma-ket yuklab, URL lar ro'yxatini tartib bo'yicha qaytaradi."""
    urls = []
    for i, img in enumerate(images_bytes, start=1):
        try:
            urls.append(upload_image(img))
        except ImgbbUploadError as e:
            raise ImgbbUploadError(f"{i}-rasmni yuklashda xatolik: {e}") from e
    return urls
