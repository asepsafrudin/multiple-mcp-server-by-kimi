import asyncio
import base64
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from servers.bridge.vision_server import vision_ocr

async def main():
    test_img = Path("/home/aseps/MCP/tests/test_pixel.png")
    # 1x1 pixel png
    test_img.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="))
    
    print("Mencoba request ke Google Vision API...")
    result = await vision_ocr(str(test_img))
    print(f"Hasil: {result}")
    
    if test_img.exists():
        test_img.unlink()

if __name__ == "__main__":
    asyncio.run(main())
