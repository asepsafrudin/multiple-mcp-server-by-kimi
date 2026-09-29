#!/usr/bin/env python3
"""Resilient wrapper untuk mikrotik_throughput_monitor.

Loop per-iterasi dibungkus try/except: jika koneksi tunnel putus,
monitoring TIDAK berhenti — client dibuat ulang dan lanjut ke sampel
berikutnya. Hanya iterasi sukses yang dihitung menuju target count.
Output memakai format kolom yang sama dengan script asli agar parser
laporan tetap kompatibel.

Usage: python scripts/mikrotik_resilient_monitor.py [interval] [count]
"""

import sys
import time
from datetime import datetime

import mikrotik_throughput_monitor as mtm  # noqa: E402


def main() -> None:
    interval = float(sys.argv[1]) if len(sys.argv) > 1 else 5.0
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 120

    settings = mtm.get_settings()
    print("=" * 140)
    print(f"MikroTik Throughput Monitor - {settings['host']}")
    print(f"Interface: all | Interval: {interval}s | Count: {count} (resilient mode)")
    print("=" * 140)
    mtm.print_header()

    client = mtm.build_client(settings)
    prev: dict = {}
    ok = 0
    errors = 0
    started = datetime.now()

    while ok < count:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            interfaces = mtm.get_interfaces(settings, client)
            for iface in interfaces:
                name = iface["name"]
                rx_new = mtm._to_int(iface.get("rx-byte", iface.get("bytes", 0)))
                tx_new = mtm._to_int(iface.get("tx-byte", iface.get("tx-byte", 0)))
                p = prev.get(name, {})
                rx_rate = (
                    (rx_new - mtm._to_int(p.get("rx-byte", p.get("bytes", 0)))) / interval
                    if p
                    else None
                )
                tx_rate = (
                    (tx_new - mtm._to_int(p.get("tx-byte", p.get("tx-byte", 0)))) / interval
                    if p
                    else None
                )
                mtm.print_interface_stats(ts, iface, rx_rate, tx_rate)
                prev[name] = iface
            ok += 1
        except Exception as e:  # jaringan putus dll -> lanjut
            errors += 1
            print(f"{ts}  !! ERROR #{errors}: {e} -- lanjut ke iterasi berikutnya")
            try:
                client.close()
            except Exception:
                pass
            client = mtm.build_client(settings)
        time.sleep(interval)

    elapsed = (datetime.now() - started).total_seconds()
    print(f"\nSelesai: {ok} iterasi sukses, {errors} error, total waktu {elapsed:.0f}s.")
    client.close()


if __name__ == "__main__":
    main()
