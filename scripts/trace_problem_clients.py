#!/usr/bin/env python3
"""Lacak klien paling bermasalah dari baseline log + bridge host table.

Output: ranking masalah per klien + pemetaan MAC->port->user.
"""
Usage: python scripts/trace_problem_clients.py <clientlog.jsonl> [w0 w1] [out.md]
       w0/w1 = window fokus "YYYY-MM-DD HH:MM:SS" (opsional, untuk penanda event).
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import mikrotik_throughput_monitor as mtm  # noqa: E402

JSONL = Path(sys.argv[1])
W0 = sys.argv[2] if len(sys.argv) > 3 else ""
W1 = sys.argv[3] if len(sys.argv) > 3 else ""
OUT = Path(sys.argv[4]) if len(sys.argv) > 4 else JSONL.with_name(
    f"problem_clients_{JSONL.stem}.md")


def main() -> None:
    # ---------- 1. parse baseline ----------
    rx_login = re.compile(r"(\S+) logged in, (\S+) from ([0-9A-F:]+)")
    rx_logout = re.compile(r"(\S+) logged out, (\d+) (\d+) (\d+)")
    rx_active = re.compile(r"user (\S+) is already active")
    rx_disc = re.compile(r"<pppoe-(\S+)>: (terminating|disconnected)")

    users = defaultdict(lambda: {"login": 0, "logout": 0, "already": 0,
                                 "disc": 0, "macs": set(), "events": [],
                                 "in_win": 0})
    for line in JSONL.read_text().splitlines():
        e = json.loads(line)
        if "_snapshot" in e:
            continue
        t, msg, topics = e.get("time", ""), e.get("message", ""), e.get("topics", "")
        if "pppoe" not in topics and "ppp" not in topics:
            continue
        in_win = W0 <= t <= W1
        m = rx_login.search(msg)
        if m:
            u = users[m.group(1)]
            u["login"] += 1
            u["macs"].add(m.group(3))
            u["events"].append((t, "login"))
            u["in_win"] += in_win
            continue
        m = rx_logout.search(msg)
        if m:
            u = users[m.group(1)]
            u["logout"] += 1
            u["events"].append((t, "logout"))
            u["in_win"] += in_win
            continue
        m = rx_active.search(msg)
        if m:
            u = users[m.group(1)]
            u["already"] += 1
            u["events"].append((t, "ERR:already-active"))
            u["in_win"] += in_win
            continue
        m = rx_disc.search(msg)
        if m:
            u = users[m.group(1)]
            u["disc"] += 1
            u["events"].append((t, m.group(2)))
            u["in_win"] += in_win

    # ---------- 2. bridge host table (MAC -> port), toleran offline ----------
    mac_port, e8, act = {}, {}, []
    try:
        settings = mtm.get_settings()
        client = mtm.build_client(settings)
        try:
            base = f"{settings['scheme']}://{settings['host']}:{settings['port']}/rest"
            hosts = client.get(f"{base}/interface/bridge/host").json()
            for h in hosts:
                mac_port[h.get("mac-address", "").upper()] = h.get("on-interface", "?")
            ether = client.get(f"{base}/interface/ethernet").json()
            e8 = next((x for x in ether if x.get("name") == "ether8"), {})
            act = client.get(f"{base}/ppp/active").json()
        finally:
            client.close()
    except Exception as exc:
        print(f"WARN: router tidak terjangkau ({exc}); lanjut tanpa data live")

    # ---------- 3. susun laporan ----------
    # skor masalah: logout+disc+2*already (reconnect tak bersih berat)
    def score(u):
        return u["logout"] + u["disc"] + 2 * u["already"] + u["login"]

    ranked = sorted(users.items(), key=lambda kv: -score(kv[1]))
    uptime_map = {s.get("name"): (s.get("address", "?"), s.get("uptime", "?")) for s in act}

    L = []
    L.append("# 🔍 Penelusuran Klien Bermasalah — baseline 09:46–22:52 (fokus 19:00–21:00)")
    L.append("")
    L.append("## 1. Ranking Klien (berdasarkan frekuensi putus-nyambung)")
    L.append("")
    L.append("| User | Login | Logout | Disconnect | Err 'already active' | Event 19-21 | MAC (port fisik) | IP & uptime sesi kini |")
    L.append("|---|---|---|---|---|---|---|---|")
    for name, u in ranked:
        macs = ", ".join(f"`{m}`({mac_port.get(m, '?')})" for m in sorted(u["macs"])) or "-"
        ip, up = uptime_map.get(name, ("(offline)", "-"))
        L.append(f"| `{name}` | {u['login']} | {u['logout']} | {u['disc']} | {u['already']} | {u['in_win']} | {macs} | {ip} / {up} |")
    L.append("")
    L.append("## 2. Klien di belakang ether8 (terdampak flap 19:00–21:00)")
    L.append("")
    on_e8 = [(m, p) for m, p in mac_port.items() if p == "ether8"]
    if on_e8:
        mac_user = {}
        for name, u in users.items():
            for m in u["macs"]:
                mac_user[m] = name
        L.append("| MAC | User PPPoE |")
        L.append("|---|---|")
        for m, p in on_e8:
            L.append(f"| `{m}` | `{mac_user.get(m, '(bukan klien PPPoE / tidak terpetakan)')}` |")
    else:
        L.append("- Tidak ada MAC klien yang terdeteksi di ether8 saat ini (bridge host table).")
    L.append("")
    L.append("## 3. Detail ether8")
    L.append("")
    L.append("```json")
    L.append(json.dumps({k: v for k, v in e8.items() if k in
                         ("name", "status", "link-downs", "speed", "duplex",
                          "auto-negotiation", "rx-crc-error", "rx-fcs-error",
                          "rx-align-error", "rx-length-error", "tx-collision",
                          "tx-excessive-collision", "tx-late-collision")}, indent=2))
    L.append("```")
    L.append("")
    L.append("## 4. Kronologi event klien paling bermasalah")
    L.append("")
    for name, u in ranked[:5]:
        if score(u) == 0:
            continue
        L.append(f"### `{name}` (skor {score(u)})")
        L.append("```")
        for t, ev in u["events"]:
            mark = " <-- 19-21" if W0 <= t <= W1 else ""
            L.append(f"{t}  {ev}{mark}")
        L.append("```")
        L.append("")
    OUT.write_text("\n".join(L) + "\n")
    print(f"OK -> {OUT}")
    print(f"users={len(users)} on_ether8={len(on_e8)}")
    print("TOP5:", [(n, score(u)) for n, u in ranked[:5]])


if __name__ == "__main__":
    main()
