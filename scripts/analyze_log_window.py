#!/usr/bin/env python3
"""Analisis entri log MikroTik pada rentang waktu tertentu dari file JSONL.

Usage: analyze_log_window.py <clientlog.jsonl> "YYYY-MM-DD HH:MM:SS" "YYYY-MM-DD HH:MM:SS" [out.md]
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

JSONL = Path(sys.argv[1])
START = sys.argv[2]
END = sys.argv[3]
OUT = (
    Path(sys.argv[4])
    if len(sys.argv) > 4
    else JSONL.with_name(
        f"{JSONL.stem}_window_{START[11:13]}{START[14:16]}-{END[11:13]}{END[14:16]}.md"
    )
)


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
    for line in JSONL.read_text().splitlines():
        e = json.loads(line)
        if "_snapshot" in e:
            continue
        t = e.get("time", "")
        if START <= t <= END:
            entries.append(e)
    entries.sort(key=lambda e: e.get("time", ""))

    logins, logouts, errors, links, admin, other = [], [], [], [], [], []
    rx_login = re.compile(r"(\S+) logged in, (\S+) from ([0-9A-F:]+)")
    rx_logout = re.compile(r"(\S+) logged out, (\d+) (\d+) (\d+) (\d+) (\d+) from (\S+)")
    for e in entries:
        t, msg, topics = e.get("time", ""), e.get("message", ""), e.get("topics", "")
        m = rx_login.search(msg)
        if m and "pppoe" in topics:
            logins.append((t, m.group(1), m.group(2), m.group(3)))
            continue
        m = rx_logout.search(msg)
        if m and "pppoe" in topics:
            logouts.append(
                (
                    t,
                    m.group(1),
                    int(m.group(2)),
                    int(m.group(3)),
                    int(m.group(4)),
                    int(m.group(5)),
                    int(m.group(6)),
                    m.group(7),
                )
            )
            continue
        if "error" in topics or "critical" in topics or "warning" in topics:
            errors.append((t, topics, msg))
        elif "interface" in topics:
            links.append((t, msg))
        elif "account" in topics and "system" in topics:
            admin.append((t, msg))
        else:
            other.append((t, topics, msg))

    per_client = defaultdict(lambda: {"sessions": 0, "dur": 0, "rx": 0, "tx": 0})
    for t, user, dur, rx_b, tx_b, rx_p, tx_p, mac in logouts:
        c = per_client[user]
        c["sessions"] += 1
        c["dur"] += dur
        c["rx"] += rx_b
        c["tx"] += tx_b

    # hitung flap per interface
    flap = defaultdict(int)
    for t, msg in links:
        iface = msg.split(" link ")[0] if " link " in msg else msg.split()[0]
        flap[iface] += 1

    L = []
    L.append(f"# 📋 Laporan Aktivitas Log MikroTik — {START} s/d {END} WIB")
    L.append("")
    L.append("| Parameter | Nilai |")
    L.append("|---|---|")
    L.append("| **Router** | `<REDACTED>` (hEX S, RouterOS 7.19.6) |")
    L.append(f"| **Window analisis** | {START} – {END} WIB |")
    L.append("| **Sumber data** | Baseline buffer router (diambil 22:58, mencakup 09:46–22:52) |")
    L.append(f"| **Total entri dalam window** | {len(entries)} |")
    L.append(f"| **PPPoE login / logout** | {len(logins)} / {len(logouts)} |")
    L.append(f"| **Event interface** | {len(links)} |")
    L.append(f"| **Error/warning** | {len(errors)} |")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## 1. Sesi PPPoE — Login")
    L.append("")
    if logins:
        L.append("| Waktu | User | IP | MAC |")
        L.append("|---|---|---|---|")
        for t, u, ip, mac in logins:
            L.append(f"| {t[11:]} | `{u}` | {ip} | `{mac}` |")
    else:
        L.append("- Tidak ada login baru.")
    L.append("")
    L.append("## 2. Sesi PPPoE — Logout (durasi & pemakaian)")
    L.append("")
    if logouts:
        L.append("| Waktu | User | Durasi Sesi | RX (download) | TX (upload) | MAC |")
        L.append("|---|---|---|---|---|---|")
        for t, u, dur, rxb, txb, rxp, txp, mac in logouts:
            L.append(
                f"| {t[11:]} | `{u}` | {fmt_dur(dur)} | {fmt_bytes(rxb)} | {fmt_bytes(txb)} | `{mac}` |"
            )
    else:
        L.append("- Tidak ada logout.")
    L.append("")
    if per_client:
        L.append("## 3. Agregat per Klien (sesi berakhir dalam window)")
        L.append("")
        L.append("| User | Sesi | Total Durasi | Total RX | Total TX |")
        L.append("|---|---|---|---|---|")
        for u, c in sorted(
            per_client.items(), key=lambda kv: kv[1]["rx"] + kv[1]["tx"], reverse=True
        ):
            L.append(
                f"| `{u}` | {c['sessions']} | {fmt_dur(c['dur'])} | {fmt_bytes(c['rx'])} | {fmt_bytes(c['tx'])} |"
            )
        L.append("")
    L.append("---")
    L.append("")
    L.append("## 4. Event Interface (link up/down)")
    L.append("")
    if links:
        if flap:
            L.append(
                "**Frekuensi per interface:** "
                + ", ".join(f"`{k}` {v}×" for k, v in sorted(flap.items(), key=lambda x: -x[1]))
            )
            L.append("")
        L.append("| Waktu | Pesan |")
        L.append("|---|---|")
        for t, msg in links:
            L.append(f"| {t[11:]} | {msg} |")
    else:
        L.append("- Tidak ada event interface.")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## 5. Error / Warning / Critical")
    L.append("")
    if errors:
        L.append("| Waktu | Topik | Pesan |")
        L.append("|---|---|---|")
        for t, topics, msg in errors:
            L.append(f"| {t[11:]} | {topics} | {msg} |")
    else:
        L.append("- Tidak ada error.")
    L.append("")
    if other:
        L.append("## 6. Event Lainnya")
        L.append("")
        L.append("| Waktu | Topik | Pesan |")
        L.append("|---|---|---|")
        for t, topics, msg in other:
            L.append(f"| {t[11:]} | {topics} | {msg} |")
        L.append("")
    L.append("---")
    L.append("")
    L.append("## 7. Kronologi Lengkap (semua entri dalam window)")
    L.append("")
    L.append("```")
    for e in entries:
        L.append(f"[{e.get('time')}] ({e.get('topics')}) {e.get('message')}")
    L.append("```")
    L.append("")

    OUT.write_text("\n".join(L) + "\n")
    print(f"OK -> {OUT}")
    print(
        f"entries={len(entries)} logins={len(logins)} logouts={len(logouts)} "
        f"links={len(links)} errors={len(errors)} admin={len(admin)} other={len(other)}"
    )


if __name__ == "__main__":
    main()
