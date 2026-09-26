#!/usr/bin/env python3
import sys
import json
from pathlib import Path

ROOT = Path("/home/aseps/MCP")
sys.path.insert(0, str(ROOT))

import scripts.mikrotik_throughput_monitor as mtm

def main():
    settings = mtm.get_settings()
    client = mtm.build_client(settings)
    
    url = f"{settings['scheme']}://{settings['host']}:{settings['port']}/rest/log"
    print(f"Connecting to REST API: {settings['scheme']}://{settings['host']}:{settings['port']}/rest/log")
    
    try:
        response = client.get(url)
        response.raise_for_status()
        logs = response.json()
        print(f"Fetched {len(logs)} log entries.")
        
        if not logs:
            print("No log entries returned.")
            return
            
        print("First entry sample:")
        print(json.dumps(logs[0], indent=2))
        print("Last entry sample:")
        print(json.dumps(logs[-1], indent=2))
        
        # Save to logs directory
        out_path = ROOT / "logs" / "mikrotik_clientlog_raw_20260813.jsonl"
        with open(out_path, "w") as f:
            for log in logs:
                f.write(json.dumps(log) + "\n")
        print(f"Saved raw logs to: {out_path}")
        
    except Exception as e:
        print(f"Error fetching logs: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
