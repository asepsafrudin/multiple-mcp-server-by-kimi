# Arsitektur MCP Aseps

## Prinsip Desain

1. **Agnostik agent** — semua server mengikuti protokol MCP, bisa dipakai oleh Claude Desktop, Cline, Cursor, maupun custom agent.
2. **Local-first** — memory, knowledge, dan skill default menggunakan SQLite local. PostgreSQL/pgvector tetap didukung lewat konfigurasi.
3. **Efisiensi token** — hasil pencarian dibatasi, chunking knowledge, compact representation untuk memory.
4. **Credential terpisah** — tidak ada secret hardcoded; semua credential berasal dari `.env` atau `config/credentials/`.
5. **Modular** — setiap server bisa dijalankan/di-disable secara independen.

## Arsitektur Sistem 5-Lapis

Sistem ini berevolusi menggunakan penggabungan **Microsoft Agent Framework (MAF)**, **Oh My Pi (OMP)**, **SemIf (JEV-CPU)**, **Hindsight Memory**, dan **MCP Suite**.

```
┌────────────────────────────────────────────────────────┐
│ LAPISAN 1: ORKESTRASI (MAF Orchestrator Agent)         │
│ Mengatur graph workflow (Concurrent/Handoff)           │
└───────────────────┬────────────────────────────────────┘
                    ▼
┌───────────────────┴────────────────────────────────────┐
│ LAPISAN 2: KEPUTUSAN (SemIf / JEV-CPU)                 │
│ Routing task, triage, pre-check via Qwen3-0.6B (CPU)   │
└───────────────────┬────────────────────────────────────┘
                    ▼
┌───────────────────┴────────────────────────────────────┐
│ LAPISAN 3: RUNTIME (OMP) & LAPISAN 4: MEMORI           │
│ OMP: Coding Subagent (ACP/SDK)                         │
│ Hindsight: Memori jangka panjang (retain, reflect)     │
└───────────────────┬────────────────────────────────────┘
                    ▼
┌───────────────────┴────────────────────────────────────┐
│ LAPISAN 5: PENYEDIA TOOL (MCP Suite)                   │
│ (Core, Knowledge, Skills, Bridge MikroTik/Telegram)    │
└────────────────────────────────────────────────────────┘
```

## Shared Library

`shared/` menyediakan kemampuan yang dipakai lintas server:

- `config.py` — `pydantic-settings` untuk load `.env`.
- `embeddings.py` — async Ollama client dengan Redis cache dan L2 normalisasi.
- `models.py` — Pydantic model untuk `MemoryEntry`, `KnowledgeChunk`, `Skill`.
- `logging.py` — logging terstruktur.
- `redis_client.py` — Redis helpers, dengan graceful fallback bila Redis mati.
- `security.py` — path validation, audit log, hashing.
- `server_runner.py` — CLI runner untuk stdio/sse/ws transport.

## Transport

- **stdio** — default untuk integrasi editor lokal.
- **sse** — digunakan oleh `scripts/start-all.sh` untuk menjalankan semua server di background.
- **ws** — didukung oleh runner, belum diuji untuk production.

## Data Flow

### Memory Store → Recall

1. Agent memanggil `memory_store(namespace, content, category, ...)`.
2. `servers/memory/engine.py` menyimpan ke SQLite `memories`, `memory_fts`, dan `memory_vec`.
3. Embedding di-generate via Ollama `nomic-embed-text`, normalisasi L2.
4. `memory_recall(query)` melakukan semantic search di `memory_vec`, difilter & diperkaya dengan FTS5 fallback.

### Knowledge Harvest → Search

1. Agent memanggil `knowledge_index(project)`.
2. `servers/knowledge/harvester.py` scan workspace, filter file teks, chunk, embed.
3. Chunk disimpan di `knowledge_chunks`, `knowledge_fts`, `knowledge_vec`.
4. `knowledge_search(query)` mengembalikan chunk relevan dengan hybrid search.

### Skill Register → Recall

1. Agent memanggil `skill_register(...)` atau `skill_load_registry(...)`.
2. Skill disimpan di `skills`, `skill_fts`, `skill_vec`.
3. `skill_recall(query)` mencocokkan skill berdasarkan deskripsi, trigger, dan prompt template.

## Skalabilitas & Batasan

- SQLite cocok untuk single-node, ribuan sampai ratusan ribu entri.
- Untuk multi-node atau jutaan entri, migrasi ke PostgreSQL + pgvector direncanakan.
- Embedding via Ollama lokal membatasi throughput; Redis cache mengurangi duplikasi.
