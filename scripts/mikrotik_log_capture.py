#!/usr/bin/env python3
"""Tangkap log RouterOS selama durasi tertentu via polling REST /rest/log.

Setiap entri baru ditulis ke file JSONL + TXT di /home/aseps/MCP/logs/.
Toleran putus koneksi: error -> tunggu & lanjut. Berhenti otomatis
setelah DURATION_SEC detik.

Usage: python scripts/mikrotik_log_capture.py [duration_min=20] [poll_sec=15]
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

import mikrotik_throughput_monitor as mtm  # noqa: E402

DURATION_SEC = int(float(sys.argv[1]) * 60) if len(sys.argv) > 1 else 20 * 60
POLL_SEC = int(sys.argv[2]) if len(sys.argv) > 2 else 15
TS = datetime.now().strftime("%Y%m%d_%H%M%S")
LOGS_DIR = Path(__file__).resolve().parents[1] / "logs"
JSONL = LOGS_DIR / f"mikrotik_clientlog_raw_{TS}.jsonl"
TXT = LOGS_DIR / f"mikrotik_clientlog_raw_{TS}.txt"


def fetch_log(client, settings):
    url = f"{settings['scheme']}://{settings['host']}:{settings['port']}/rest/log"
    return client.get(url).json()


def main() -> None:
    settings = mtm.get_settings()
    client = mtm.build_client(settings)
    seen = set()
    total = 0
    errors = 0
    start = time.time()
    deadline = start + DURATION_SEC

    print(f"START {datetime.now():%Y-%m-%d %H:%M:%S} -> {JSONL.name}", flush=True)
    with JSONL.open("a") as fj, TXT.open("a") as ft:
        # snapshot sesi PPPoE aktif di awal
        try:
            url = f"{settings['scheme']}://{settings['host']}:{settings['port']}/rest/ppp/active"
            act = client.get(url).json()
            fj.write(
                json.dumps(
                    {
                        "_snapshot": "ppp_active_start",
                        "time": f"{datetime.now():%Y-%m-%d %H:%M:%S}",
                        "sessions": act,
                    }
                )
                + "\n"
            )
            print(f"snapshot awal: {len(act)} sesi ppp aktif", flush=True)
        except Exception as e:
            print(f"snapshot awal gagal: {e}", flush=True)

        poll = 0
        while time.time() < deadline:
            poll += 1
            try:
                entries = fetch_log(client, settings)
                new = []
                for e in entries:
                    key = (e.get("time"), e.get("topics"), e.get("message"))
                    if key not in seen:
                        seen.add(key)
                        new.append(e)
                for e in new:
                    fj.write(json.dumps(e) + "\n")
                    ft.write(f"[{e.get('time')}] ({e.get('topics')}) {e.get('message')}\n")
                fj.flush()
                ft.flush()
                total += len(new)
                print(
                    f"poll {poll:3d} {datetime.now():%H:%M:%S}: +{len(new)} baru (total {total})",
                    flush=True,
                )
            except Exception as e:
                errors += 1
                print(f"poll {poll:3d} ERROR #{errors}: {e}", flush=True)
                try:
                    client.close()
                except Exception:
                    pass
                client = mtm.build_client(settings)
            time.sleep(POLL_SEC)

        # snapshot sesi PPPoE aktif di akhir
        try:
            url = f"{settings['scheme']}://{settings['host']}:{settings['port']}/rest/ppp/active"
            act = client.get(url).json()
            fj.write(
                json.dumps(
                    {
                        "_snapshot": "ppp_active_end",
                        "time": f"{datetime.now():%Y-%m-%d %H:%M:%S}",
                        "sessions": act,
                    }
                )
                + "\n"
            )
            print(f"snapshot akhir: {len(act)} sesi ppp aktif", flush=True)
        except Exception as e:
            print(f"snapshot akhir gagal: {e}", flush=True)

    print(
        f"DONE {datetime.now():%Y-%m-%d %H:%M:%S} total={total} entri, errors={errors}", flush=True
    )
    client.close()


if __name__ == "__main__":
    main()
