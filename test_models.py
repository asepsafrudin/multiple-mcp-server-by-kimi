import requests
import json
import os

key = os.popen('grep "^llm-vllm-key" .env | cut -d "=" -f 2-').read().strip()
url = "https://api.runpod.ai/v2/m1arai9rnwwau7/openai/v1/models"
headers = {
    "Authorization": f"Bearer {key}"
}
print("Mengecek daftar model yang tersedia...")
res = requests.get(url, headers=headers)
print("Status Code:", res.status_code)
if res.status_code == 200:
    print(json.dumps(res.json(), indent=2))
else:
    print(res.text)
