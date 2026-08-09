# Deployment Guide

## Instalasi

```bash
git clone https://github.com/asepsafrudin/multiple-mcp-server-by-kimi.git /home/aseps/MCP
cd /home/aseps/MCP
cp .env.example .env
# edit .env
make install
```

## Menjalankan Dependensi (Docker)

```bash
docker-compose up -d
```

Ini akan menjalankan:
- Ollama di port 11434
- Redis di port 6379

Pull model embedding:

```bash
docker exec -it mcp-ollama ollama pull nomic-embed-text
```

## Menjalankan Server

### 1. Mode stdio untuk Editor

Salin konfigurasi editor yang sesuai:

```bash
# Claude Desktop
mkdir -p ~/.config/claude
cp config/claude_desktop_config.json ~/.config/claude/config.json

# Cline
mkdir -p ~/.config/cline
cp config/cline_mcp_settings.json ~/.config/cline/mcp_settings.json
```

Pastikan path `/home/aseps/MCP/.venv/bin/python` sesuai dengan sistem Anda.

### 2. Mode SSE untuk Remote/Testing

```bash
make start
```

Akses endpoint:
- http://127.0.0.1:8000/sse — core
- http://127.0.0.1:8001/sse — memory
- http://127.0.0.1:8002/sse — knowledge
- http://127.0.0.1:8003/sse — skills
- http://127.0.0.1:8004/sse — gmail
- http://127.0.0.1:8005/sse — telegram
- http://127.0.0.1:8006/sse — gemini
- http://127.0.0.1:8007/sse — vision

```bash
make stop
```

## Backup

```bash
make backup
```

Hasil backup disimpan di `backups/` dengan timestamp.

## Update

```bash
git pull origin main
make dev
make test
make restart
```

## Troubleshooting

| Masalah | Solusi |
|---------|--------|
| Ollama tidak terhubung | Pastikan Ollama berjalan dan model `nomic-embed-text` sudah di-pull. |
| Redis tidak terhubung | Embedding akan tetap jalan tanpa cache; periksa `REDIS_URL`. |
| Permission denied PostgreSQL | Saat ini memory/knowledge menggunakan SQLite local-first; PostgreSQL hanya disiapkan untuk masa depan. |
| Tool tidak muncul di editor | Periksa log editor dan `logs/mcp-*.log`; pastikan path Python benar. |
