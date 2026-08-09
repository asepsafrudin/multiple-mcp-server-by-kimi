# Memory System

MCP Memory Server menyediakan **long-term memory (LTM)** untuk agent: menyimpan fakta, keputusan, kesalahan, konteks, dan pola.

## Konsep

- **Namespace** — isolasi memori per agent / user / project.
- **Category** — `general`, `decision`, `learning`, `context`, `error`, `pattern`.
- **Importance** — skala 1–10; memori penting lebih mudah di-retrieve.
- **Validation status** — `pending`, `verified`, `rejected`.
- **Quantization** — memori bisa dikompres ke level `summary` atau `compressed` untuk efisiensi token.
- **Expiry** — TTL opsional; memori kadaluarsa otomatis dihapus.

## Tools

| Tool | Fungsi |
|------|--------|
| `memory_store` | Simpan memori |
| `memory_recall` | Semantic + keyword recall |
| `memory_search` | Filter berdasarkan tags, category, project, recency |
| `memory_forget` | Hapus memori by ID |
| `memory_update` | Update field tertentu |
| `memory_quantize` | Kompres memori |
| `memory_evaluate` | Ubah validation status |
| `memory_stats` | Statistik + cleanup expired |

## Backend

- **SQLite** local-first: `data/memory_v2.db`
- **sqlite-vec** untuk semantic search (L2 distance, embedding normalisasi L2)
- **FTS5** untuk keyword fallback
- **Ollama** `nomic-embed-text` untuk embedding 768-dimensi
- **Redis** cache embedding opsional

## Contoh Penggunaan

```python
# Store
await memory_store(
    namespace="agent-alpha",
    content="User prefers response in Indonesian.",
    category="learning",
    tags=["language", "preference"],
    importance=9,
)

# Recall
await memory_recall(
    namespace="agent-alpha",
    query="preferred language",
    limit=5,
)
```

## Implementasi

Lihat `servers/memory/engine.py` dan `servers/memory/server.py`.
