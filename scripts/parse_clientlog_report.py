#!/usr/bin/env python3
"""Parse mikrotik_clientlog_raw JSONL -> laporan markdown aktivitas klien.

Usage: python scripts/parse_clientlog_report.py <clientlog.jsonl> [window_start "YYYY-MM-DD HH:MM:SS"] [out.md]
window_start opsional: entri SEBELUM waktu ini dianggap baseline (di luar window).
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

JSONL = Path(sys.argv[1])
WINDOW_START = sys.argv[2] if len(sys.argv) > 2 else ""
OUT = Path(sys.argv[3]) if len(sys.argv) > 3 else JSONL.with_name(
    JSONL.name.replace("_raw_", "_report_").replace(".jsonl", ".md"))


def fmt_bytes(n: float) -> str:
    for u in ["B", "KB", "MB", "GB", "TB"]:
        if abs(n) < 1024.0:
            return f"{n:.2f} {u}"
        n /= 1024.0
    return f"{n:.2f} PB"


def fmt_dur(sec: float) -> str:
    sec = int(sec)
    h, sec = divmod(sec, 3600)
    m, s = divmod(sec, 60)
    return f"{h}j {m}m {s}d" if h else (f"{m}m {s}d" if m else f"{s}d")


def main() -> None:
    entries = []
    snap_start = snap_end = None
    for line in JSONL.read_text().splitlines():
        e = json.loads(line)
        if e.get("_snapshot") == "ppp_active_start":
            snap_start = e
        elif e.get("_snapshot") == "ppp_active_end":
            snap_end = e
        else:
            entries.append(e)

    win = [e for e in entries if e.get("time", "") >= WINDOW_START]
    base = [e for e in entries if e.get("time", "") < WINDOW_START]

    logins, logouts, errors, links, admin = [], [], [], [], []
    rx_login = re.compile(r"(\S+) logged in, (\S+) from ([0-9A-F:]+)")
    rx_logout = re.compile(r"(\S+) logged out, (\d+) (\d+) (\d+) (\d+) (\d+) from (\S+)")
    for e in win:
        t, msg = e.get("time", ""), e.get("message", "")
        topics = e.get("topics", "")
        m = rx_login.search(msg)
        if m and "pppoe" in topics:
            logins.append((t, m.group(1), m.group(2), m.group(3)))
            continue
        m = rx_logout.search(msg)
        if m and "pppoe" in topics:
            logouts.append((t, m.group(1), int(m.group(2)), int(m.group(3)),
                            int(m.group(4)), int(m.group(5)), int(m.group(6)), m.group(7)))
            continue
        if "error" in topics or "critical" in topics or "warning" in topics:
            errors.append((t, topics, msg))
        elif "interface" in topics:
            links.append((t, msg))
        elif "account" in topics and "system" in topics:
            admin.append((t, msg))

    per_client = defaultdict(lambda: {"sessions": 0, "dur": 0, "rx": 0, "tx": 0})
    for t, user, dur, rx_b, tx_b, rx_p, tx_p, mac in logouts:
        c = per_client[user]
        c["sessions"] += 1
        c["dur"] += dur
        c["rx"] += rx_b
        c["tx"] += tx_b

    L = []
    L.append("# 📋 Laporan Aktivitas Klien MikroTik (dari Log Router)")
    L.append("")
    L.append("| Parameter | Nilai |")
    L.append("|---|---|")
    L.append("| **Router** | `<REDACTED>` (hEX S, RouterOS 7.19.6) |")
    L.append(f"| **Window penangkapan** | {WINDOW_START} WIB s/d selesai (20 menit) |")
    L.append("| **Metode** | Polling `/rest/log` tiap 15 dtk (tanpa mengubah konfigurasi router) |")
    L.append(f"| **Entri baru dalam window** | {len(win)} |")
    L.append(f"| **Sesi PPP aktif (awal → akhir)** | {len(snap_start['sessions']) if snap_start else '?'} → {len(snap_end['sessions']) if snap_end else '?'} |")
    L.append(f"| **File data mentah** | `{JSONL.name}` |")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## 1. Aktivitas Sesi PPPoE Klien (dalam window)")
    L.append("")
    if logins:
        L.append(f"### 🔵 Login ({len(logins)})")
        L.append("")
        L.append("| Waktu | User | IP diberikan | MAC |")
        L.append("|---|---|---|---|")
        for t, u, ip, mac in logins:
            L.append(f"| {t} | `{u}` | {ip} | `{mac}` |")
        L.append("")
    if logouts:
        L.append(f"### ⚪ Logout ({len(logouts)})")
        L.append("")
        L.append("| Waktu | User | Durasi Sesi | RX (download) | TX (upload) | MAC |")
        L.append("|---|---|---|---|---|---|")
        for t, u, dur, rxb, txb, rxp, txp, mac in logouts:
            L.append(f"| {t} | `{u}` | {fmt_dur(dur)} | {fmt_bytes(rxb)} | {fmt_bytes(txb)} | `{mac}` |")
        L.append("")
    if not logins and not logouts:
        L.append("- 😴 **Tidak ada klien yang login/logout selama 20 menit** — semua sesi stabil.")
        L.append("")
    if per_client:
        L.append("### Agregat per klien (sesi berakhir dalam window)")
        L.append("")
        L.append("| User | Sesi | Total Durasi | Total RX | Total TX |")
        L.append("|---|---|---|---|---|")
        for u, c in sorted(per_client.items(), key=lambda kv: kv[1]["rx"] + kv[1]["tx"], reverse=True):
            L.append(f"| `{u}` | {c['sessions']} | {fmt_dur(c['dur'])} | {fmt_bytes(c['rx'])} | {fmt_bytes(c['tx'])} |")
        L.append("")
    L.append("---")
    L.append("")
    L.append("## 2. Event Interface (link up/down)")
    L.append("")
    if links:
        L.append("| Waktu | Pesan |")
        L.append("|---|---|")
        for t, msg in links:
            L.append(f"| {t} | {msg} |")
    else:
        L.append("- ✅ Tidak ada link flap selama window.")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## 3. Error / Warning / Critical")
    L.append("")
    if errors:
        L.append("| Waktu | Topik | Pesan |")
        L.append("|---|---|---|")
        for t, topics, msg in errors:
            L.append(f"| {t} | {topics} | {msg} |")
    else:
        L.append("- ✅ Tidak ada error/warning selama window.")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## 4. Aktivitas Admin (system,account)")
    L.append("")
    if admin:
        L.append("| Waktu | Pesan |")
        L.append("|---|---|")
        for t, msg in admin:
            L.append(f"| {t} | {msg} |")
        L.append("")
        L.append("> Catatan: event login/logout `rest-api`/`api` berasal dari proses monitoring itu sendiri.")
    else:
        L.append("- Tidak ada aktivitas admin.")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## 5. Sesi PPP Aktif (snapshot akhir window)")
    L.append("")
    if snap_end:
        L.append("| User | IP | Uptime |")
        L.append("|---|---|---|")
        for s in sorted(snap_end["sessions"], key=lambda x: x.get("name", "")):
            L.append(f"| `{s.get('name','?')}` | {s.get('address','?')} | {s.get('uptime','?')} |")
    L.append("")
    L.append("---")
    L.append("")
    L.append(f"*Baseline pra-window: {len(base)} entri (±13 jam terakhir) juga tersimpan di file JSONL yang sama.*")

    OUT.write_text("\n".join(L) + "\n")
    print(f"OK -> {OUT}")
    print(f"window_entries={len(win)} logins={len(logins)} logouts={len(logouts)} "
          f"links={len(links)} errors={len(errors)} admin={len(admin)}")


if __name__ == "__main__":
    main()
