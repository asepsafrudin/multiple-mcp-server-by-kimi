# Konfigurasi MCP untuk Antigravity IDE

Panduan untuk mengintegrasikan MCP Server dengan Antigravity IDE sebagai default tools.

## 🎯 Tools yang Tersedia

MCP Server menyediakan 8 tools yang sangat berguna untuk meningkatkan produktivitas:

### 📁 File Operations
1. **`list_dir`** - List isi direktori
2. **`read_file`** - Baca isi file
3. **`write_file`** - Tulis/buat file baru

### 💾 Memory Operations (Long-term Memory)
4. **`memory_save`** - Simpan informasi ke PostgreSQL dengan vector embeddings
5. **`memory_search`** - Cari dengan hybrid search (semantic + keyword)
6. **`memory_list`** - List semua memories dengan pagination
7. **`memory_delete`** - Hapus memory berdasarkan ID atau key

### 🔧 Shell Operations
8. **`run_shell`** - Execute safe shell commands (ls, pwd, git, dll)

### 🤖 Sub-Agent Operations
9. **`execute_task`** - Eksekusi tugas tingkat tinggi secara otonom melalui dekomposisi dan eksekusi bertingkat.

## 📋 File Konfigurasi

File konfigurasi berada di: [`antigravity-mcp-config.json`](file:///home/aseps/MCP/antigravity-mcp-config.json)

```json
{
  "mcpServers": {
    "mcp-universal": {
      "command": "bash",
      "args": ["/home/aseps/MCP/mcp-memory/docker-run.sh"],
      "env": {
        "PYTHONPATH": "/home/aseps/MCP/mcp-memory"
      },
      "description": "Universal MCP Server dengan long-term memory",
      "tools": [
        "list_dir", "read_file", "file_writer",
        "memory_save", "memory_search", "memory_list", "memory_delete",
        "run_shell"
      ]
    },
    "mcp-subagent": {
      "command": "bash",
      "args": ["/home/aseps/MCP/mcp-subagent-system/mcp-run.sh"],
      "description": "MCP Sub-Agent System untuk eksekusi tugas otonom",
      "tools": ["execute_task"]
    }
  },
  "defaultServer": "mcp-subagent",
  "autoStart": true
}
```

## 🚀 Cara Menggunakan

### 1. Pastikan Prerequisites Terpenuhi

```bash
# Check PostgreSQL container
docker ps | grep mcp-pg

# Jika belum ada, jalankan:
docker run -d --name mcp-pg \
  -e POSTGRES_DB=mcp \
  -e POSTGRES_USER=aseps \
  -e POSTGRES_PASSWORD=secure123 \
  -v ~/mcp-data/pg:/var/lib/postgresql/data \
  -p 5432:5432 \
  pgvector/pgvector:pg16

# Initialize database
docker exec -i mcp-pg psql -U aseps -d mcp < /home/aseps/MCP/mcp-docker/init_db.sql
```

### 2. Test MCP Server

```bash
# Test manual
cd /home/aseps/MCP/mcp-docker
bash docker-run.sh

# Dalam terminal lain, test dengan curl:
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "id": 1
  }'
```

### 3. Konfigurasi di Antigravity IDE

Salin konfigurasi ke lokasi yang sesuai untuk Antigravity IDE (lokasi ini mungkin berbeda tergantung IDE):

```bash
# Contoh lokasi konfigurasi (sesuaikan dengan IDE Anda)
cp /home/aseps/MCP/antigravity-mcp-config.json ~/.config/antigravity/mcp-config.json
```

## 💡 Rekomendasi Tools untuk Produktivitas

Berdasarkan analisis, berikut tools yang paling berguna untuk Antigravity IDE:

### Priority 1: Essential Tools (Wajib)
- ✅ **`memory_save`** - Simpan context penting untuk session berikutnya
- ✅ **`memory_search`** - Retrieve context dari session sebelumnya
- ✅ **`read_file`** - Baca file untuk analisis
- ✅ **`write_file`** - Generate atau update file

### Priority 2: Productivity Boosters
- ✅ **`list_dir`** - Explore struktur project
- ✅ **`run_shell`** - Execute commands (git, testing, dll)

### Priority 3: Advanced Features
- ✅ **`memory_list`** - Browse semua saved memories
- ✅ **`memory_delete`** - Cleanup old/irrelevant memories

## 🎨 Use Cases

### Use Case 1: Code Analysis dengan Memory
```
1. Agent membaca file dengan read_file
2. Agent menganalisis dan menyimpan findings dengan memory_save
3. Di session berikutnya, agent bisa retrieve dengan memory_search
```

### Use Case 2: Project Documentation
```
1. Agent explore struktur dengan list_dir
2. Agent baca files penting dengan read_file
3. Agent generate dokumentasi dengan write_file
4. Agent save summary ke memory untuk reference
```

### Use Case 3: Iterative Development
```
1. Agent search memory untuk context dari session sebelumnya
2. Agent baca current code dengan read_file
3. Agent generate improvements dengan write_file
4. Agent run tests dengan run_shell
5. Agent save results ke memory
```

## 🔧 Advanced Configuration

### Custom Tool Selection

Jika Anda ingin membatasi tools yang tersedia:

```json
{
  "mcpServers": {
    "mcp-minimal": {
      "command": "bash",
      "args": ["/home/aseps/MCP/mcp-docker/docker-run.sh"],
      "tools": ["read_file", "memory_save", "memory_search"]
    },
    "mcp-full": {
      "command": "bash",
      "args": ["/home/aseps/MCP/mcp-docker/docker-run.sh"],
      "tools": ["*"]
    }
  },
  "defaultServer": "mcp-minimal"
}
```

### Environment Variables

Customize behavior dengan environment variables:

```json
{
  "env": {
    "PYTHONPATH": "/home/aseps/MCP/mcp-docker",
    "MCP_LOG_LEVEL": "INFO",
    "MCP_MEMORY_STRATEGY": "hybrid"
  }
}
```

## 📊 Memory Search Strategies

MCP Server mendukung 3 strategi pencarian:

1. **`hybrid`** (default) - Kombinasi semantic + keyword (60:40 ratio)
2. **`semantic`** - Pure vector similarity search
3. **`keyword`** - Full-text search dengan PostgreSQL

Contoh penggunaan:

```python
# Hybrid search (best for most cases)
memory_search(query="authentication implementation", strategy="hybrid")

# Semantic search (best for conceptual queries)
memory_search(query="how to handle user sessions", strategy="semantic")

# Keyword search (best for exact matches)
memory_search(query="def authenticate_user", strategy="keyword")
```

## 🛡️ Security Notes

> [!WARNING]
> **Shell Command Safety**: Tool `run_shell` hanya mengizinkan safe commands (ls, pwd, git, dll). Dangerous commands (rm -rf, dd, etc.) akan ditolak.

> [!IMPORTANT]
> **Database Access**: Memory tools memerlukan PostgreSQL running. Pastikan credentials aman dan tidak di-commit ke repository.

## 🔄 Maintenance

### Cleanup Old Memories

```bash
# List all memories
curl -X POST http://localhost:8000/ -d '{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {"name": "memory_list", "arguments": {"limit": 50}},
  "id": 1
}'

# Delete specific memory
curl -X POST http://localhost:8000/ -d '{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {"name": "memory_delete", "arguments": {"key": "old_key"}},
  "id": 1
}'
```

### Monitor Performance

```bash
# Check PostgreSQL stats
docker exec mcp-pg psql -U aseps -d mcp -c "SELECT COUNT(*) FROM memories;"

# Check memory usage
docker stats mcp-pg --no-stream
```

## 📚 References

- [MCP Server API Documentation](file:///home/aseps/MCP/mcp-docker/API_DOCUMENTATION.md)
- [Architecture Overview](file:///home/aseps/MCP/ARCHITECTURE.md)
- [Security Guidelines](file:///home/aseps/MCP/mcp-docker/SECURITY.md)

## 🎉 Next Steps

1. ✅ Konfigurasi file sudah dibuat
2. 📝 Dokumentasi lengkap tersedia
3. 🚀 Siap diintegrasikan dengan Antigravity IDE
4. 💡 Gunakan memory tools untuk persistent context across sessions!
