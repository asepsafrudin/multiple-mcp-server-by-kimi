#!/usr/bin/env python3

import requests


def load_env():
    env = {}
    with open("/home/aseps/MCP/env/.env.remote", "r") as f:
        for line in f:
            if line.strip() and not line.startswith("#"):
                try:
                    k, v = line.strip().split("=", 1)
                    env[k] = v
                except ValueError:
                    # Skip malformed lines that do not contain '='.
                    pass
    return env


env = load_env()
account_id = env["CF_ACCOUNT_ID"]
token = env["CF_API_TOKEN"]
token_dns = env["CF_DNS_API_TOKEN"]
zone_id = env["CF_ZONE_ID_SUPD2"]

ssh_domain = dict(env).get("CF_TUNNEL_SSH_DOMAIN", "ssh.supd2.net")
ssh_target = dict(env).get("CF_TUNNEL_SSH_TARGET", "ssh://localhost:8022")
tunnel_name = "antigravity-wsl-ssh"

headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# 1. Check if tunnel exists
url_tunnels = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/cfd_tunnel"
r = requests.get(url_tunnels, headers=headers)
tunnels = r.json().get("result", [])
tunnel = next((t for t in tunnels if t["name"] == tunnel_name), None)

if not tunnel:
    print(f"Creating new tunnel '{tunnel_name}'...")
    data = {
        "name": tunnel_name,
        "tunnel_secret": "c3VwZXJzZWNyZXR0dW5uZWxzZWNyZXQxMjM0NTY3ODkw",
    }  # Dummy 32 byte secret encoded
    r_create = requests.post(url_tunnels, headers=headers, json=data)
    if r_create.status_code != 200:
        print("Failed to create tunnel:", r_create.text)
        exit(1)
    tunnel = r_create.json()["result"]

tunnel_id = tunnel["id"]
print(f"Tunnel ID: {tunnel_id}")

# Get Tunnel Token
print("Fetching Tunnel Token...")
r_token = requests.get(f"{url_tunnels}/{tunnel_id}/token", headers=headers)
if r_token.status_code == 200:
    tunnel_token = r_token.json()["result"]
else:
    print("Failed to get token:", r_token.text)
    tunnel_token = "<unknown>"

# 2. Configure Tunnel Ingress via API
print(f"Configuring ingress for {ssh_domain} -> {ssh_target}")
url_config = f"{url_tunnels}/{tunnel_id}/configurations"
config_data = {
    "config": {
        "ingress": [
            {"hostname": ssh_domain, "service": ssh_target},
            {"service": "http_status:404"},
        ],
        "warp-routing": {"enabled": False},
    }
}
r_config = requests.put(url_config, headers=headers, json=config_data)
if r_config.status_code == 200:
    print("Ingress configured successfully!")
else:
    print("Failed to configure ingress:", r_config.text)

# 3. Create DNS CNAME record
print(f"Creating DNS CNAME for {ssh_domain}...")
headers_dns = {"Authorization": f"Bearer {token_dns}", "Content-Type": "application/json"}
url_dns = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"

# Check if exists
r_dns_check = requests.get(f"{url_dns}?name={ssh_domain}", headers=headers_dns)
dns_records = r_dns_check.json().get("result", [])
if dns_records:
    dns_id = dns_records[0]["id"]
    dns_data = {
        "type": "CNAME",
        "name": ssh_domain,
        "content": f"{tunnel_id}.cfargotunnel.com",
        "proxied": True,
        "ttl": 1,
    }
    r_dns = requests.put(f"{url_dns}/{dns_id}", headers=headers_dns, json=dns_data)
    print("Updated existing DNS record.")
else:
    dns_data = {
        "type": "CNAME",
        "name": ssh_domain,
        "content": f"{tunnel_id}.cfargotunnel.com",
        "proxied": True,
        "ttl": 1,
    }
    r_dns = requests.post(url_dns, headers=headers_dns, json=dns_data)
    if r_dns.status_code == 200:
        print("Created new DNS CNAME record.")
    else:
        print("Failed to create DNS:", r_dns.text)

print("\n--- DONE ---")
print("Command to run on Remote WSL:")
print(f"cloudflared tunnel run --token {tunnel_token}")
