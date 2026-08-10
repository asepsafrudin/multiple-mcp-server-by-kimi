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

async def run_ssh_commands(settings: dict, commands: dict[str, str]) -> dict[str, dict]:
    """Connect to RouterOS via SSH and run a series of commands."""
    import asyncssh
    
    results = {}
    print(f"Connecting to MikroTik at {settings['host']}:{settings.get('ssh_port', 22)}...")
    try:
        async with asyncssh.connect(
            settings["host"],
            port=settings.get("ssh_port", 22),
            username=settings["user"],
            password=settings["password"],
            known_hosts=None,
            connect_timeout=10.0,
        ) as conn:
            for key, cmd in commands.items():
                print(f"Running command for [{key}]: {cmd}")
                res = await conn.run(cmd, check=False, timeout=30.0)
                results[key] = {
                    "command": cmd,
                    "exit_status": res.returncode,
                    "stdout": res.stdout,
                    "stderr": res.stderr
                }
    except Exception as e:
        print(f"Failed to execute SSH commands: {e}")
        raise
    return results

async def main():
    settings = get_settings()
    # Add SSH port configuration
    import os
    settings["ssh_port"] = int(os.getenv("MIKROTIK_SSH_PORT", "22"))
    
    commands = {
        "system_resource": "/system resource print",
        "system_routerboard": "/system routerboard print",
        "system_identity": "/system identity print",
        "interfaces": "/interface print detail without-paging",
        "ip_addresses": "/ip address print detail without-paging",
        "ip_routes": "/ip route print detail without-paging",
        "ip_dns": "/ip dns print",
        "ip_services": "/ip service print detail without-paging",
        "ip_dhcp": "/ip dhcp-server print detail without-paging",
        "ip_dhcp_leases": "/ip dhcp-server lease print detail without-paging",
        "ppp_profiles": "/ppp profile print detail without-paging",
        "ppp_secrets": "/ppp secret print detail without-paging",
        "ppp_active": "/ppp active print detail without-paging",
        "simple_queues": "/queue simple print detail without-paging",
        "queue_tree": "/queue tree print detail without-paging",
        "firewall_rules": "/ip firewall filter print detail without-paging",
        "firewall_nat": "/ip firewall nat print detail without-paging",
        "firewall_mangle": "/ip firewall mangle print detail without-paging",
        "firewall_raw": "/ip firewall raw print detail without-paging",
        "mac_server": "/tool mac-server print",
        "bandwidth_server": "/tool bandwidth-server print",
        "neighbor_discovery": "/ip neighbor discovery-settings print",
        "export_config": "/export"
    }
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = root / "logs"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    raw_log_path = output_dir / f"mikrotik_audit_raw_{timestamp}.txt"
    print(f"Raw audit output will be saved to: {raw_log_path}")
    
    try:
        results = await run_ssh_commands(settings, commands)
    except Exception as e:
        print(f"Fatal error fetching configuration: {e}")
        return 1
        
    with open(raw_log_path, "w") as f:
        f.write(f"=== MIKROTIK AUDIT RAW DATA - {datetime.now()} ===\n")
        f.write(f"Host: {settings['host']}\n")
        f.write("=" * 60 + "\n\n")
        for key, res in results.items():
            f.write(f"[{key.upper()}] Command: {res['command']}\n")
            f.write(f"Exit Status: {res['exit_status']}\n")
            if res["stderr"]:
                f.write(f"STDERR:\n{res['stderr']}\n")
            f.write("STDOUT:\n")
            f.write(res["stdout"])
            f.write("\n" + "=" * 60 + "\n\n")
            
    print(f"Finished raw dump. Now analyzing data...")
    
    # Analyze and write audit report card
    generate_audit_report(results, timestamp, output_dir)
    return 0

def generate_audit_report(results: dict, timestamp: str, output_dir: Path):
    settings = get_settings()
    report_path = output_dir / f"mikrotik_audit_report_{timestamp}.md"
    
    # Helper to clean/strip stdout
    def get_out(key: str) -> str:
        return results.get(key, {}).get("stdout", "").strip()
        
    sys_res = get_out("system_resource")
    sys_board = get_out("system_routerboard")
    sys_id = get_out("system_identity")
    firewall_filters = get_out("firewall_rules")
    firewall_nat = get_out("firewall_nat")
    firewall_mangle = get_out("firewall_mangle")
    firewall_raw = get_out("firewall_raw")
    queues = get_out("simple_queues")
    queue_tree = get_out("queue_tree")
    dhcp = get_out("ip_dhcp")
    dhcp_leases = get_out("ip_dhcp_leases")
    dns = get_out("ip_dns")
    services = get_out("ip_services")
    ppp_profiles = get_out("ppp_profiles")
    ppp_active = get_out("ppp_active")
    ppp_secrets = get_out("ppp_secrets")
    routes = get_out("ip_routes")
    neigh_disc = get_out("neighbor_discovery")
    mac_srv = get_out("mac_server")
    bnd_srv = get_out("bandwidth_server")
    
    # Quick analysis logic
    findings = []
    recommendations = []
    
    # 1. Check services security
    active_insecure_services = []
    for line in services.splitlines():
        if "name=" in line:
            import re
            m = re.search(r'name="([^"]+)"', line)
            if m:
                s_name = m.group(1)
                if s_name in ["telnet", "ftp", "www", "api"]:
                    prefix = line.split("name=")[0]
                    if 'X' not in prefix:
                        active_insecure_services.append(s_name)
                        
    if active_insecure_services:
        findings.append(f"Insecure IP services are enabled: **{', '.join(set(active_insecure_services))}**.")
        recommendations.append("Disable insecure IP services (telnet, ftp, api, www on port 80) and use secure versions (ssh, api-ssl, www-ssl) under `/ip service`.")
        
    # 2. Check DNS recursion / DDoS risk
    is_dns_remote = False
    for line in dns.splitlines():
        if "allow-remote-requests: yes" in line:
            is_dns_remote = True
            break
    if is_dns_remote:
        # Check if port 53 UDP is blocked in firewall filters
        dns_blocked = False
        for line in firewall_filters.splitlines():
            if "dst-port=53" in line and "action=drop" in line and "chain=input" in line:
                dns_blocked = True
                break
        if not dns_blocked:
            findings.append("DNS 'allow-remote-requests' is enabled, and UDP/TCP port 53 is not explicitly drop-blocked on the WAN interface in firewall input chain.")
            recommendations.append("Secure DNS service by adding a firewall input rule to drop incoming UDP/TCP port 53 traffic from the WAN interface: `/ip firewall filter add action=drop chain=input dst-port=53 protocol=udp in-interface=ether1` (replace ether1 with actual WAN interface name).")

    # 3. Check for Fasttrack vs Simple Queues conflict
    has_fasttrack = "fasttrack-connection" in firewall_filters or "fasttrack" in firewall_filters
    has_queues = len(queues.splitlines()) > 1
    if has_fasttrack and has_queues:
        findings.append("Fasttrack connection rule is enabled in the firewall alongside simple queues. Fasttrack bypasses simple queues for established/related connections, which can break queue limits and QoS shaping.")
        recommendations.append("If bandwidth limits/QoS are critical for all clients, disable Fasttrack, or configure Fasttrack bypass mangle rules/queue packet marks so critical traffic is properly limited.")

    # 4. Check for default route failover and packet routing issues
    if "gateway=" not in routes:
        findings.append("No active gateway or routing config could import gateways properly, or default route could be single-point-of-failure.")
    else:
        # Check for multiple gateways or failover configs (distance)
        route_lines = routes.splitlines()
        has_backup_route = False
        default_routes_count = 0
        for line in route_lines:
            if "0.0.0.0/0" in line:
                default_routes_count += 1
                if "distance=" in line and int(line.split("distance=")[1].split()[0]) > 1:
                    has_backup_route = True
        
        if default_routes_count > 1 and not has_backup_route:
            findings.append("Multiple default routes (0.0.0.0/0) exist, but they have the same routing distance. This can lead to unpredictable ECMP routing issues if not explicitly configured.")
            recommendations.append("Configure distinct values for `distance` on failover default routes (e.g., Primary distance=1, Backup distance=2) or use recursive routing check-gateway functionality.")
        elif default_routes_count == 1:
            findings.append("Single default route configured. No failover ISP routing config detected.")
            recommendations.append("If secondary WAN/backup path is available, configure load balancing or failover with ping check gateway.")

    # 5. Check PPPoE profiles configuration
    # Check parent queue settings
    if "parent-queue=" not in ppp_profiles and "parent-queue=Total-PPPoE-Parent" not in ppp_profiles:
        findings.append("PPP profiles are not consistently configured with parent-queues. Total-PPPoE-Parent might not be applied to all profiles.")
        recommendations.append("Check PPP Profiles and apply the `parent-queue=Total-PPPoE-Parent` parameter to all subscription profiles under `/ppp profile`.")

    # Check TCP MSS alteration
    if "change-tcp-mss=yes" not in ppp_profiles:
        findings.append("TCP MSS clamping might not be enabled for PPP profiles. This can cause PMTUD black hole issues and page loading failures for clients.")
        recommendations.append("Ensure `change-tcp-mss` is set to `yes` or `default` inside PPP profile configurations to resolve MTU fragmentation issues.")

    # 6. Check DHCP Server ARP/Security
    if "add-arp=yes" not in dhcp:
        findings.append("DHCP servers lack MAC verification integration ('add-arp=yes'). This makes the network vulnerable to IP spoofing by manual configuration.")
        recommendations.append("Enable `add-arp=yes` in `/ip dhcp-server` configuration and set the interface's ARP mode to `reply-only` (under `/interface`) to restrict clients to DHCP-assigned leases only.")

    # 7. Check UPnP Security
    # Check if UPnP configuration is in export
    export_out = get_out("export_config")
    if "/ip upnp" in export_out and "enabled=yes" in export_out:
        findings.append("UPnP (Universal Plug and Play) is enabled. If WAN interfaces are exposed, it allows internal clients to open arbitrary inbound firewall ports automatically.")
        recommendations.append("Disable UPnP `/ip upnp set enabled=no` unless strictly required, or ensure and verify that the WAN interface is defined correctly as 'external=yes' under UPnP interfaces.")

    # 8. neighbor discovery on all interfaces
    # neighbor configuration
    for line in neigh_disc.splitlines():
        if "discover-interface-list=all" in line or "discover=yes" in line:
            findings.append("MikroTik Neighbor Discovery Protocol (MNDP) is enabled on all interfaces. This leaks system version, identity, and MAC address on public/WAN interfaces.")
            recommendations.append("Change Neighbor Discovery settings under `/ip neighbor discovery-settings` to use a discovery interface list that excludes public/WAN interfaces (e.g. set it to 'LAN' only).")

    # 9. bandwidth server enabled
    for line in bnd_srv.splitlines():
        if "enabled: yes" in line:
            # Check if authenticated or TLS is enforced
            findings.append("MikroTik Bandwidth Server is active. This can be abused for DDoS reflect attacks or unauthorized resource exhaustion if not filtered.")
            recommendations.append("Disable the bandwidth test server: `/tool bandwidth-server set enabled=no` or restrict it via `/tool bandwidth-server set authenticate=yes`.")

    # 10. MAC Server enabled on all
    for line in mac_srv.splitlines():
        if "allowed-interface-list=all" in line or "allowed=all" in line:
            findings.append("MAC WinBox/SSH server is allowed on all interfaces, including WAN networks.")
            recommendations.append("Restrict MAC-Telnet and MAC-WinBox access under `/tool mac-server` and `/tool mac-server mac-winbox` to trusted LAN interface lists only.")

    # Firewalls & IP configuration audit
    # Check for basic Input Chain firewall filter rules
    if "chain=input" not in firewall_filters:
        findings.append("No firewall filter rules configured for the input chain. The router is unprotected from direct external attacks.")
        recommendations.append("Configure a basic input firewall rule set to drop invalid connections, allow established/related, allow ICMP, allow LAN management, and drop everything else on WAN interface.")

    with open(report_path, "w") as f:
        f.write(f"# MIKROTIK ROUTERBOARD AUDIT REPORT\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n")
        f.write(f"**Target Host:** `{settings['host']}`  \n\n")
        
        f.write("## 1. System Inventory\n\n")
        f.write("### RouterOS Identity\n")
        f.write(f"```\n{sys_id}\n```\n\n")
        f.write("### System Resources\n")
        f.write(f"```\n{sys_res}\n```\n\n")
        f.write("### RouterBoard Stats\n")
        f.write(f"```\n{sys_board}\n```\n\n")
        
        f.write("## 2. Client Configurations (DHCP & PPPoE) Audit\n\n")
        f.write("### Active PPP and Profiles Info\n")
        f.write("#### Profiles:\n")
        f.write(f"```\n{ppp_profiles}\n```\n\n")
        f.write("#### Active Sessions:\n")
        f.write(f"```\n{ppp_active}\n```\n\n")
        f.write("#### Secrets:\n")
        f.write(f"```\n{ppp_secrets}\n```\n\n")
        
        f.write("### DHCP Server & Leases\n")
        f.write(f"```\n{dhcp}\n```\n")
        f.write("#### Active Leases:\n")
        f.write(f"```\n{dhcp_leases}\n```\n\n")
        
        f.write("## 3. Packet Routing & Queue Performance Audit\n\n")
        f.write("### Routing Table\n")
        f.write(f"```\n{routes}\n```\n\n")
        f.write("### Firewall Configuration status\n")
        f.write("#### Filter Rules:\n")
        f.write(f"```\n{firewall_filters}\n```\n")
        f.write("#### NAT Rules:\n")
        f.write(f"```\n{firewall_nat}\n```\n")
        f.write("#### Mangle Rules:\n")
        f.write(f"```\n{firewall_mangle}\n```\n")
        f.write("#### Raw Rules:\n")
        f.write(f"```\n{firewall_raw}\n```\n\n")
        
        f.write("### Queue Status\n")
        f.write("#### Simple Queues:\n")
        f.write(f"```\n{queues}\n```\n")
        f.write("#### Queue Tree:\n")
        f.write(f"```\n{queue_tree}\n```\n\n")
        
        f.write("## 4. Key Findings & Security Vulnerabilities\n\n")
        if findings:
            for idx, find in enumerate(findings, 1):
                f.write(f"{idx}. ⚠️ {find}\n")
        else:
            f.write("✅ No critical security or configuration vulnerabilities detected in current sweep.\n")
        f.write("\n")
        
        f.write("## 5. Actionable Recommendations for Optimizations\n\n")
        if recommendations:
            for idx, rec in enumerate(recommendations, 1):
                f.write(f"{idx}. 💡 {rec}\n")
        else:
            f.write("✅ Network is running optimized. Maintain current configuration backups.\n")
            
        f.write("\n--\n*Generated by Antigravity AI - MikroTik Configuration Audit module.*\n")
        
    print(f"Report card generated and saved to: {report_path}")

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
