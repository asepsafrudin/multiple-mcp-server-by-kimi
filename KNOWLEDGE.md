# Knowledge System (Workspace RAG)

MCP Knowledge Server menyediakan **Retrieval-Augmented Generation (RAG)** untuk workspace/project lokal. File teks di-index, di-chunk, di-embed, dan bisa dicari secara semantik maupun keyword.

## Konsep

- **Project** — namespace knowledge (biasanya sama dengan nama folder workspace).
- **File** — setiap file teks yang relevan di-chunk.
- **Chunk** — bagian kecil teks dengan metadata file_path, file_hash, file_type, chunk_index.
- **Hybrid Search** — kombinasi semantic search (sqlite-vec) + FTS5 keyword fallback.

## Tools

| Tool | Fungsi |
|------|--------|
| `knowledge_index` | Index/harvest project workspace |
| `knowledge_search` | Hybrid semantic + keyword search |
| `knowledge_stats` | Statistik project |
| `knowledge_forget_project` | Hapus semua chunk project |
| `knowledge_reindex` | Rebuild index project |

## Backend

- **SQLite** local-first: `data/knowledge_v2.db`
- **sqlite-vec** untuk semantic search
- **FTS5** untuk keyword search
- **Ollama** embedding

## File yang Di-index

Text files: `.txt`, `.md`, `.py`, `.js`, `.ts`, `.json`, `.yaml`, `.sh`, `.html`, `.css`, `.sql`, `.go`, `.rs`, `.java`, dan banyak lagi.

Direktori yang di-skip: `.git`, `node_modules`, `__pycache__`, `.venv`, `dist`, `build`, `target`, dll.

File lock & credential di-skip: `package-lock.json`, `yarn.lock`, `.env`, dll.

## Chunking

- Markdown: ~400 token/chunk
- Code: ~300 token/chunk
- Default: ~500 token/chunk
- Overlap: ~10% antar chunk

## Contoh Penggunaan

```python
await knowledge_index(project="my-app")
results = await knowledge_search(
    query="FastMCP route handler",
    project="my-app",
    limit=5,
)
```

## Implementasi

Lihat `servers/knowledge/engine.py`, `servers/knowledge/harvester.py`, `servers/knowledge/chunking.py`.
