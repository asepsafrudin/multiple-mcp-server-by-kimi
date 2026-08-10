#!/usr/bin/env python3
"""Script to test MikroTik queue shaping by generating UDP traffic from the host to a PPPoE IP."""

import sys
import time
import socket
import asyncio
from pathlib import Path
from threading import Thread

# Add root directory to sys.path
root = Path(__file__).resolve().parents[1]
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from scripts.mikrotik_pppoe_quality_monitor import get_settings


def flood_udp(target_ip: str, target_port: int, duration: float, speed_kbps: int):
    """Flood UDP packets to a target IP at a determinado speed (in Kbps)."""
    # 1 packet = 1400 bytes
    packet_size = 1400 
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    data = b"X" * packet_size
    
    # Calculate intervals
    # speed_kbps = speed in kilobits per second
    # bytes_per_sec = speed_kbps * 1000 / 8
    bytes_per_sec = (speed_kbps * 125)
    packets_per_sec = bytes_per_sec / packet_size
    interval = 1.0 / packets_per_sec if packets_per_sec > 0 else 0.1
    
    print(f"[Flood] Starting UDP flood to {target_ip}:{target_port} at {speed_kbps} Kbps for {duration} seconds...")
    start_time = time.time()
    packets_sent = 0
    
    try:
        while time.time() - start_time < duration:
            t_send = time.time()
            sock.sendto(data, (target_ip, target_port))
            packets_sent += 1
            
            # Rate limiting
            elapsed_send = time.time() - t_send
            sleep_time = interval - elapsed_send
            if sleep_time > 0:
                time.sleep(sleep_time)
    except Exception as e:
        print(f"[Flood] Error during flood: {e}")
    finally:
        sock.close()
        total_time = time.time() - start_time
        actual_speed = (packets_sent * packet_size * 8) / (total_time * 1000000)
        print(f"[Flood] Finished. Sent {packets_sent} packets in {total_time:.2f}s (Average rate: {actual_speed:.2f} Mbps)")


async def monitor_queue(settings: dict, queue_name: str, duration: float):
    """Monitor simple queue stats via SSH during the test."""
    import asyncssh
    
    print(f"[Monitor] Connecting to MikroTik to monitor queue '{queue_name}'...")
    async with asyncssh.connect(
        settings["host"],
        port=settings.get("ssh_port", 22),
        username=settings["user"],
        password=settings["password"],
        known_hosts=None,
        connect_timeout=10.0,
    ) as conn:
        print(f"[Monitor] Monitoring queue rate for {duration} seconds (1s interval)...")
        time_elapsed = 0.0
        while time_elapsed < duration:
            # Print the rate and limit-at/max-limit
            cmd = f'/queue simple print o where name="{queue_name}"'
            res = await conn.run(cmd)
            lines = res.stdout.strip().splitlines()
            # Find rate details
            rate_line = ""
            for line in lines:
                if "rate=" in line or "max-limit=" in line or "bytes=" in line:
                    rate_line += "  " + line.strip()
            
            # Print snapshot
            print(f"[Monitor] Time: {int(time_elapsed)}s | Info:{rate_line if rate_line else ' Queue active'}")
            await asyncio.sleep(1.0)
            time_elapsed += 1.0


def main():
    settings = get_settings()
    
    # We will target Yudi (192.168.99.100) which has a limit of 2M (2000k)
    # We will flood at 5000 Kbps (5 Mbps), which is way above Yudi's limit
    target_ip = "192.168.99.100" 
    target_port = 9999
    flood_duration = 8.0 # 8 seconds
    rate_kbps = 5000 # 5 Mbps
    
    queue_name = "<pppoe-Yudi>"
    
    # Run flood in a background thread
    flood_thread = Thread(target=flood_udp, args=(target_ip, target_port, flood_duration, rate_kbps))
    
    # Start flood
    flood_thread.start()
    
    # Monitor queue rate in the main thread (async)
    asyncio.run(monitor_queue(settings, queue_name, flood_duration + 2.0))
    
    # Make sure thread is joined
    flood_thread.join()
    print("[Test] Completed.")


if __name__ == "__main__":
    main()
