"""
Bot 1'ning admin panelidagi parseAndInsertProduct() bilan AYNAN bir xil
tartibda Supabase'ga yozadi (manba: Bot 1 HTML fayli):

  1. catalogs        -> {name}                 (lookup by name, yo'q bo'lsa insert)
  2. product_types    -> {name, catalog_id}     (lookup by name+catalog_id, yo'q bo'lsa insert)
  3. products         -> {name, price, description, catalog_id, type_id,
                          images, extra, rating, reviews_count, views_count,
                          likes_count, sold_count}
  4. product_variants -> {product_id, variant_type, options}   (har variant uchun)
  5. reviews          -> {product_id, author, text, images}    (har sharh uchun)

Jadval/ustun nomlari Bot 1'dagi haqiqiy kod bilan bir xil — hech narsani
taxmin qilish shart bo'lmadi.
"""
from supabase import create_client, Client

from config import SUPABASE_URL, SUPABASE_KEY

_supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


class SupabaseInsertError(Exception):
    pass


def _get_or_create_catalog(name: str) -> str | None:
    if not name:
        return None
    res = _supabase.table("catalogs").select("*").eq("name", name).maybe_single().execute()
    if res and res.data:
        return res.data["id"]
    ins = _supabase.table("catalogs").insert({"name": name}).execute()
    if not ins.data:
        raise SupabaseInsertError(f"catalog qo'shishda xato: {name}")
    return ins.data[0]["id"]


def _get_or_create_type(name: str, catalog_id: str | None) -> str | None:
    if not name:
        return None
    query = _supabase.table("product_types").select("*").eq("name", name)
    query = query.eq("catalog_id", catalog_id) if catalog_id is not None else query.is_("catalog_id", "null")
    res = query.maybe_single().execute()
    if res and res.data:
        return res.data["id"]
    ins = _supabase.table("product_types").insert({"name": name, "catalog_id": catalog_id}).execute()
    if not ins.data:
        raise SupabaseInsertError(f"product_type qo'shishda xato: {name}")
    return ins.data[0]["id"]


def insert_product(parsed: dict) -> dict:
    """
    parsed — html_parser.parse_product_html() natijasi.
    Muvaffaqiyatli bo'lsa, yaratilgan products qatorini qaytaradi.
    """
    try:
        catalog_id = _get_or_create_catalog(parsed["catalog_name"])
        type_id = _get_or_create_type(parsed["type_name"], catalog_id)

        product_row = {
            "name": parsed["name"],
            "price": parsed["price"],
            "description": parsed["description"],
            "catalog_id": catalog_id,
            "type_id": type_id,
            "images": parsed["images"],
            "extra": parsed["extra"],
            "rating": parsed["rating"],
            "reviews_count": parsed["reviews_count"],
            "views_count": parsed["views_count"],
            "likes_count": parsed["likes_count"],
            "sold_count": parsed["sold_count"],
        }
        ins = _supabase.table("products").insert(product_row).execute()
        if not ins.data:
            raise SupabaseInsertError("mahsulot qo'shishda xato: bo'sh javob qaytdi")
        product = ins.data[0]

        for v in parsed["variants"]:
            r = (
                _supabase.table("product_variants")
                .insert(
                    {
                        "product_id": product["id"],
                        "variant_type": v["variant_type"],
                        "options": v["options"],
                    }
                )
                .execute()
            )
            if getattr(r, "data", None) is None:
                raise SupabaseInsertError(f"variant qo'shishda xato: {v['variant_type']}")

        for r_item in parsed["reviews"]:
            r = (
                _supabase.table("reviews")
                .insert(
                    {
                        "product_id": product["id"],
                        "author": r_item["author"],
                        "text": r_item["text"],
                        "images": r_item["images"],
                    }
                )
                .execute()
            )
            if getattr(r, "data", None) is None:
                raise SupabaseInsertError("sharh qo'shishda xato")

        return product

    except SupabaseInsertError:
        raise
    except Exception as e:
        raise SupabaseInsertError(f"Supabase'ga yozishda xatolik: {e}") from e
