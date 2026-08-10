#!/usr/bin/env python3
import asyncio
import sys
import os
from pathlib import Path

# Add root directory to sys.path
root = Path(__file__).resolve().parents[1]
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from scripts.mikrotik_pppoe_quality_monitor import get_settings

CLIENTS = {
    "192.168.99.115": "Ery",
    "192.168.99.118": "Buguru",
    "192.168.99.117": "Putro",
    "192.168.99.114": "Purba",
    "192.168.99.103": "Boby",
    "192.168.99.108": "David",
    "192.168.99.109": "tasripin",
    "192.168.99.104": "Amir",
    "192.168.99.100": "Yudi",
    "192.168.99.102": "Hadi",
    "192.168.99.113": "AgusB8",
    "192.168.99.105": "Doblay_Ori",
    "192.168.99.107": "Surya"
}

PORTS = [80, 81, 82, 8080, 8081, 8082, 443, 22, 23, 7547, 8291]

async def check_port_through_tunnel(conn, ip: str, port: int) -> bool:
    """Try to open a TCP connection to destination via the MikroTik SSH connection."""
    try:
        reader, writer = await asyncio.wait_for(
            conn.open_connection(ip, port),
            timeout=3.0
        )
        writer.close()
        await writer.wait_closed()
        return True
    except Exception:
        return False

async def main():
    import asyncssh
    settings = get_settings()
    settings["ssh_port"] = int(os.getenv("MIKROTIK_SSH_PORT", "22"))
    
    print(f"Connecting to MikroTik at {settings['host']}:{settings['ssh_port']} to establish SSH tunnel...")
    async with asyncssh.connect(
        settings["host"],
        port=settings["ssh_port"],
        username=settings["user"],
        password=settings["password"],
        known_hosts=None,
        connect_timeout=10.0,
    ) as conn:
        print("\nScanning active PPPoE client remote management ports...")
        print("-" * 60)
        print(f"{'Client Name':<15} | {'IP Address':<15} | {'Open Ports'}")
        print("-" * 60)
        
        tasks = []
        for ip, name in CLIENTS.items():
            for port in PORTS:
                tasks.append((name, ip, port))
                
        results = await asyncio.gather(*(
            check_port_through_tunnel(conn, ip, port) for name, ip, port in tasks
        ))
        
        # Group results by client
        client_ports = {ip: [] for ip in CLIENTS}
        for (name, ip, port), open_status in zip(tasks, results):
            if open_status:
                client_ports[ip].append(port)
                
        for ip, name in CLIENTS.items():
            open_list = [str(p) for p in client_ports[ip]]
            open_str = ", ".join(open_list) if open_list else "Closed (Blocked/Disabled)"
            print(f"{name:<15} | {ip:<15} | {open_str}")
            
if __name__ == "__main__":
    asyncio.run(main())
