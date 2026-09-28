#!/usr/bin/env python3
"""Script to store MikroTik configurations in long-term memory (LTM)."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
root = Path(__file__).resolve().parents[1]
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from servers.memory.engine import store
from shared.models import MemoryEntry


async def main():
    m1 = MemoryEntry(
        namespace="network",
        content=(
            "MikroTik Router 1 (Default / Remote / WAN):\n"
            "- Host: <REDACTED>\n"
            "- REST SSL Port: 3227\n"
            "- SSH Port: 3228\n"
            "- Scheme: https\n"
            "- User: admin\n"
            "- OS: RouterOS v7 (Supports full REST API)\n"
            "- Connection Type: Remote VPN Tunnel (via tunnel.id)"
        ),
        summary="MikroTik Router 1 Connection (<REDACTED>)",
        category="context",
        tags=["mikrotik", "router1", "vpn", "remote"],
        importance=10,
        validation_status="verified",
    )

    m2 = MemoryEntry(
        namespace="network",
        content=(
            "MikroTik Router 2 (Lokal / LAN):\n"
            "- Host: 192.168.22.1\n"
            "- REST SSL Port: 80 (HTTP)\n"
            "- SSH Port: 22\n"
            "- Scheme: http\n"
            "- User: admin\n"
            "- OS: RouterOS v6 (No REST API support, returns 404 on /rest; use SSH instead)\n"
            "- Connection Type: Local IP connection"
        ),
        summary="MikroTik Router 2 Connection (192.168.22.1)",
        category="context",
        tags=["mikrotik", "router2", "local", "lan"],
        importance=10,
        validation_status="verified",
    )

    id1 = await store(m1)
    id2 = await store(m2)
    print(f"Stored Memory 1 ID: {id1}")
    print(f"Stored Memory 2 ID: {id2}")


if __name__ == "__main__":
    asyncio.run(main())
