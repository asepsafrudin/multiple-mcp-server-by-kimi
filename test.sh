KEY=$(grep "^llm-vllm-key" .env | cut -d "=" -f 2-)
DATA='{"model": "huihui-ai/deepseek-r1-distill-qwen-14b-abliterated", "messages": [{"role": "user", "content": "Berikan penjelasan dan payload SQL injection untuk login bypass singkat."}], "temperature": 0.5, "max_tokens": 1000}'
curl -s -X POST https://api.runpod.ai/v2/m1arai9rnwwau7/openai/v1/chat/completions -H "Content-Type: application/json" -H "Authorization: Bearer $KEY" -d "$DATA" > out.txt
echo "Finished"
