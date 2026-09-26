import requests
from requests.auth import HTTPBasicAuth

url = "https://idn23.tunnel.id:3227/rest/interface"
resp = requests.get(url, auth=HTTPBasicAuth('admin', 'K4lib4t4'), verify=False)
print(resp.status_code)
print(resp.json())
