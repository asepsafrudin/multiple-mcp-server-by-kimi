"""Manual probe: verify the Google Cloud Vision service-account token refresh.

This is not a pytest test: it needs a local service-account JSON and performs a
real network call. It was moved out of ``tests/`` because importing it during
collection aborted the whole suite with ``FileNotFoundError`` (TASK-140).

Usage:
    VISION_CREDENTIALS_PATH=/path/to/service-account.json \\
        python scripts/probe_vision_token.py
"""

from __future__ import annotations

import os

from google.auth.transport.requests import Request
from google.oauth2 import service_account


def main() -> None:
    path = os.environ.get("VISION_CREDENTIALS_PATH")
    if not path:
        raise SystemExit(
            "Set VISION_CREDENTIALS_PATH to a Google service-account JSON file "
            "before running this probe."
        )

    credentials = service_account.Credentials.from_service_account_file(
        path,
        scopes=["https://www.googleapis.com/auth/cloud-vision"],
    )
    print("Token before refresh:", credentials.token)
    credentials.refresh(Request())
    print("Token after refresh:", credentials.token is not None)


if __name__ == "__main__":
    main()
