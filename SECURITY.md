# Security Guide

## Prinsip

1. **No hardcoded secrets** — semua credential berasal dari `.env` atau `config/credentials/`.
2. **Path sandboxing** — core filesystem tools hanya mengizinkan direktori di `ALLOWED_DIRECTORIES`.
3. **Input validation** — semua tools menggunakan Pydantic model dan security helpers.
4. **Audit logging** — setiap aksi sensitif bisa dicatat via `audit_log` tool.
5. **Least privilege** — bridge integrations gagal gracefully jika credential tidak tersedia.

## Credential Management

Salin dan isi `.env`:

```bash
cp .env.example .env
chmod 600 .env
```

Variabel yang perlu diisi (opsional kecuali digunakan):

```env
DB_URL=postgresql://user:pass@localhost:5432/mcp
REDIS_URL=redis://localhost:6379/0
OLLAMA_URL=http://localhost:11434
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
GMAIL_CREDENTIALS_PATH=/home/aseps/MCP/config/credentials/gmail_credentials.json
GMAIL_TOKEN_PATH=/home/aseps/MCP/config/credentials/gmail_token.json
GOOGLE_VISION_CREDENTIALS_PATH=/home/aseps/MCP/config/credentials/vision_sa.json
GEMINI_API_KEY=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

## Path Restrictions

Default `allowed_directories` di `shared/config.py`:

- `/home/aseps/MCP`
- `/home/aseps/Workspace`
- `/tmp`

Bisa di-override via env `ALLOWED_DIRECTORIES` (comma-separated).

## Audit Log

Gunakan tool `audit_log` dari core server:

```python
await audit_log(
    action="memory_delete",
    resource="memory:abc123",
    result="success",
    metadata={"namespace": "agent-alpha"},
)
```

## Git & Secrets

- `.env` dan `config/credentials/` sudah di-gitignore.
- Jangan pernah commit file `.env`, token, atau service-account JSON.
- Backup credential secara terpisah dari repository.

## Rekomendasi Produksi

- Gunakan PostgreSQL + pgvector dengan user yang memiliki hak terbatas.
- Aktifkan Redis hanya dengan password/authentication.
- Jalankan server sebagai user non-root.
- Gunakan AppArmor/SELinux untuk membatasi akses filesystem server.
