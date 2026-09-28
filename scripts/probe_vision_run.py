"""Manual probe: run a Google Vision OCR call against a generated 1x1 PNG.

This is not a pytest test: it needs credentials and network access. It was moved
out of ``tests/`` so that pytest collection no longer depends on them (TASK-140).
"""

from __future__ import annotations

import asyncio
import base64
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from servers.bridge.vision_server import vision_ocr  # noqa: E402

_PIXEL_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="vision-probe-") as tmp_dir:
        test_img = Path(tmp_dir) / "test_pixel.png"
        test_img.write_bytes(base64.b64decode(_PIXEL_PNG_B64))

        print("Requesting the Google Vision API ...")
        result = await vision_ocr(str(test_img))
        print(f"Result: {result}")


if __name__ == "__main__":
    asyncio.run(main())
