"""MCP bridge server for Google Cloud Vision OCR.

Environment variable required:
  GOOGLE_VISION_CREDENTIALS_PATH - path to service-account JSON
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import httpx
from fastmcp import FastMCP

from shared.config import get_settings
from shared.logging import configure_logging, get_logger

configure_logging()
logger = get_logger("mcp.bridge.vision")

mcp = FastMCP(
    name="mcp-vision-bridge",
    instructions="Google Cloud Vision OCR bridge. Configure GOOGLE_VISION_CREDENTIALS_PATH.",
)


def _get_access_token() -> str:
    settings = get_settings()
    creds_path = settings.google_vision_credentials_path
    if not creds_path:
        raise RuntimeError("GOOGLE_VISION_CREDENTIALS_PATH not configured")

    from google.oauth2 import service_account
    credentials = service_account.Credentials.from_service_account_file(
        str(creds_path),
        scopes=["https://www.googleapis.com/auth/cloud-vision"],
    )
    return credentials.token


@mcp.tool()
async def vision_ocr(image_path: str) -> dict:
    """Run OCR on an image file using Google Cloud Vision."""
    path = Path(image_path)
    if not path.exists():
        return {"status": "error", "error": f"File not found: {image_path}"}

    try:
        token = _get_access_token()
        image_bytes = path.read_bytes()
        encoded = base64.b64encode(image_bytes).decode("utf-8")

        url = "https://vision.googleapis.com/v1/images:annotate"
        payload = {
            "requests": [{
                "image": {"content": encoded},
                "features": [{"type": "TEXT_DETECTION", "maxResults": 1}],
            }]
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            data = response.json()

        annotations = data["responses"][0].get("textAnnotations", [])
        text = annotations[0]["description"] if annotations else ""
        return {"status": "ok", "text": text, "annotations": len(annotations)}
    except Exception as exc:  # noqa: BLE001
        logger.error("vision_ocr_failed", error=str(exc))
        return {"status": "error", "error": str(exc)}


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
