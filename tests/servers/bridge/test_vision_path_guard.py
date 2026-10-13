"""TASK-139 regression: vision_ocr menolak image_path di luar allowed (sebelum baca/kirim ke layanan eksternal)."""

from __future__ import annotations

import asyncio

from servers.bridge.vision_server import vision_ocr


def test_vision_ocr_rejects_outside_allowed():
    res = asyncio.run(vision_ocr(image_path="/etc/passwd"))
    assert res.get("status") == "error"
    assert "not allowed" in res.get("error", "").lower()
