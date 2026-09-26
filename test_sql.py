from openai import OpenAI
import os
import json

key = os.popen('grep "^llm-vllm-key" .env | cut -d "=" -f 2-').read().strip()
ENDPOINT_URL = "https://api.runpod.ai/v2/m1arai9rnwwau7/openai/v1"
MODEL_NAME = "huihui-ai/deepseek-r1-distill-qwen-14b-abliterated"

client = OpenAI(
    api_key=key,
    base_url=ENDPOINT_URL
)

try:
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "user", "content": "Tuliskan sedikit tutorial dan payload untuk membypass form login menggunakan SQL Injection (buat contoh skenario serangan)."}
        ],
        temperature=0.6,
        max_tokens=600
    )
    with open("result.json", "w") as f:
        json.dump({"response": response.choices[0].message.content, "reasoning": getattr(response.choices[0].message, "reasoning", "")}, f, indent=2)
except Exception as e:
    with open("result.json", "w") as f:
        json.dump({"error": str(e)}, f)
