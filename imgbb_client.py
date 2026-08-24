import requests

def upload_image_to_imgbb(image_bytes: bytes) -> str:
    """Rasmni Telegraph serveriga yuklaydi va URL qaytaradi."""
    url = "https://telegra.ph/upload"
    files = {'file': ('image.jpg', image_bytes, 'image/jpeg')}
    
    response = requests.post(url, files=files)
    
    if response.status_code == 200:
        data = response.json()
        if isinstance(data, list) and len(data) > 0:
            return "https://telegra.ph" + data[0]['src']
            
    raise Exception(f"Telegraph yuklashda xatolik: {response.text}")
