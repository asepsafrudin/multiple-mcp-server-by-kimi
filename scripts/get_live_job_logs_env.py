#!/usr/bin/env python3
import os

import httpx


def main():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("Error: GITHUB_TOKEN environment variable not set.")
    repo = "asepsafrudin/multiple-mcp-server-by-kimi"
    run_id = "31712429010"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    client = httpx.Client(headers=headers, follow_redirects=True)

    # 1. Get job ID
    res = client.get(f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/jobs")
    if res.status_code != 200:
        print("Error getting jobs:", res.text)
        return

    jobs = res.json().get("jobs", [])
    if not jobs:
        print("No jobs found.")
        return

    job_id = jobs[0]["id"]

    # 2. Get live logs
    local_headers = headers.copy()
    local_headers["Accept"] = "application/vnd.github.v3.raw"
    res_logs = client.get(
        f"https://api.github.com/repos/{repo}/actions/jobs/{job_id}/logs", headers=local_headers
    )
    if res_logs.status_code == 200:
        content = res_logs.text
        lines = content.splitlines()

        # Look for Verify .env Structure
        print_section = False
        target_lines = []
        for line in lines:
            if "Verify .env Structure" in line:
                print_section = True
            if "Debug Connection to MikroTik" in line:
                print_section = False
            if print_section:
                target_lines.append(line)
        print("\n=== Verify .env Structure Output ===")
        print("\n".join(target_lines))

        # Look for Record Traffic Statistics
        print_section = False
        target_lines_rec = []
        for line in lines:
            if "Record Traffic Statistics" in line:
                print_section = True
            if "Commit and Push CSV Log" in line:
                print_section = False
            if print_section:
                target_lines_rec.append(line)
        print("\n=== Record Traffic Statistics Output ===")
        print("\n".join(target_lines_rec[-40:]))
    else:
        print(f"Error fetching live logs: status={res_logs.status_code}")


if __name__ == "__main__":
    main()
