"""MCP bridge server for Google Gemini integration.

Environment variable required:
  GEMINI_API_KEY
"""

from __future__ import annotations

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
logger = get_logger("mcp.bridge.gemini")

mcp = FastMCP(
    name="mcp-gemini-bridge",
    instructions="Google Gemini bridge. Configure GEMINI_API_KEY in environment or .env.",
)


@mcp.tool()
async def gemini_generate(
    prompt: str,
    model: str | None = None,
    max_tokens: int = 1024,
    temperature: float = 0.7,
) -> dict:
    """Generate text with Google Gemini."""
    settings = get_settings()
    api_key = settings.gemini_api_key
    if not api_key:
        return {"status": "error", "error": "GEMINI_API_KEY not configured"}

    model_name = model or "gemini-1.5-flash-latest"
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
        f"?key={api_key}"
    )
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": temperature,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

        candidates = data.get("candidates", [])
        if not candidates:
            return {"status": "error", "error": "No candidates returned", "raw": data}

        text = ""
        for part in candidates[0].get("content", {}).get("parts", []):
            text += part.get("text", "")
        return {"status": "ok", "text": text, "model": model_name}
    except Exception as exc:  # noqa: BLE001
        logger.error("gemini_generate_failed", error=str(exc))
        return {"status": "error", "error": str(exc)}


if __name__ == "__main__":
    from shared.server_runner import run

    run(mcp)
