import requests

class ImgbbUploadError(Exception):
    """Telegraph yuklash xatoligi uchun klass (bot.py buzilmasligi uchun)"""
    pass

def upload_images(image_bytes_list: list[bytes]) -> list[str]:
    """
    Rasmlar ro'yxatini Telegraph serveriga yuklaydi 
    va URL havolalar ro'yxatini qaytaradi.
    """
    uploaded_urls = []
    
    for idx, img_bytes in enumerate(image_bytes_list, 1):
        url = "https://telegra.ph/upload"
        files = {'file': (f'image_{idx}.jpg', img_bytes, 'image/jpeg')}
        
        try:
            response = requests.post(url, files=files, timeout=15)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) > 0 and 'src' in data[0]:
                    full_url = "https://telegra.ph" + data[0]['src']
                    uploaded_urls.append(full_url)
                else:
                    raise ImgbbUploadError(f"{idx}-rasmni yuklashda xatolik: Noto'g'ri javob strukturasi")
            else:
                raise ImgbbUploadError(f"{idx}-rasmni yuklashda xatolik: Telegraph status {response.status_code}")
        except Exception as e:
            raise ImgbbUploadError(f"{idx}-rasmni yuklashda xatolik: {str(e)}")
            
    return uploaded_urls
