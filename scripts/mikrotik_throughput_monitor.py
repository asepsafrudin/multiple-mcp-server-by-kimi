#!/usr/bin/env python3
"""Monitor packet throughput on MikroTik RouterOS via REST API.

Queries interface statistics and displays real-time throughput metrics
including bytes/packets in/out, rates, and interface status.

Usage:
    python scripts/mikrotik_throughput_monitor.py [--interface ether1] [--interval 2] [--count 10]
"""

import argparse
import time
from datetime import datetime
from typing import Any

import httpx


def get_settings() -> dict[str, Any]:
    """Load MikroTik settings from environment."""
    import os
    from pathlib import Path

    from dotenv import load_dotenv

    # Load .env from project root
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")

    host = os.getenv("MIKROTIK_HOST") or "idn23.tunnel.id"
    port_str = os.getenv("MIKROTIK_PORT")
    port = int(port_str) if port_str and port_str.strip() else 3227
    scheme = os.getenv("MIKROTIK_SCHEME") or "https"
    user = os.getenv("MIKROTIK_USER") or "admin"
    password = os.getenv("MIKROTIK_PASSWORD") or ""

    return {
        "host": host,
        "port": port,
        "scheme": scheme,
        "user": user,
        "password": password,
        "tls_verify": os.getenv("MIKROTIK_TLS_VERIFY", "false").lower() == "true",
    }


def build_client(settings: dict[str, Any]) -> httpx.Client:
    """Build synchronous HTTP client with Basic auth."""
    return httpx.Client(
        auth=(settings["user"], settings["password"]),
        timeout=30.0,
        verify=settings["tls_verify"],
    )


def get_interfaces(settings: dict[str, Any], client: httpx.Client) -> list[dict[str, Any]]:
    """Fetch all interfaces from RouterOS REST API."""
    url = f"{settings['scheme']}://{settings['host']}:{settings['port']}/rest/interface"
    response = client.get(url)
    response.raise_for_status()
    return response.json()


def get_interface_by_name(
    settings: dict[str, Any], client: httpx.Client, name: str
) -> dict[str, Any] | None:
    """Fetch specific interface by name."""
    interfaces = get_interfaces(settings, client)
    for iface in interfaces:
        if iface.get("name") == name:
            return iface
    return None


def format_bytes(bytes_val: int | None) -> str:
    """Format bytes to human-readable string."""
    if bytes_val is None:
        return "N/A"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(bytes_val) < 1024.0:
            return f"{bytes_val:.2f} {unit}"
        bytes_val /= 1024.0
    return f"{bytes_val:.2f} PB"


def format_rate(bytes_per_sec: float | None) -> str:
    """Format throughput rate."""
    if bytes_per_sec is None:
        return "N/A"
    return f"{format_bytes(int(bytes_per_sec))}/s"


def print_header() -> None:
    """Print table header."""
    print(
        f"{'Time':<20} {'Interface':<20} {'RX Bytes':<15} {'TX Bytes':<15} "
        f"{'RX Packets':<15} {'TX Packets':<15} {'RX Rate':<15} {'TX Rate':<15}"
    )
    print("-" * 140)


def _to_int(value: Any) -> int:
    """Convert value to int, handling strings and None."""
    if value is None:
        return 0
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


def print_interface_stats(
    timestamp: str,
    iface: dict[str, Any],
    rx_rate: float | None = None,
    tx_rate: float | None = None,
) -> None:
    """Print interface statistics row."""
    rx_bytes = _to_int(iface.get("rx-byte", iface.get("bytes", 0)))
    tx_bytes = _to_int(iface.get("tx-byte", iface.get("tx-byte", 0)))
    rx_packets = _to_int(iface.get("rx-packet", iface.get("packets", 0)))
    tx_packets = _to_int(iface.get("tx-packet", iface.get("packets", 0)))

    rx_rate_str = format_rate(rx_rate) if rx_rate is not None else "N/A"
    tx_rate_str = format_rate(tx_rate) if tx_rate is not None else "N/A"

    print(
        f"{timestamp:<20} {iface.get('name', 'unknown'):<20} "
        f"{format_bytes(rx_bytes):<15} {format_bytes(tx_bytes):<15} "
        f"{str(rx_packets):<15} {str(tx_packets):<15} "
        f"{rx_rate_str:<15} {tx_rate_str:<15}"
    )


def monitor_throughput(
    settings: dict[str, Any],
    interface: str | None = None,
    interval: float = 2.0,
    count: int | None = None,
) -> None:
    """Monitor interface throughput continuously."""
    print("=" * 140)
    print(f"MikroTik Throughput Monitor - {settings['host']}")
    print(f"Interface: {interface or 'all'} | Interval: {interval}s | Count: {count or '∞'}")
    print("=" * 140)
    print_header()

    client = build_client(settings)
    iteration = 0

    try:
        # Get initial stats
        if interface:
            iface_data = get_interface_by_name(settings, client, interface)
            if iface_data is None:
                print(f"Error: Interface '{interface}' not found.")
                return
            prev_stats = {interface: iface_data}
        else:
            interfaces = get_interfaces(settings, client)
            prev_stats = {iface["name"]: iface for iface in interfaces}

        while True:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if interface:
                iface_data = get_interface_by_name(settings, client, interface)
                if iface_data:
                    rx_bytes_new = _to_int(iface_data.get("rx-byte", iface_data.get("bytes", 0)))
                    tx_bytes_new = _to_int(iface_data.get("tx-byte", iface_data.get("tx-byte", 0)))
                    prev = prev_stats.get(interface, {})

                    rx_rate = (
                        (rx_bytes_new - _to_int(prev.get("rx-byte", prev.get("bytes", 0)))) / interval
                        if prev
                        else None
                    )
                    tx_rate = (
                        (tx_bytes_new - _to_int(prev.get("tx-byte", prev.get("tx-byte", 0)))) / interval
                        if prev
                        else None
                    )

                    print_interface_stats(timestamp, iface_data, rx_rate, tx_rate)
                    prev_stats[interface] = iface_data
            else:
                interfaces = get_interfaces(settings, client)
                for iface_data in interfaces:
                    name = iface_data["name"]
                    rx_bytes_new = _to_int(iface_data.get("rx-byte", iface_data.get("bytes", 0)))
                    tx_bytes_new = _to_int(iface_data.get("tx-byte", iface_data.get("tx-byte", 0)))
                    prev = prev_stats.get(name, {})

                    rx_rate = (
                        (rx_bytes_new - _to_int(prev.get("rx-byte", prev.get("bytes", 0)))) / interval
                        if prev
                        else None
                    )
                    tx_rate = (
                        (tx_bytes_new - _to_int(prev.get("tx-byte", prev.get("tx-byte", 0)))) / interval
                        if prev
                        else None
                    )

                    print_interface_stats(timestamp, iface_data, rx_rate, tx_rate)
                    prev_stats[name] = iface_data

            iteration += 1
            if count and iteration >= count:
                break

            time.sleep(interval)

    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        client.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Monitor MikroTik interface throughput in real-time"
    )
    parser.add_argument(
        "--interface",
        "-i",
        help="Specific interface to monitor (e.g. ether1, wlan1)",
    )
    parser.add_argument(
        "--interval",
        "-n",
        type=float,
        default=2.0,
        help="Polling interval in seconds (default: 2.0)",
    )
    parser.add_argument(
        "--count",
        "-c",
        type=int,
        help="Number of samples to collect (default: infinite)",
    )
    args = parser.parse_args()

    try:
        settings = get_settings()
        monitor_throughput(
            settings=settings,
            interface=args.interface,
            interval=args.interval,
            count=args.count,
        )
    except Exception as e:
        print(f"Fatal error: {e}")
        return 1
    return 0


if __name__ == "__main__":
    exit(main() or 0)