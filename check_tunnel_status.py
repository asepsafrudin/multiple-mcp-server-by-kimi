import requests, os
with open('env/.env.remote') as f: env = dict(line.strip().split('=', 1) for line in f if '=' in line and not line.startswith('#'))
r = requests.get(
    f"https://api.cloudflare.com/client/v4/accounts/{env['CF_ACCOUNT_ID']}/cfd_tunnel",
    headers={'Authorization': f"Bearer {env['CF_API_TOKEN']}"}
)
if r.status_code == 200:
    for t in r.json().get('result', []):
        if t['id'] == 'd586c541-71ab-4e93-b9df-d7e232d4cc46':
            print(f"Status: {t.get('status')}, Connections: {len(t.get('connections', []))}")
