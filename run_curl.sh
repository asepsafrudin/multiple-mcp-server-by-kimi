KEY=$(grep "^llm-vllm-key" .env | cut -d "=" -f 2-)
curl -s -X POST https://api.runpod.ai/v2/m1arai9rnwwau7/openai/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $KEY" \
  -d '{
    "model": "huihui-ai/deepseek-r1-distill-qwen-14b-abliterated",
    "messages": [
      {"role": "user", "content": "Sebut 3 kata random dalam bahasa indonesia."}
    ],
    "temperature": 0.6,
    "max_tokens": 100
  }'
