#!/usr/bin/env python3
import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add root directory to sys.path
root = Path(__file__).resolve().parents[1]
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from scripts.mikrotik_pppoe_quality_monitor import get_settings

async def run_ssh_commands(settings: dict, commands: list[str]) -> list[dict]:
    """Connect to RouterOS via SSH and run a list of commands in sequence."""
    import asyncssh
    
    results = []
    print(f"Connecting to MikroTik at {settings['host']}:{settings.get('ssh_port', 22)}...")
    async with asyncssh.connect(
        settings["host"],
        port=settings.get("ssh_port", 22),
        username=settings["user"],
        password=settings["password"],
        known_hosts=None,
        connect_timeout=10.0,
    ) as conn:
        for cmd in commands:
            print(f"Running: {cmd}")
            res = await conn.run(cmd, check=False, timeout=30.0)
            results.append({
                "command": cmd,
                "exit_status": res.returncode,
                "stdout": res.stdout,
                "stderr": res.stderr
            })
    return results

async def main():
    settings = get_settings()
    import os
    settings["ssh_port"] = int(os.getenv("MIKROTIK_SSH_PORT", "22"))
    
    # 1. Backups
    backup_commands = [
        "/system backup save name=before_mcp_optimization",
        "/export file=before_mcp_optimization"
    ]
    
    print("\n--- STEP 1: Creating Configuration Backups ---")
    try:
        backup_res = await run_ssh_commands(settings, backup_commands)
        for r in backup_res:
            if r["exit_status"] != 0:
                print(f"❌ Backup failed: {r['command']}. Error: {r['stderr'].strip()}")
                return 1
            print(f"✅ Backup success: {r['command']}")
    except Exception as e:
        print(f"Failed to complete backups: {e}")
        return 1
        
    # 2. Optimization and Securing commands
    opt_commands = [
        # --- Client QoS: Convert default & default-small Queue Types to FQ-CoDel ---
        '/queue type { set [find name=default] kind=fq-codel fq-codel-limit=1000 fq-codel-target=5ms fq-codel-interval=100ms }',
        '/queue type { set [find name=default-small] kind=fq-codel fq-codel-limit=1000 fq-codel-target=5ms fq-codel-interval=100ms }',
        
        # --- Client DHCP Server: Update to local DNS Cache and enable IP Spoofing protection ---
        '/ip dhcp-server network { set [find address="192.168.77.0/24"] dns-server=192.168.77.1 }',
        '/ip dhcp-server { set [find name=dhcp1] add-arp=yes }',
        '/interface { set [find name=ether9] arp=reply-only }',
        
        # --- PPP Profiles: Enforce TCP MSS alteration explicitly ---
        '/ppp profile { set [find name="2Mb"] change-tcp-mss=yes }',
        '/ppp profile { set [find name="3M"] change-tcp-mss=yes }',
        '/ppp profile { set [find name="4MB"] change-tcp-mss=yes }',
        '/ppp profile { set [find name="5Mb"] change-tcp-mss=yes }',
        '/ppp profile { set [find name="6Mb"] change-tcp-mss=yes }',
        '/ppp profile { set [find name="7M"] change-tcp-mss=yes }',
        '/ppp profile { set [find name="8M"] change-tcp-mss=yes }',
        '/ppp profile { set [find name="10 Mb"] change-tcp-mss=yes }',
        
        # --- Security: Secure MNDP neighbor discovery to LAN list only ---
        '/ip neighbor discovery-settings { set discover-interface-list=LAN }',
        
        # --- Security: Restrict MAC Server services to LAN list only ---
        '/tool mac-server { set allowed-interface-list=LAN }',
        '/tool mac-server mac-winbox { set allowed-interface-list=LAN }',
        
        # --- Security: Disable Bandwidth Test Server ---
        '/tool bandwidth-server { set enabled=no }',
        
        # --- Firewall Filter: Clear existing rules (except place holder) to avoid duplicates ---
        '/ip firewall filter { remove [find chain=input] }',
        '/ip firewall filter { remove [find chain=forward] }',
        
        # --- Firewall Filter: Secure Input Chain ---
        '/ip firewall filter add chain=input action=accept connection-state=established,related,untracked comment="Allow established/related/untracked"',
        '/ip firewall filter add chain=input action=drop connection-state=invalid comment="Drop invalid packets"',
        '/ip firewall filter add chain=input action=accept protocol=icmp comment="Allow ICMP ping"',
        '/ip firewall filter add chain=input action=accept in-interface=sstp-tunnel-id comment="Allow management from SSTP VPN"',
        '/ip firewall filter add chain=input action=accept in-interface=ether9 comment="Allow management from Local LAN"',
        '/ip firewall filter add chain=input action=accept in-interface=bridge1 comment="Allow management from PPPoE network"',
        '/ip firewall filter add chain=input action=drop protocol=udp dst-port=53 in-interface-list=WAN comment="Drop DNS request from WAN"',
        '/ip firewall filter add chain=input action=drop protocol=tcp dst-port=53 in-interface-list=WAN comment="Drop DNS request from WAN"',
        '/ip firewall filter add chain=input action=drop in-interface-list=WAN comment="Drop all other input from WAN"',
        
        # --- Firewall Filter: Secure Forward Chain ---
        '/ip firewall filter add chain=forward action=accept connection-state=established,related,untracked comment="Allow established/related forward"',
        '/ip firewall filter add chain=forward action=drop connection-state=invalid comment="Drop invalid forward"',
        '/ip firewall filter add chain=forward action=drop connection-state=new connection-nat-state=!dstnat in-interface-list=WAN comment="Drop dynamic WAN forwards without dst-nat"'
    ]
    
    print("\n--- STEP 2: Applying Configuration Optimizations ---")
    try:
        opt_res = await run_ssh_commands(settings, opt_commands)
        all_ok = True
        for r in opt_res:
            if r["exit_status"] != 0:
                print(f"⚠️ Warning / Command Failed: {r['command']}. Error: {r['stderr'].strip()}")
                all_ok = False
            else:
                print(f"✅ Success: {r['command']}")
                
        if all_ok:
            print("\n🎉 ALL OPTIMIZATIONS COMPLETED SUCCESSFULLY!")
        else:
            print("\n⚠️ Optimizations completed with some warnings / failures. Please check the logs.")
    except Exception as e:
        print(f"Fatal error applying configurations: {e}")
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
