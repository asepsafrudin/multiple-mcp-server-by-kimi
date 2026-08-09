"""Web fetching and URL checking utilities."""

from __future__ import annotations

import re
from typing import Any

import httpx

from shared.config import get_settings


def _strip_html_tags(text: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


async def fetch_url(
    url: str,
    extract_text: bool = True,
    timeout: int = 30,
    max_chars: int = 10_000,
) -> dict[str, Any]:
    """Fetch the content of a URL.

    Args:
        url: Target URL (http/https).
        extract_text: If True and the response is HTML, strip tags.
        timeout: Request timeout in seconds.
        max_chars: Maximum characters to return.
    """
    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": "mcp-aseps-core/0.1.0"},
    ) as client:
        response = await client.get(url)
        response.raise_for_status()

    content_type = response.headers.get("content-type", "")
    text = response.text

    if extract_text and "text/html" in content_type:
        text = _strip_html_tags(text)

    if len(text) > max_chars:
        text = text[:max_chars] + "\n... [truncated]"

    return {
        "url": str(response.url),
        "status_code": response.status_code,
        "content_type": content_type,
        "length": len(text),
        "content": text,
    }


async def check_url_status(url: str, timeout: int = 10) -> dict[str, Any]:
    """Check whether a URL is reachable via HEAD request."""
    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": "mcp-aseps-core/0.1.0"},
    ) as client:
        response = await client.head(url)
    return {
        "url": str(response.url),
        "status_code": response.status_code,
        "reachable": response.status_code < 400,
    }
