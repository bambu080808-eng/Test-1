# Bot 2 — Mahsulot yuklovchi Telegram bot

Ushbu bot quyidagi jarayonni to'liq avtomatlashtiradi:

1. `/start` → "🖼 Mahsulot rasimlarini yuklash" tugmasi
2. Mahsulot rasimlari (bittalab yoki albom holida) — har birida "✅ Qabul qilindi" javobi
3. "➡️ Kamentariya rasimlariga o'tish" tugmasi → sharh (kamentariya) rasimlari (ixtiyoriy)
4. "➡️ Mahsulot ma'lumotlari rasimlariga o'tish" tugmasi → narx/nom/tavsif/sharh matni ko'rsatilgan skrinshotlar
5. "✅ Tayyor" tugmasi bosilgach:
   - mahsulot va sharh rasmlari **imgbb** ga yuklanadi (URL olinadi)
   - ma'lumot skrinshotlari + URL lar **Gemini AI** ga yuboriladi, u standart HTML kartochkani yaratadi
   - HTML **Bot 1'ning `parseAndInsertProduct()` funksiyasi bilan AYNAN bir xil mantiqda** tahlil qilinadi va **Supabase**'ga yoziladi
   - foydalanuvchiga "✅ bazaga joylandi" xabari yuboriladi (yoki xatolik bo'lsa, aniq sababi bilan xabar beriladi)

## ✅ Supabase sxemasi — Bot 1'ning haqiqiy kodidan olindi

Siz yuborgan `Shu.html` faylidagi `parseAndInsertProduct()` funksiyasini
tekshirib chiqdim. Bot 2 endi aynan shu 5 ta jadval va ustunlarga, aynan shu
tartibda yozadi — taxmin qilingan hech narsa yo'q:

1. **`catalogs`** — `{name}` (agar mavjud bo'lmasa, avval shu yerga qo'shiladi)
2. **`product_types`** — `{name, catalog_id}` (agar mavjud bo'lmasa qo'shiladi)
3. **`products`** — `{name, price, description, catalog_id, type_id, images (jsonb), extra (jsonb), rating, reviews_count, views_count, likes_count, sold_count}`
4. **`product_variants`** — har bir variant uchun: `{product_id, variant_type, options (jsonb)}`
5. **`reviews`** — har bir sharh uchun: `{product_id, author, text, images (jsonb)}`

`schema.sql` faylida bu tuzilma hujjat sifatida yozilgan (jadvallar allaqachon
mavjud bo'lgani uchun uni ishga tushirish shart emas).

## Fayllar

| Fayl | Vazifasi |
|---|---|
| `bot.py` | Asosiy bot — tugmalar, holatlar (states), rasm qabul qilish, yakuniy jarayon |
| `config.py` | Muhit o'zgaruvchilarini o'qiydi |
| `prompts.py` | Gemini uchun qayta yozilgan promt (asl talab qoidalari saqlangan) |
| `imgbb_client.py` | Rasmlarni imgbb'ga yuklab URL olish |
| `gemini_client.py` | Gemini API chaqiruvi (skrinshotlar + URL lar → HTML) |
| `html_parser.py` | AI qaytargan HTML'ni Bot 1 bilan bir xil mantiqda maydonlarga ajratish |
| `supabase_client.py` | catalogs/product_types/products/product_variants/reviews'ga yozish |
| `schema.sql` | Tasdiqlangan sxema (hujjat sifatida) |
| `render.yaml`, `Procfile` | Render'ga deploy qilish uchun |

## Render'ga deploy qilish

1. Ushbu papkani GitHub repo qilib yuklang (yoki Render'ga to'g'ridan-to'g'ri
   ZIP/repo sifatida bering).
2. Render dashboard → **New +** → **Blueprint** → repo'ni tanlang (bu
   `render.yaml`ni avtomatik o'qib, "Background Worker" xizmatini yaratadi).
   - Blueprint ishlatmasangiz: **New +** → **Background Worker** → repo →
     Build command: `pip install -r requirements.txt`, Start command:
     `python bot.py`.
3. **Environment** bo'limida quyidagilarni kiriting (`.env.example` ga qarang):
   - `TELEGRAM_BOT_TOKEN` — @BotFather'dan
   - `IMGBB_API_KEY` — https://api.imgbb.com/
   - `GEMINI_API_KEY` — https://aistudio.google.com/apikey
   - `SUPABASE_URL` — `https://nwxfvcmujyicnxxkrpcz.supabase.co` (Bot 1'dagi bilan bir xil loyiha)
   - `SUPABASE_KEY` — tavsiya etiladi: **service_role** kalit (Supabase
     Dashboard → Settings → API). Bot 1 anon/publishable kalitni ishlatadi;
     agar o'sha kalit uchun `insert` ruxsat beruvchi RLS policy mavjud bo'lsa,
     uni ham ishlatsa bo'ladi — lekin service_role eng ishonchli yo'l.
   - ixtiyoriy: `GEMINI_MODEL` (default: `gemini-2.5-flash`), `ADMIN_CHAT_IDS`,
     `MAX_INFO_IMAGES`
4. Deploy qiling. Bot **polling** rejimida ishlaydi (webhook shart emas),
   shuning uchun "Background Worker" turi yetarli.

## Botni faqat o'zingiz ishlatishingiz uchun

`ADMIN_CHAT_IDS` ga o'z Telegram user ID'ingizni yozing (vergul bilan bir
nechtasini ham yozish mumkin). Bo'sh qoldirilsa, bot hammaga ochiq bo'ladi.
User ID'ni bilish uchun Telegram'da @userinfobot ga yozing.

## Kutilmagan holatlar (edge case'lar) qanday ishlaydi

- **Rasm o'rniga matn/boshqa fayl yuborilsa** → bot hozirgi bosqichda nima
  kutayotganini eslatib, holatni o'zgartirmaydi.
- **Rasm fayl (Document) sifatida yuborilsa** (siqilmagan) → bot ham buni
  qabul qiladi (`filters.Document.IMAGE`).
- **"➡️ Kamentariya rasimlariga o'tish" 0 ta mahsulot rasmi bilan bosilsa** →
  bot ogohlantiradi, kamida 1 ta rasm so'raydi.
- **"✅ Tayyor" 0 ta ma'lumot skrinshoti bilan bosilsa** → bot ogohlantiradi.
- **imgbb yuklashda xatolik** → foydalanuvchiga aniq xabar, `/start` bilan
  qaytadan boshlash taklif qilinadi.
- **AI kutilmagan formatda javob bersa** (HTML emas) → xatolik sifatida
  ushlanadi, foydalanuvchiga aniq aytiladi.
- **Supabase yozishda xatolik** (masalan RLS ruxsat bermasa) → foydalanuvchiga
  aniq xabar beriladi, jarayon "osilib" qolmaydi. `product_variants`/`reviews`
  yozishda xatolik bo'lsa ham (asosiy `products` qatori allaqachon yozilgan
  bo'lishi mumkin), bu holat ham aniq xabar bilan bildiriladi.
- **Har qanday kutilmagan/dasturdagi xatolik** → global error handler ushlab,
  foydalanuvchiga umumiy xabar yuboradi va Render loglariga to'liq stacktrace
  yozadi (Render dashboard → Logs).
- **`/cancel`** — istalgan bosqichda jarayonni bekor qilib, boshidan
  boshlash imkonini beradi.

## Lokal test qilish

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # va qiymatlarni to'ldiring
export $(cat .env | xargs)
python bot.py
```
