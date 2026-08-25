import uuid
from config import supabase

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
