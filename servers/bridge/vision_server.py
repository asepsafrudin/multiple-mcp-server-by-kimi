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

    import google.auth.transport.requests
    from google.oauth2 import service_account

    credentials = service_account.Credentials.from_service_account_file(
        str(creds_path),
        scopes=["https://www.googleapis.com/auth/cloud-vision"],
    )
    request = google.auth.transport.requests.Request()
    credentials.refresh(request)
    return credentials.token


async def _ollama_fallback_ocr(encoded_img: str) -> dict:
    """Fallback to local Ollama multimodal model."""
    settings = get_settings()
    ollama_url = f"{settings.ollama_url.rstrip('/')}/api/generate"

    payload = {
        "model": "llama3.2-vision",
        "prompt": "Extract all readable text from this image as accurately as possible. Output only the extracted text without any conversational fillers. Preserve formatting where possible.",
        "images": [encoded_img],
        "stream": False,
    }

    logger.info("falling_back_to_ollama_vision", model="llama3.2-vision")
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(ollama_url, json=payload)
        if response.status_code == 404:
            logger.warning("llama3.2-vision model not found, attempting moondream")
            payload["model"] = "moondream"
            response = await client.post(ollama_url, json=payload)

        response.raise_for_status()
        data = response.json()

    text = data.get("response", "").strip()
    return {"status": "ok", "text": text, "source": "ollama_" + payload["model"]}


@mcp.tool()
async def vision_ocr(image_path: str) -> dict:
    """Run OCR on an image file using Google Cloud Vision."""
    path = Path(image_path)
    if not path.exists():
        return {"status": "error", "error": f"File not found: {image_path}"}

    try:
        image_bytes = path.read_bytes()
        encoded = base64.b64encode(image_bytes).decode("utf-8")
    except Exception as exc:
        return {"status": "error", "error": f"Failed to read image: {exc}"}

    try:
        token = _get_access_token()

        url = "https://vision.googleapis.com/v1/images:annotate"
        payload = {
            "requests": [
                {
                    "image": {"content": encoded},
                    "features": [{"type": "TEXT_DETECTION", "maxResults": 1}],
                }
            ]
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
        return {
            "status": "ok",
            "text": text,
            "annotations": len(annotations),
            "source": "google_cloud_vision",
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("vision_ocr_failed_attempting_fallback", error=str(exc))
        try:
            return await _ollama_fallback_ocr(encoded)
        except Exception as fallback_exc:
            logger.error("vision_ocr_fallback_failed", error=str(fallback_exc))
            return {
                "status": "error",
                "error": f"Google Vision API failed: {exc} | Ollama Fallback failed: {fallback_exc}",
            }


if __name__ == "__main__":
    from shared.server_runner import run

    run(mcp)
