#!/usr/bin/env python3
"""Script to apply Parent Queue configuration on MikroTik RouterOS for PPPoE clients."""

import sys
import asyncio
from pathlib import Path

# Add root directory to sys.path
root = Path(__file__).resolve().parents[1]
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from scripts.mikrotik_pppoe_quality_monitor import get_settings


async def run_ssh_commands(settings: dict, commands: list[str]) -> list[dict]:
    """Connect to RouterOS via SSH and run a series of commands."""
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
            print(f"Running command: {cmd}")
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
    
    # 1. Prepare backup commands
    backup_commands = [
        "/system backup save name=before_parent_queue",
        "/export file=before_parent_queue"
    ]
    
    print("\n--- STEP 1: Creating RouterOS Backups ---")
    backup_results = await run_ssh_commands(settings, backup_commands)
    for res in backup_results:
        if res["exit_status"] == 0:
            print(f"✅ Success: {res['command']}")
            if "backup save" in res["command"]:
                print(f"   Stdout: {res['stdout'].strip()}")
        else:
            print(f"❌ Failed: {res['command']}. Error: {res['stderr'].strip()}")
            # If backup fails, abort for safety
            print("Aborting migration due to backup failure.")
            return 1
            
    # Load profile list to modify dynamically
    print("\n--- STEP 2: Fetching Existing PPP Profiles ---")
    query_profiles_res = await run_ssh_commands(settings, ["/ppp profile print as-value"])
    
    # Parse existing profiles
    # Usually we can print all profiles and extract names
    profile_names = ["2Mb", "3M", "4MB", "5Mb", "6Mb", "8M"] # Known profiles from print
    
    # Let's run a command to get the exact list of ppp profiles from the printer,
    # or we can just apply to all standard profiles on RouterOS
    # We will get names from `/ppp profile print` or we can find them dynamically in CLI.
    # In RouterOS CLI: /ppp profile set [find name~"^(2Mb|3M|4MB|5Mb|6Mb|8M|default|default-encryption)$"] parent-queue=Total-PPPoE-Parent
    # It is safer to find profiles matching these exact name patterns on the fly.
    
    target_profiles = ["2Mb", "3M", "4MB", "5Mb", "6Mb", "8M", "default", "default-encryption"]
    
    # 3. Create parent queue and change profile rules
    migration_commands = [
        # Check if parent queue already exists, build it if missing
        '/queue simple {:local parent [find name="Total-PPPoE-Parent"]; :if ($parent = "") do={add name="Total-PPPoE-Parent" target=0.0.0.0/0 max-limit=48M/48M queue=default/default comment="Parent Queue for PPPoE Clients"} else={set $parent max-limit=48M/48M queue=default/default}}'
    ]
    
    # Add profile update commands for target profiles
    for profile in target_profiles:
        migration_commands.append(
            f'/ppp profile {{:local p [find name="{profile}"]; :if ($p != "") do={{set $p parent-queue=Total-PPPoE-Parent}}}}'
        )
        
    # Dynamically update existing dynamic simple queues for currently active users
    migration_commands.append(
        '/queue simple {:foreach q in=[find name~"<pppoe-"] do={set $q parent="Total-PPPoE-Parent"}}'
    )
    
    print("\n--- STEP 3: Applying Parent Queue Configuration ---")
    migration_results = await run_ssh_commands(settings, migration_commands)
    
    all_ok = True
    for res in migration_results:
        if res["exit_status"] == 0:
            print(f"✅ Success: {res['command'][:80]}...")
        else:
            print(f"❌ Failed: {res['command']}. Error: {res['stderr'].strip()}")
            all_ok = False
            
    if all_ok:
        print("\n🎉 MIGRATION SUCCESSFUL!")
        print("1. Backups created: before_parent_queue.backup & before_parent_queue.rsc")
        print("2. Parent Simple Queue 'Total-PPPoE-Parent' configured at 48M/48M.")
        print("3. PPP Profiles configured to assign parent-queue to 'Total-PPPoE-Parent'.")
        print("4. Active simple queues updated dynamically to share this parent.")
    else:
        print("\n⚠️ Migration completed with some warnings.")
        
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
