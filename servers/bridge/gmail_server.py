"""MCP bridge server for Gmail integration.

Credentials must be provided via environment variables / .env:
  GMAIL_CREDENTIALS_PATH - path to OAuth2 credentials JSON
  GMAIL_TOKEN_PATH       - path to stored OAuth2 token JSON
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastmcp import FastMCP

from shared.config import get_settings
from shared.logging import configure_logging, get_logger

configure_logging()
logger = get_logger("mcp.bridge.gmail")

mcp = FastMCP(
    name="mcp-gmail-bridge",
    instructions="Gmail integration bridge. Configure GMAIL_CREDENTIALS_PATH and GMAIL_TOKEN_PATH.",
)


def _get_service():
    settings = get_settings()
    if not settings.gmail_credentials_path or not settings.gmail_token_path:
        raise RuntimeError("Gmail credentials not configured. Set GMAIL_CREDENTIALS_PATH and GMAIL_TOKEN_PATH.")

    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = None
    token_path = Path(settings.gmail_token_path)
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), ["https://www.googleapis.com/auth/gmail.modify"])
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            raise RuntimeError("Gmail token missing or invalid. Run OAuth flow first.")
        token_path.write_text(creds.to_json())
    return build("gmail", "v1", credentials=creds)


@mcp.tool()
async def gmail_list_messages(max_results: int = 10, query: str = "") -> list[dict]:
    """List recent Gmail messages matching an optional query."""
    try:
        service = _get_service()
        result = service.users().messages().list(
            userId="me", q=query, maxResults=max_results
        ).execute()
        return result.get("messages", [])
    except Exception as exc:  # noqa: BLE001
        logger.error("gmail_list_failed", error=str(exc))
        return [{"status": "error", "error": str(exc)}]


@mcp.tool()
async def gmail_send_message(to: str, subject: str, body: str) -> dict:
    """Send a plain-text email via Gmail."""
    try:
        import base64
        from email.mime.text import MIMEText

        service = _get_service()
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return {"status": "sent", "id": sent.get("id")}
    except Exception as exc:  # noqa: BLE001
        logger.error("gmail_send_failed", error=str(exc))
        return {"status": "error", "error": str(exc)}


@mcp.tool()
async def gmail_get_message(message_id: str) -> dict:
    """Fetch a Gmail message by ID."""
    try:
        service = _get_service()
        msg = service.users().messages().get(userId="me", id=message_id, format="full").execute()
        return {"status": "ok", "message": msg}
    except Exception as exc:  # noqa: BLE001
        logger.error("gmail_get_failed", error=str(exc))
        return {"status": "error", "error": str(exc)}


if __name__ == "__main__":
    from shared.server_runner import run
    run(mcp)
