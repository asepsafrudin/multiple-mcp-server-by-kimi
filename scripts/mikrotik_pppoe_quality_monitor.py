#!/usr/bin/env python3
"""Real-time PPPoE interface quality monitoring for MikroTik RouterOS.

Monitors throughput stability, latency, jitter, and packet loss for each
PPPoE client to identify unstable connections.

Usage:
    python scripts/mikrotik_pppoe_quality_monitor.py [--interval 2] [--window 30] [--duration 300]
"""

import argparse
import json
import math
import statistics
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx


def get_settings() -> dict[str, Any]:
    """Load MikroTik settings from environment."""
    import os

    from dotenv import load_dotenv

    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")

    host = os.getenv("MIKROTIK_HOST") or "192.168.1.2"
    port_str = os.getenv("MIKROTIK_PORT")
    port = int(port_str) if port_str and port_str.strip() else 443
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


def get_pppoe_interfaces(settings: dict[str, Any], client: httpx.Client) -> list[dict[str, Any]]:
    """Filter only PPPoE interfaces."""
    interfaces = get_interfaces(settings, client)
    return [iface for iface in interfaces if iface.get("name", "").startswith("<pppoe-")]


def get_pppoe_ip_mappings(settings: dict[str, Any], client: httpx.Client) -> dict[str, str]:
    """Fetch IP address configurations and map interface names to their remote IP (network)."""
    try:
        url = f"{settings['scheme']}://{settings['host']}:{settings['port']}/rest/ip/address"
        response = client.get(url)
        response.raise_for_status()
        addresses = response.json()
        mappings = {}
        for addr in addresses:
            iface = addr.get("interface")
            network = addr.get("network")
            if iface and network:
                ip = network.split("/")[0]
                mappings[iface] = ip
        return mappings
    except Exception as e:
        print(f"Warning: Failed to fetch IP mappings: {e}")
        return {}


def _to_int(value: Any) -> int:
    """Convert value to int, handling strings and None."""
    if value is None:
        return 0
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


def format_bytes(bytes_val: int) -> str:
    """Format bytes to human-readable string."""
    if bytes_val < 1024:
        return f"{bytes_val:.0f} B"
    for unit in ["KB", "MB", "GB", "TB"]:
        bytes_val /= 1024.0
        if bytes_val < 1024.0:
            return f"{bytes_val:.2f} {unit}"
    return f"{bytes_val:.2f} PB"


def ping_client(settings: dict[str, Any], address: str, count: int = 4) -> dict[str, Any]:
    """Ping a client via RouterOS /tool/ping."""
    import asyncio

    async def _ping() -> dict[str, Any]:
        try:
            import asyncssh
        except ImportError:
            return {
                "status": "error",
                "error": "asyncssh not installed. Run: pip install asyncssh",
            }

        try:
            async with asyncssh.connect(
                settings["host"],
                port=settings.get("ssh_port", 22),
                username=settings["user"],
                password=settings["password"],
                known_hosts=None,
                connect_timeout=10.0,
            ) as conn:
                cmd = f"/ping address={address} count={count} interval=200ms"
                result = await conn.run(cmd, check=False, timeout=30.0)
                return {
                    "status": "ok",
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode,
                }
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(_ping())


def parse_duration_to_ms(val: str) -> float:
    """Convert RouterOS ping duration string (e.g. '14ms671us', '420us', '10.5ms') to float ms."""
    import re
    val = val.strip().lower()
    
    # Check if format matches ms + us, e.g. "14ms671us"
    m_ms_us = re.match(r'(\d+(?:\.\d+)?)ms(\d+(?:\.\d+)?)us', val)
    if m_ms_us:
        return float(m_ms_us.group(1)) + (float(m_ms_us.group(2)) / 1000.0)
        
    # Check if format matches ms only, e.g. "14ms"
    m_ms = re.match(r'(\d+(?:\.\d+)?)ms', val)
    if m_ms:
        return float(m_ms.group(1))
        
    # Check if format matches us only, e.g. "420us"
    m_us = re.match(r'(\d+(?:\.\d+)?)us', val)
    if m_us:
        return float(m_us.group(1)) / 1000.0
        
    # Fallback
    try:
        cleaned = re.sub(r'[^\d\.]', '', val)
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0


def parse_ping_output(stdout: str) -> dict[str, Any]:
    """Parse RouterOS ping output to extract statistics."""
    lines = stdout.strip().splitlines()
    sent = 0
    received = 0
    rtts = []

    for line in lines:
        line = line.strip()
        if "sent=" in line and "received=" in line:
            parts = line.split()
            for part in parts:
                if part.startswith("sent="):
                    try:
                        sent = int(part.split("=")[1])
                    except (ValueError, IndexError):
                        pass
                elif part.startswith("received="):
                    try:
                        received = int(part.split("=")[1])
                    except (ValueError, IndexError):
                        pass
        elif "avg-rtt=" in line:
            parts = line.split()
            for part in parts:
                if part.startswith("min-rtt="):
                    try:
                        rtts.append(parse_duration_to_ms(part.split("=")[1]))
                    except (ValueError, IndexError):
                        pass
                if part.startswith("avg-rtt="):
                    try:
                        rtts.append(parse_duration_to_ms(part.split("=")[1]))
                    except (ValueError, IndexError):
                        pass
                if part.startswith("max-rtt="):
                    try:
                        rtts.append(parse_duration_to_ms(part.split("=")[1]))
                    except (ValueError, IndexError):
                        pass

    loss_pct = 0.0
    if sent > 0:
        loss_pct = ((sent - received) / sent) * 100.0

    avg_rtt = rtts[1] if len(rtts) >= 2 else (rtts[0] if rtts else 0.0)
    min_rtt = rtts[0] if rtts else 0.0
    max_rtt = rtts[2] if len(rtts) >= 3 else avg_rtt
    jitter = max_rtt - min_rtt if rtts else 0.0

    return {
        "sent": sent,
        "received": received,
        "loss_pct": round(loss_pct, 2),
        "avg_rtt": round(avg_rtt, 2),
        "min_rtt": round(min_rtt, 2),
        "max_rtt": round(max_rtt, 2),
        "jitter": round(jitter, 2),
    }


def calculate_cv(values: list[float]) -> float:
    """Calculate Coefficient of Variation (std/mean) as percentage."""
    if len(values) < 2:
        return 0.0
    mean = statistics.mean(values)
    if mean == 0:
        return 0.0
    stdev = statistics.stdev(values)
    return (stdev / mean) * 100.0


def calculate_score(cv_rx: float, cv_tx: float, loss_pct: float, jitter: float) -> int:
    """Calculate stability score (0-100). Higher is better."""
    # Throughput stability component (0-40 points)
    cv_avg = (cv_rx + cv_tx) / 2
    throughput_score = max(0, 40 - (cv_avg / 2.5))  # CV 0% = 40, CV 100% = 0

    # Packet loss component (0-30 points)
    loss_score = max(0, 30 - (loss_pct * 6))  # 0% loss = 30, 5% loss = 0

    # Jitter component (0-30 points)
    jitter_score = max(0, 30 - (jitter / 2.0))  # 0ms = 30, 60ms = 0

    total = int(throughput_score + loss_score + jitter_score)
    return min(100, max(0, total))


def get_status(score: int, loss_pct: float) -> str:
    """Classify connection status based on score and packet loss."""
    if score >= 80 and loss_pct == 0:
        return "🟢 STABLE"
    elif score >= 50:
        return "🟡 UNSTABLE"
    else:
        return "🔴 CRITICAL"


def monitor_pppoe_quality(
    settings: dict[str, Any],
    interval: float = 2.0,
    window: int = 30,
    ping_interval: int = 30,
    duration: int = 300,
    output_dir: str = "logs",
) -> None:
    """Monitor PPPoE interface quality for specified duration."""
    print("=" * 100)
    print(f"PPPoE Quality Monitor - {settings['host']}")
    print(f"Duration: {duration}s | Interval: {interval}s | Window: {window} | Ping every: {ping_interval}s")
    print("=" * 100)

    client = build_client(settings)
    start_time = time.time()
    last_ping_time = 0

    # Initialize tracking structures
    pppoe_ifaces = get_pppoe_interfaces(settings, client)
    if not pppoe_ifaces:
        print("No PPPoE interfaces found.")
        return

    print(f"Found {len(pppoe_ifaces)} PPPoE interfaces\n")

    # Rolling windows for throughput
    throughput_history: dict[str, deque] = {}
    for iface in pppoe_ifaces:
        throughput_history[iface["name"]] = {
            "rx": deque(maxlen=window),
            "tx": deque(maxlen=window),
        }

    # Ping results history
    ping_history: dict[str, dict[str, Any]] = {}
    for iface in pppoe_ifaces:
        ping_history[iface["name"]] = {
            "loss_pct": deque(maxlen=5),
            "jitter": deque(maxlen=5),
            "avg_rtt": deque(maxlen=5),
        }

    sample_count = 0
    last_throughput = {}

    try:
        while True:
            elapsed = time.time() - start_time
            if elapsed >= duration:
                break

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            current_ifaces = get_pppoe_interfaces(settings, client)
            current_names = {iface["name"] for iface in current_ifaces}

            # Remove interfaces that no longer exist
            for name in list(throughput_history.keys()):
                if name not in current_names:
                    del throughput_history[name]
                    del ping_history[name]

            # Add new interfaces
            for iface in current_ifaces:
                name = iface["name"]
                if name not in throughput_history:
                    throughput_history[name] = {"rx": deque(maxlen=window), "tx": deque(maxlen=window)}
                    ping_history[name] = {
                        "loss_pct": deque(maxlen=5),
                        "jitter": deque(maxlen=5),
                        "avg_rtt": deque(maxlen=5),
                    }

            # Calculate throughput
            current_throughput = {}
            for iface in current_ifaces:
                name = iface["name"]
                rx_bytes = _to_int(iface.get("rx-byte", iface.get("bytes", 0)))
                tx_bytes = _to_int(iface.get("tx-byte", iface.get("tx-byte", 0)))

                if name in last_throughput:
                    rx_rate = rx_bytes - last_throughput[name]["rx"]
                    tx_rate = tx_bytes - last_throughput[name]["tx"]
                    rx_rate = max(0, rx_rate / interval)
                    tx_rate = max(0, tx_rate / interval)

                    throughput_history[name]["rx"].append(rx_rate)
                    throughput_history[name]["tx"].append(tx_rate)
                    current_throughput[name] = {"rx": rx_rate, "tx": tx_rate}

                last_throughput[name] = {"rx": rx_bytes, "tx": tx_bytes}

            # Periodic ping test
            if elapsed - last_ping_time >= ping_interval:
                last_ping_time = elapsed
                print(f"\n[{timestamp}] Running ping tests...")
                ip_mappings = get_pppoe_ip_mappings(settings, client)
                for iface in current_ifaces:
                    name = iface["name"]
                    ip_address = ip_mappings.get(name)
                    if not ip_address:
                        print(f"Skipping ping for {name}: no associated IP address found in /ip/address")
                        continue
                    ping_result = ping_client(settings, ip_address, count=3)
                    if ping_result.get("status") == "ok":
                        parsed = parse_ping_output(ping_result.get("stdout", ""))
                        ping_history[name]["loss_pct"].append(parsed["loss_pct"])
                        ping_history[name]["jitter"].append(parsed["jitter"])
                        ping_history[name]["avg_rtt"].append(parsed["avg_rtt"])

            # Display results
            print(f"\n[{timestamp}] Sample #{sample_count + 1}")
            print("-" * 100)
            print(
                f"{'Client':<20} {'RX Rate':<12} {'TX Rate':<12} {'CV%':<8} {'Jitter':<10} {'Loss%':<8} {'Score':<8} {'Status'}"
            )
            print("-" * 100)

            results = []
            for iface in current_ifaces:
                name = iface["name"]
                rx_hist = list(throughput_history[name]["rx"])
                tx_hist = list(throughput_history[name]["tx"])

                cv_rx = calculate_cv(rx_hist) if len(rx_hist) >= 2 else 0.0
                cv_tx = calculate_cv(tx_hist) if len(tx_hist) >= 2 else 0.0
                cv_avg = (cv_rx + cv_tx) / 2

                # Latest throughput
                rx_rate = current_throughput.get(name, {}).get("rx", 0.0)
                tx_rate = current_throughput.get(name, {}).get("tx", 0.0)

                # Ping metrics
                loss_pct = statistics.mean(ping_history[name]["loss_pct"]) if ping_history[name]["loss_pct"] else 0.0
                jitter = statistics.mean(ping_history[name]["jitter"]) if ping_history[name]["jitter"] else 0.0

                score = calculate_score(cv_rx, cv_tx, loss_pct, jitter)
                status = get_status(score, loss_pct)

                results.append({
                    "name": name,
                    "rx_rate": rx_rate,
                    "tx_rate": tx_rate,
                    "cv": cv_avg,
                    "jitter": jitter,
                    "loss_pct": loss_pct,
                    "score": score,
                    "status": status,
                })

            # Sort by score (worst first)
            results.sort(key=lambda x: x["score"])

            for res in results:
                print(
                    f"{res['name']:<20} {format_bytes(int(res['rx_rate'])):<12} {format_bytes(int(res['tx_rate'])):<12} "
                    f"{res['cv']:<8.1f} {res['jitter']:<10.1f} {res['loss_pct']:<8.1f} {res['score']:<8} {res['status']}"
                )

            sample_count += 1
            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user.")
    finally:
        client.close()

    # Generate final report
    generate_report(results, start_time, duration, output_dir)


async def publish_to_memory_server_sse(
    content: str, summary: str, category: str, tags: list[str], importance: int
) -> bool:
    """Attempt to publish a memory using the running MCP Memory Server over SSE."""
    try:
        from mcp.client.sse import sse_client
        from mcp import ClientSession

        url = "http://127.0.0.1:8001/sse"
        async with sse_client(url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                args = {
                    "namespace": "mikrotik",
                    "content": content,
                    "summary": summary,
                    "category": category,
                    "tags": tags,
                    "importance": importance,
                    "validation_status": "verified",
                    "source": "pppoe_quality_monitor",
                    "project": "mcp-mikrotik-bridge",
                }
                result = await session.call_tool("memory_store", arguments=args)
                print(f"[Ingest] Successfully saved via SSE server: {result}")
                return True
    except Exception as e:
        print(f"[Ingest] SSE server connection failed: {e}")
        return False


async def publish_to_memory_local(
    content: str, summary: str, category: str, tags: list[str], importance: int
) -> bool:
    """Fallback: Ingest directly into SQLite memory database using local engine."""
    try:
        import sys
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))

        from servers.memory import engine
        from shared.models import MemoryEntry

        entry = MemoryEntry(
            namespace="mikrotik",
            content=content,
            summary=summary,
            category=category,
            memory_type="semantic",
            validation_status="verified",
            tags=tags,
            importance=importance,
            source="pppoe_quality_monitor",
            project="mcp-mikrotik-bridge",
        )
        memory_id = await engine.store(entry)
        print(f"[Ingest] Successfully saved to local SQLite DB. Entry ID: {memory_id}")
        
        # Close connection to allow clean shutdown of aiosqlite threads
        if engine._db is not None:
            await engine._db.close()
            engine._db = None

        return True
    except Exception as e:
        print(f"[Ingest] Local SQLite database fallback failed: {e}")
        return False


def ingest_unstable_client_memory(
    client_name: str,
    status: str,
    cv: float,
    jitter: float,
    loss_pct: float,
    issues: list[str],
) -> None:
    """Save unstable client health event into long-term memory via MCP SSE or local DB fallback."""
    import asyncio

    content = (
        f"Interface PPPoE [{client_name}] is reported as [{status}]. "
        f"Throughput CV: {cv:.1f}%, Jitter: {jitter:.1f}ms, Packet Loss: {loss_pct:.1f}%. "
        f"Issues detected: {', '.join(issues) if issues else 'None'}."
    )
    summary = f"PPPoE client {client_name} unstable: CV {cv:.1f}%, loss {loss_pct:.1f}%"
    category = "error"
    tags = ["mikrotik", "pppoe", "unstable", client_name.strip("<>")]
    importance = 7 if "CRITICAL" in status else 5

    async def _run():
        success = await publish_to_memory_server_sse(content, summary, category, tags, importance)
        if not success:
            print("[Ingest] Falling back to direct SQLite write...")
            await publish_to_memory_local(content, summary, category, tags, importance)

    try:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            import threading
            threading.Thread(target=lambda: asyncio.run(_run())).start()
        else:
            loop.run_until_complete(_run())
    except Exception as e:
        print(f"Warning: Failed to execute ingestion task: {e}")


def generate_report(
    results: list[dict[str, Any]], start_time: float, duration: int, output_dir: str
) -> None:
    """Generate Markdown quality report."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = Path(output_dir) / f"pppoe_quality_monitor_{timestamp}.md"
    log_path = Path(output_dir) / f"pppoe_quality_monitor_{timestamp}.log"

    # Ensure output directory exists
    report_path.parent.mkdir(parents=True, exist_ok=True)

    report_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(report_path, "w") as f:
        f.write(f"# PPPoE Quality Monitoring Report\n\n")
        f.write(f"**Generated:** {report_time}  \n")
        f.write(f"**Duration:** {duration} seconds  \n")
        f.write(f"**Interfaces Monitored:** {len(results)} PPPoE clients\n\n")

        f.write("## Summary\n\n")
        f.write("| Ranking | Client | RX Avg | TX Avg | CV% | Jitter (ms) | Loss% | Score | Status |\n")
        f.write("|---------|--------|--------|--------|-----|-------------|-------|-------|--------|\n")

        for idx, res in enumerate(results, 1):
            rx_avg = format_bytes(int(res["rx_rate"]))
            tx_avg = format_bytes(int(res["tx_rate"]))
            f.write(
                f"| {idx} | {res['name']} | {rx_avg} | {tx_avg} | "
                f"{res['cv']:.1f}% | {res['jitter']:.1f} | {res['loss_pct']:.1f}% | "
                f"{res['score']} | {res['status']} |\n"
            )

        # Unstable clients section
        unstable = [r for r in results if "UNSTABLE" in r["status"] or "CRITICAL" in r["status"]]
        if unstable:
            f.write("\n## ⚠️ Unstable Clients (Prioritized)\n\n")
            for res in unstable:
                f.write(f"- **{res['name']}**: {res['status']}\n")
                f.write(f"  - CV: {res['cv']:.1f}%, Jitter: {res['jitter']:.1f}ms, Loss: {res['loss_pct']:.1f}%\n")
                issues = []
                if res["cv"] > 70:
                    issues.append("High throughput fluctuation")
                elif res["cv"] > 30:
                    issues.append("Moderate throughput fluctuation")
                if res["loss_pct"] > 5:
                    issues.append("High packet loss")
                elif res["loss_pct"] > 0:
                    issues.append("Some packet loss")
                if res["jitter"] > 20:
                    issues.append("High jitter")
                if issues:
                    f.write(f"  - Issues: {', '.join(issues)}\n")

        f.write("\n## Recommendations\n\n")
        critical_count = sum(1 for r in results if "CRITICAL" in r["status"])
        unstable_count = sum(1 for r in results if "UNSTABLE" in r["status"])
        stable_count = sum(1 for r in results if "STABLE" in r["status"])

        f.write(f"- 🟢 Stable: {stable_count} clients\n")
        f.write(f"- 🟡 Unstable: {unstable_count} clients\n")
        f.write(f"- 🔴 Critical: {critical_count} clients\n\n")

        if critical_count > 0:
            f.write("**Action Required:** Check physical connection, signal strength, and MTU settings for critical clients.\n")
        elif unstable_count > 0:
            f.write("**Recommendation:** Monitor unstable clients for potential degradation.\n")
        else:
            f.write("**All clients are stable.**\n")

        f.write("\n---\n*Report generated by mikrotik_pppoe_quality_monitor.py*\n")

    print(f"\n\nReport saved to: {report_path}")
    print(f"Log saved to: {log_path}")

    # Recommendation 3: Ingest unstable/critical PPPoE clients directly to memory
    unstable_clients = [r for r in results if "UNSTABLE" in r["status"] or "CRITICAL" in r["status"]]
    if unstable_clients:
        print(f"\n[Ingest] Found {len(unstable_clients)} unstable client(s). Publishing metrics to mcp-memory-server...")
        for res in unstable_clients:
            issues = []
            if res["cv"] > 70:
                issues.append("High throughput fluctuation")
            elif res["cv"] > 30:
                issues.append("Moderate throughput fluctuation")
            if res["loss_pct"] > 5:
                issues.append("High packet loss")
            elif res["loss_pct"] > 0:
                issues.append("Some packet loss")
            if res["jitter"] > 20:
                issues.append("High jitter")
            
            try:
                ingest_unstable_client_memory(
                    client_name=res["name"],
                    status=res["status"],
                    cv=res["cv"],
                    jitter=res["jitter"],
                    loss_pct=res["loss_pct"],
                    issues=issues
                )
            except Exception as e:
                print(f"Warning: Failed to ingest memory for {res['name']}: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Monitor PPPoE interface quality in real-time")
    parser.add_argument("--interval", type=float, default=2.0, help="Polling interval in seconds (default: 2.0)")
    parser.add_argument("--window", type=int, default=30, help="Rolling window size for CV calculation (default: 30)")
    parser.add_argument("--ping-interval", type=int, default=30, help="Ping test interval in seconds (default: 30)")
    parser.add_argument("--duration", type=int, default=300, help="Monitoring duration in seconds (default: 300 = 5 min)")
    parser.add_argument("--output", type=str, default="logs", help="Output directory for reports (default: logs/)")
    args = parser.parse_args()

    try:
        settings = get_settings()
        monitor_pppoe_quality(
            settings=settings,
            interval=args.interval,
            window=args.window,
            ping_interval=args.ping_interval,
            duration=args.duration,
            output_dir=args.output,
        )
    except Exception as e:
        print(f"Fatal error: {e}")
        return 1
    return 0


if __name__ == "__main__":
    exit(main() or 0)