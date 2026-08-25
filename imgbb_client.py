import os
import uuid
from supabase import create_client, Client

# Muhit o'zgaruvchilaridan (Environment Variables) Supabase kalitlarini olish
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL yoki SUPABASE_KEY kalitlari topilmadi!")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class ImgbbUploadError(Exception):
    pass

def upload_images(image_bytes_list: list[bytes]) -> list[str]:
    """
    Rasmlar ro'yxatini Supabase Storage'ga yuklaydi 
    va doimiy ishlaydigan Public URL havolalarini qaytaradi.
    """
    uploaded_urls = []
    
    for idx, img_bytes in enumerate(image_bytes_list, 1):
        file_name = f"prod_{uuid.uuid4().hex[:10]}.jpg"
        
        try:
            # Supabase 'images' bucket'iga yuklash
            supabase.storage.from_("images").upload(
                path=file_name,
                file=img_bytes,
                file_options={"content-type": "image/jpeg"}
            )
            
            # Ochiq URL havolani olish
            public_url = supabase.storage.from_("images").get_public_url(file_name)
            uploaded_urls.append(public_url)
            
        except Exception as e:
            raise ImgbbUploadError(f"{idx}-rasmni Supabase'ga yuklashda xatolik: {str(e)}")
            
    return uploaded_urls
