#!/usr/bin/env python3
"""Script untuk melakukan End-to-End test eksternal API menggunakan kredensial sungguhan.
Penting: Pastikan Anda telah mengonfigurasi variabel-variabel kredensial di file .env
"""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.config import get_settings

async def test_telegram():
    print("==== [ TELEGRAM ] ====")
    from servers.bridge.telegram_server import telegram_get_updates, telegram_send_message
    res = await telegram_get_updates(limit=1)
    print("Fetch updates result:")
    print(res)
    if res and not (isinstance(res, list) and len(res) > 0 and res[0].get("status") == "error"):
        print("✅ Telegram GET OK")
    else:
        print("❌ Telegram GET ERROR")
    print("\n")

async def test_gmail():
    print("==== [ GMAIL ] ====")
    from servers.bridge.gmail_server import gmail_list_messages
    res = await gmail_list_messages(max_results=1)
    print("List message result (max 1):")
    if isinstance(res, list) and (len(res) == 0 or "id" in res[0]):
        print(res)
        print("✅ Gmail LIST OK")
    else:
        print(res)
        print("❌ Gmail LIST ERROR")
    print("\n")


async def test_gemini():
    print("==== [ GEMINI ] ====")
    from servers.bridge.gemini_server import gemini_generate
    res = await gemini_generate("Balas dengan kata 'Halo Dunia' saja", model="gemini-1.5-flash-latest")
    print("Generate text result:")
    print(res)
    if res.get("status") == "ok":
        print("✅ Gemini OK")
    else:
        print("❌ Gemini ERROR")
    print("\n")


async def test_vision():
    print("==== [ VISION OCR ] ====")
    from servers.bridge.vision_server import vision_ocr
    # Buat dummy gambar teks transparan ringan berukuran 1x1 jika tdk ada gambar utk ditest
    img_path = ROOT / "test_image.png"
    with open(img_path, "wb") as f:
        # Base64 kecil untuk representasi PNG kosong (akan gagal mendapatkan text, namun memastikan koneksi Oauth2/API Vision berhasil)
        f.write(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82')
    
    res = await vision_ocr(str(img_path))
    if img_path.exists():
        img_path.unlink()
        
    print("Vision OCR result:")
    print(res)
    if res.get("status") == "ok":
        print("✅ Vision OCR OK")
    else:
        print("❌ Vision OCR ERROR")
    print("\n")

async def main():
    settings = get_settings()
    print("\nMemulai Verifikasi End-to-End dengan kredensial sungguhan .env\n")
    
    all_skipped = True
    
    if settings.telegram_bot_token:
        all_skipped = False
        await test_telegram()
    else:
        print("⚠️ SKIP Telegram: TELEGRAM_BOT_TOKEN missing in .env")
        
    if settings.gmail_credentials_path and settings.gmail_token_path:
        all_skipped = False
        await test_gmail()
    else:
        print("⚠️ SKIP Gmail: GMAIL_CREDENTIALS_PATH or GMAIL_TOKEN_PATH missing in .env")
        
    if settings.gemini_api_key:
        all_skipped = False
        await test_gemini()
    else:
        print("⚠️ SKIP Gemini: GEMINI_API_KEY missing in .env")
        
    if settings.google_vision_credentials_path:
        all_skipped = False
        await test_vision()
    else:
        print("⚠️ SKIP Vision: GOOGLE_VISION_CREDENTIALS_PATH missing in .env")
        
    if all_skipped:
        print("\n\n❗ SEMUA SKIPPED. Peringatan: .env Anda nampaknya tidak terisi profil credential apapun.")
        print("Silakan salin isi .env.example menjadi .env lalu jalankan lagi script ini.")

if __name__ == "__main__":
    asyncio.run(main())
