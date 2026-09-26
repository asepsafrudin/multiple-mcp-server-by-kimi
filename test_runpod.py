from openai import OpenAI
import os

key = os.popen('grep "^llm-vllm-key" .env | cut -d "=" -f 2-').read().strip()
ENDPOINT_URL = "https://api.runpod.ai/v2/m1arai9rnwwau7/openai/v1"
MODEL_NAME = "huihui-ai/deepseek-r1-distill-qwen-14b-abliterated"

client = OpenAI(
    api_key=key,
    base_url=ENDPOINT_URL
)

print(f"Mengirim permintaan Chat Completion ke model: {MODEL_NAME}...\n")

try:
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "user", "content": "Sebut 3 kata random dalam bahasa indonesia."}
        ],
        temperature=0.6,
        max_tokens=300
    )
    print("Berhasil! Ini respons dari AI:")
    print("-" * 50)
    print(response.choices[0].message.content)
    print("-" * 50)
except Exception as e:
    print(f"Gagal melakukan pengetestan! Error: {e}")
