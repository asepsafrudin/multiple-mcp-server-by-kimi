#!/usr/bin/env python3
"""One-time OAuth2 bootstrap for the Gmail MCP bridge.

The modular ``servers.bridge.gmail_server`` authenticates with an *authorized-user*
token (GMAIL_TOKEN_PATH) refreshed via GMAIL_CREDENTIALS_PATH (OAuth2 client secret).
This script runs the interactive consent flow once and writes the token JSON.

Prerequisites
-------------
1. Enable the Gmail API in Google Cloud Console for the project.
2. Create an OAuth 2.0 Client ID (Desktop app) and download its JSON
   (client secret) to the path in GMAIL_CREDENTIALS_PATH.
3. On first use only, the script opens a browser for sign-in / consent.

Usage
-----
    ./.venv/bin/python scripts/gmail_oauth_setup.py

It honours GMAIL_CREDENTIALS_PATH / GMAIL_TOKEN_PATH from the project .env,
or you may override with --client-secret / --token.
"""

from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from google_auth_oauthlib.flow import InstalledAppFlow

from shared.config import get_settings

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def main() -> int:
    parser = argparse.ArgumentParser(description="One-time Gmail OAuth2 bootstrap.")
    parser.add_argument(
        "--client-secret",
        default=None,
        help="Path to OAuth2 client secret JSON (default: GMAIL_CREDENTIALS_PATH).",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="Output path for the authorized-user token (default: GMAIL_TOKEN_PATH).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="Local redirect port (default: arbitrary free port).",
    )
    args = parser.parse_args()

    s = get_settings()
    client_secret = Path(args.client_secret or s.gmail_credentials_path or "")
    token_out = Path(args.token or s.gmail_token_path or "")

    if not client_secret.exists():
        print(
            f"ERROR: client secret not found at {client_secret}\n"
            "Download the OAuth 2.0 Client ID JSON (Desktop app) from Google Cloud "
            "Console -> APIs & Services -> Credentials and point GMAIL_CREDENTIALS_PATH "
            "to it (or pass --client-secret).",
            file=sys.stderr,
        )
        return 1
    if not token_out.parent.exists():
        token_out.parent.mkdir(parents=True, exist_ok=True)

    print(f"Client secret : {client_secret}")
    print(f"Token output  : {token_out}")
    print("A browser will open (or a URL will be shown) for Google sign-in.\n")

    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), SCOPES)

    # Prefer auto-open; fall back to manual open when no browser is available.
    try:
        creds = flow.run_local_server(port=args.port)
    except webbrowser.Error:
        print(
            "\n[INFO] Python could not auto-launch a browser.\n"
            "A local auth server is listening on 127.0.0.1. Open the URL that gets\n"
            "printed below in your browser, sign in, and allow access. It will\n"
            "redirect back automatically.\n"
        )
        creds = flow.run_local_server(port=args.port, open_browser=False)

    token_out.write_text(creds.to_json())
    print(f"\nOK. Token saved to {token_out}")
    print("Reload/restart Cline so mcp-gmail-bridge picks up the new token.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())