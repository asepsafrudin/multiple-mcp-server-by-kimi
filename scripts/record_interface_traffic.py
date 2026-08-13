#!/usr/bin/env python3
"""Record interface traffic (bandwidth and packets) on MikroTik RouterOS.

Polls the REST API for interface stats and writes to a daily CSV log.
Usage:
    python scripts/record_interface_traffic.py --interface ether5 --interval 5 --duration 10800
"""
import argparse
import csv
import time
from datetime import datetime
from pathlib import Path
import sys

# Add root directory to sys.path
root = Path(__file__).resolve().parents[1]
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

import scripts.mikrotik_throughput_monitor as mtm

def main() -> int:
    parser = argparse.ArgumentParser(description="Record MikroTik interface traffic and packet stats")
    parser.add_argument("--interface", "-i", default="ether5", help="Interface name to record (default: ether5)")
    parser.add_argument("--interval", "-n", type=float, default=5.0, help="Polling interval in seconds (default: 5.0)")
    parser.add_argument("--duration", "-d", type=int, default=10800, help="Recording duration in seconds (default: 10800 = 3 hours)")
    parser.add_argument("--output-dir", "-o", default="logs", help="Directory to save logs")
    args = parser.parse_args()

    settings = mtm.get_settings()
    client = mtm.build_client(settings)

    out_dir = root / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    
    date_str = datetime.now().strftime("%Y%m%d")
    csv_file = out_dir / f"traffic_{args.interface}_{date_str}.csv"
    
    file_exists = csv_file.exists()
    
    print(f"Recording traffic for interface '{args.interface}'...")
    print(f"Sampling every {args.interval}s for {args.duration}s (~{args.duration/3600:.1f} hours).")
    print(f"Logging to: {csv_file}")
    
    start_time = time.time()
    end_time = start_time + args.duration
    
    # Store initial counters
    prev_rx_bytes = 0
    prev_tx_bytes = 0
    prev_rx_pkts = 0
    prev_tx_pkts = 0
    prev_ts = time.time()
    
    # Fetch first sample for comparison
    try:
        iface = mtm.get_interface_by_name(settings, client, args.interface)
        if not iface:
            print(f"Error: Interface '{args.interface}' not found.")
            return 1
        
        prev_rx_bytes = mtm._to_int(iface.get("rx-byte", iface.get("bytes", 0)))
        prev_tx_bytes = mtm._to_int(iface.get("tx-byte", iface.get("tx-byte", 0)))
        prev_rx_pkts = mtm._to_int(iface.get("rx-packet", iface.get("packets", 0)))
        prev_tx_pkts = mtm._to_int(iface.get("tx-packet", iface.get("packets", 0)))
        prev_ts = time.time()
        print("Initial connection successful. Recording started...")
    except Exception as e:
        print(f"Initial connection failed: {e}")
        return 1

    try:
        with open(csv_file, mode="a", newline="") as f:
            writer = csv.writer(f)
            if not file_exists:
                # Write header
                writer.writerow([
                    "timestamp", "interface",
                    "rx_bytes_total", "tx_bytes_total",
                    "rx_pkts_total", "tx_pkts_total",
                    "rx_bps", "tx_bps",
                    "rx_pps", "tx_pps"
                ])
                f.flush()

            while time.time() < end_time:
                time.sleep(args.interval)
                current_ts = time.time()
                dt_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                try:
                    iface = mtm.get_interface_by_name(settings, client, args.interface)
                    if not iface:
                        print(f"[{dt_str}] Warning: Interface '{args.interface}' disappeared.")
                        continue
                        
                    rx_bytes = mtm._to_int(iface.get("rx-byte", iface.get("bytes", 0)))
                    tx_bytes = mtm._to_int(iface.get("tx-byte", iface.get("tx-byte", 0)))
                    rx_pkts = mtm._to_int(iface.get("rx-packet", iface.get("packets", 0)))
                    tx_pkts = mtm._to_int(iface.get("tx-packet", iface.get("packets", 0)))
                    
                    time_diff = current_ts - prev_ts
                    if time_diff <= 0:
                        time_diff = args.interval
                        
                    # Calculate rates
                    # Avoid negative values on counter reset/reconnect
                    rx_bytes_delta = max(0, rx_bytes - prev_rx_bytes)
                    tx_bytes_delta = max(0, tx_bytes - prev_tx_bytes)
                    rx_pkts_delta = max(0, rx_pkts - prev_rx_pkts)
                    tx_pkts_delta = max(0, tx_pkts - prev_tx_pkts)
                    
                    rx_bps = int((rx_bytes_delta * 8) / time_diff)
                    tx_bps = int((tx_bytes_delta * 8) / time_diff)
                    rx_pps = round(rx_pkts_delta / time_diff, 1)
                    tx_pps = round(tx_pkts_delta / time_diff, 1)
                    
                    writer.writerow([
                        dt_str, args.interface,
                        rx_bytes, tx_bytes,
                        rx_pkts, tx_pkts,
                        rx_bps, tx_bps,
                        rx_pps, tx_pps
                    ])
                    f.flush()
                    
                    # Update previous values
                    prev_rx_bytes = rx_bytes
                    prev_tx_bytes = tx_bytes
                    prev_rx_pkts = rx_pkts
                    prev_tx_pkts = tx_pkts
                    prev_ts = current_ts
                    
                except Exception as e:
                    print(f"[{dt_str}] Error polling interface stats: {e}")
                    # Try to reconstruct client connection
                    try:
                        client.close()
                    except:
                        pass
                    client = mtm.build_client(settings)
                    
    except KeyboardInterrupt:
        print("\nRecording stopped by user.")
    finally:
        client.close()
        print("Recording finished.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
