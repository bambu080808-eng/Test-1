"""
Bot 1'ning admin panelidagi parseAndInsertProduct() funksiyasi bilan AYNAN bir
xil mantiqda AI qaytargan <div class="product">...</div> HTML kodini
maydonlarga ajratadi. (Manba: Bot 1 HTML fayli, parseAndInsertProduct().)

Bot 1 raw HTML'ni saqlamaydi — u kodni o'qib, quyidagi qiymatlarni ajratib
oladi va Supabase'dagi 5 ta jadvalga (catalogs, product_types, products,
product_variants, reviews) yozadi. Shuning uchun bu yerda ham xuddi shunday
qilinadi — catalog_id/type_id keyinroq supabase_client.py da hal qilinadi
(chunki ular alohida jadvaldan lookup-or-create talab qiladi).
"""
import re

from bs4 import BeautifulSoup


class ParseError(Exception):
    pass


def _clean_price(text: str) -> float:
    # Bot 1: parseFloat(text.replace(/[^\d.]/g,"")) || 0
    digits = re.sub(r"[^\d.]", "", text or "")
    try:
        return float(digits) if digits else 0.0
    except ValueError:
        return 0.0


def parse_product_html(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    product = soup.select_one(".product") or soup.body or soup

    images = [img.get("src", "").strip() for img in product.select(".images img")]
    images = [u for u in images if u]

    price_el = product.select_one(".price")
    price = _clean_price(price_el.get_text() if price_el else "0")

    name_el = product.select_one(".name")
    name = name_el.get_text(strip=True) if name_el else "Nomsiz mahsulot"

    desc_el = product.select_one(".desc")
    description = desc_el.get_text(strip=True) if desc_el else ""

    catalog_el = product.select_one(".catalog")
    catalog_name = catalog_el.get_text(strip=True) if catalog_el else ""

    type_el = product.select_one(".type")
    type_name = type_el.get_text(strip=True) if type_el else ""

    stats = {}
    for span in product.select(".stats span[data-key]"):
        key = span.get("data-key")
        if key:
            stats[key] = span.get_text(strip=True)

    extra = {}
    for div in product.select(".extra[data-key]"):
        key = div.get("data-key")
        if key:
            extra[key] = div.get_text(strip=True)

    variants = []
    for v in product.select(".variant"):
        options = [s.get_text(strip=True) for s in v.select("span")]
        variants.append({"variant_type": v.get("data-type", ""), "options": options})

    reviews = []
    for r in product.select(".review"):
        author_el = r.select_one(".author")
        text_el = r.select_one(".text")
        rimgs = [img.get("src", "").strip() for img in r.select(".review-images img")]
        reviews.append(
            {
                "author": author_el.get_text(strip=True) if author_el else "Foydalanuvchi",
                "text": text_el.get_text(strip=True) if text_el else "",
                "images": [u for u in rimgs if u],
            }
        )

    def _int(val, default=0):
        try:
            return int(float(val))
        except (TypeError, ValueError):
            return default

    def _float(val, default=5.0):
        try:
            return float(val)
        except (TypeError, ValueError):
            return default

    return {
        "name": name,
        "price": price,
        "description": description,
        "catalog_name": catalog_name,
        "type_name": type_name,
        "images": images,
        "extra": extra,
        "rating": _float(stats.get("rating"), 5.0),
        "reviews_count": _int(stats.get("reviews"), 0),
        "views_count": _int(stats.get("views"), 0),
        "likes_count": _int(stats.get("likes"), 0),
        "sold_count": _int(stats.get("sold"), 0),
        "variants": variants,
        "reviews": reviews,
    }
