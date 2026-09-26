#!/usr/bin/env python3
"""Parse throughput monitor raw log -> markdown report.

Usage: python scripts/parse_throughput_report.py <raw_log.txt> [out.md]
"""
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

LOG = Path(sys.argv[1])
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else LOG.with_name(
    LOG.name.replace("_raw_", "_report_").replace(".txt", ".md"))

UNITS = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}

ROW = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+"
    r"(\S+)\s+"
    r"([\d.]+) (B|KB|MB|GB|TB)\s+"
    r"([\d.]+) (B|KB|MB|GB|TB)\s+"
    r"(\d+)\s+(\d+)\s+"
    r"(?:(\d+(?:\.\d+)?) (B|KB|MB|GB|TB)/s|(N/A))\s+"
    r"(?:(\d+(?:\.\d+)?) (B|KB|MB|GB|TB)/s|(N/A))\s*$"
)


def to_bytes(val: str, unit: str) -> int:
    return int(float(val) * UNITS[unit])


def fmt(b: float) -> str:
    for u in ["B", "KB", "MB", "GB", "TB"]:
        if abs(b) < 1024.0:
            return f"{b:.2f} {u}"
        b /= 1024.0
    return f"{b:.2f} PB"


def main() -> None:
    text = LOG.read_text()
    host = re.search(r"MikroTik Throughput Monitor - (\S+)", text).group(1)
    meta = re.search(r"Interface: (\S+) \| Interval: ([\d.]+)s \| Count: (\d+)", text)

    rx_rates = defaultdict(list)
    tx_rates = defaultdict(list)
    first_rx, first_tx, last_rx, last_tx = {}, {}, {}, {}
    first_pkt, last_pkt = {}, {}
    timestamps = set()

    for line in text.splitlines():
        m = ROW.match(line)
        if not m:
            continue
        ts, name = m.group(1), m.group(2)
        timestamps.add(ts)
        rx_b = to_bytes(m.group(3), m.group(4))
        tx_b = to_bytes(m.group(5), m.group(6))
        rx_p, tx_p = int(m.group(7)), int(m.group(8))
        if name not in first_rx:
            first_rx[name], first_tx[name] = rx_b, tx_b
            first_pkt[name] = (rx_p, tx_p)
        last_rx[name], last_tx[name] = rx_b, tx_b
        last_pkt[name] = (rx_p, tx_p)
        if m.group(9):
            rx_rates[name].append(to_bytes(m.group(9), m.group(10)))
        if m.group(12):
            tx_rates[name].append(to_bytes(m.group(12), m.group(13)))

    n_iter = len(timestamps)
    t0 = datetime.strptime(min(timestamps), "%Y-%m-%d %H:%M:%S")
    t1 = datetime.strptime(max(timestamps), "%Y-%m-%d %H:%M:%S")
    dur = (t1 - t0).total_seconds()

    rows = []
    for name in last_rx:
        d_rx = last_rx[name] - first_rx[name]
        d_tx = last_tx[name] - first_tx[name]
        rxs, txs = rx_rates.get(name, []), tx_rates.get(name, [])
        rows.append({
            "name": name, "d_rx": d_rx, "d_tx": d_tx,
            "rx_avg": sum(rxs) / len(rxs) if rxs else 0.0,
            "rx_max": max(rxs) if rxs else 0.0,
            "tx_avg": sum(txs) / len(txs) if txs else 0.0,
            "tx_max": max(txs) if txs else 0.0,
            "rx_pkts": last_pkt[name][0] - first_pkt[name][0],
            "tx_pkts": last_pkt[name][1] - first_pkt[name][1],
            "active": (d_rx + d_tx) > 0,
        })

    active = [r for r in rows if r["active"]]
    idle = [r for r in rows if not r["active"]]
    pppoe = [r for r in rows if r["name"].startswith("<pppoe-")]
    phys = [r for r in active if not r["name"].startswith("<pppoe-")]
    tot_rx = sum(r["d_rx"] for r in phys if r["d_rx"] > 0)
    tot_tx = sum(r["d_tx"] for r in phys if r["d_tx"] > 0)
    top_rx = sorted(active, key=lambda r: r["d_rx"], reverse=True)[:5]
    top_tx = sorted(active, key=lambda r: r["d_tx"], reverse=True)[:5]

    L = []
    L.append("# 📊 Laporan Monitoring Throughput MikroTik")
    L.append("")
    L.append("| Parameter | Nilai |")
    L.append("|---|---|")
    L.append(f"| **Router** | `{host}` |")
    L.append(f"| **Waktu mulai** | {t0:%Y-%m-%d %H:%M:%S} WIB |")
    L.append(f"| **Waktu selesai** | {t1:%Y-%m-%d %H:%M:%S} WIB |")
    L.append(f"| **Durasi monitoring** | {int(dur)} detik (~{dur/60:.1f} menit) |")
    L.append(f"| **Interval sampling** | {meta.group(2)} detik |")
    L.append(f"| **Jumlah iterasi** | {n_iter} sampel |")
    L.append(f"| **Interface termonitor** | {len(rows)} ({len(active)} aktif, {len(idle)} idle) |")
    L.append(f"| **File data mentah** | `{LOG.name}` |")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## 1. Ringkasan Eksekutif")
    L.append("")
    L.append(f"- **Total trafik interface fisik/non-PPPoE selama window**: RX **{fmt(tot_rx)}**, TX **{fmt(tot_tx)}**")
    if phys:
        busiest = max(phys, key=lambda r: r["rx_avg"])
        L.append(f"- **Interface tersibuk (rata-rata RX)**: `{busiest['name']}` — {fmt(busiest['rx_avg'])}/s RX, {fmt(busiest['tx_avg'])}/s TX")
    pppoe_active = [r for r in pppoe if r["active"]]
    L.append(f"- **Klien PPPoE aktif**: {len(pppoe_active)} dari {len(pppoe)} sesi terpantau")
    if idle:
        idle_names = ", ".join(f"`{r['name']}`" for r in idle)
        L.append(f"- **Interface idle (tanpa trafik)**: {idle_names}")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## 2. Statistik Interface Fisik / Statis")
    L.append("")
    L.append("| Interface | RX Total | TX Total | RX Avg | RX Max | TX Avg | TX Max |")
    L.append("|---|---|---|---|---|---|---|")
    for r in sorted(phys, key=lambda x: x["d_rx"] + x["d_tx"], reverse=True):
        L.append(f"| `{r['name']}` | {fmt(r['d_rx'])} | {fmt(r['d_tx'])} | "
                 f"{fmt(r['rx_avg'])}/s | {fmt(r['rx_max'])}/s | "
                 f"{fmt(r['tx_avg'])}/s | {fmt(r['tx_max'])}/s |")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## 3. Statistik Klien PPPoE")
    L.append("")
    L.append("| Klien | RX Total | TX Total | RX Avg | RX Max | TX Avg | TX Max |")
    L.append("|---|---|---|---|---|---|---|")
    for r in sorted(pppoe, key=lambda x: x["d_rx"] + x["d_tx"], reverse=True):
        L.append(f"| `{r['name']}` | {fmt(r['d_rx'])} | {fmt(r['d_tx'])} | "
                 f"{fmt(r['rx_avg'])}/s | {fmt(r['rx_max'])}/s | "
                 f"{fmt(r['tx_avg'])}/s | {fmt(r['tx_max'])}/s |")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## 4. Top 5 Talkers (berdasarkan total data)")
    L.append("")
    L.append("### Download (RX) terbanyak")
    L.append("")
    L.append("| # | Interface | RX Total | RX Avg | RX Packets |")
    L.append("|---|---|---|---|---|")
    for i, r in enumerate(top_rx, 1):
        L.append(f"| {i} | `{r['name']}` | {fmt(r['d_rx'])} | {fmt(r['rx_avg'])}/s | {r['rx_pkts']:,} |")
    L.append("")
    L.append("### Upload (TX) terbanyak")
    L.append("")
    L.append("| # | Interface | TX Total | TX Avg | TX Packets |")
    L.append("|---|---|---|---|---|")
    for i, r in enumerate(top_tx, 1):
        L.append(f"| {i} | `{r['name']}` | {fmt(r['d_tx'])} | {fmt(r['tx_avg'])}/s | {r['tx_pkts']:,} |")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## 5. Temuan & Catatan")
    L.append("")
    notes = []
    for r in rows:
        if r["d_rx"] < 0 or r["d_tx"] < 0:
            notes.append(f"- ⚠️ `{r['name']}`: counter menurun (kemungkinan sesi PPPoE reconnect/reset selama monitoring).")
    for r in idle:
        notes.append(f"- ℹ️ `{r['name']}`: tidak ada trafik sama sekali selama monitoring (link down / tidak dipakai).")
    if pppoe:
        quiet = [r for r in pppoe if r["active"] and 0 < (r["d_rx"] + r["d_tx"]) < 1024 * 1024]
        if quiet:
            notes.append(f"- ℹ️ {len(quiet)} klien PPPoE hampir idle (<1 MB total): online tapi tidak aktif.")
    heavy = [r for r in active if r["rx_max"] > 50 * 1024**2 or r["tx_max"] > 50 * 1024**2]
    for r in heavy:
        notes.append(f"- 🔥 `{r['name']}`: spike di atas 50 MB/s (puncak RX {fmt(r['rx_max'])}/s, TX {fmt(r['tx_max'])}/s).")
    if not notes:
        notes.append("- ✅ Tidak ada anomali; seluruh interface berjalan normal.")
    L.extend(notes)
    L.append("")
    L.append("---")
    L.append("")
    L.append(f"*Laporan dibuat otomatis dari `{LOG.name}` — {n_iter} sampel, interval {meta.group(2)}s.*")

    OUT.write_text("\n".join(L) + "\n")
    print(f"OK -> {OUT}")
    print(f"interfaces={len(rows)} active={len(active)} iters={n_iter} dur={dur}s")


if __name__ == "__main__":
    main()
