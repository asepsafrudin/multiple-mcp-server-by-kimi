# TASKS — Status Pekerjaan

Daftar tugas & status implementasi `MCP Aseps`. Perbarui checklist ini seiring progres.

- `[x]` selesai & terverifikasi
- `[ ]` belum / sedang dikerjakan

## Foundation & Shared

- [x] Skeleton modular multi-server
- [x] `shared/config.py` — pydantic-settings + `.env`
- [x] `shared/embeddings.py` — Ollama client + Redis cache + normalisasi L2
- [x] `shared/db.py` — koneksi SQLite (aiosqlite)
- [x] `shared/redis_client.py` — Redis helpers dengan graceful fallback
- [x] `shared/models.py` — `MemoryEntry`, `KnowledgeChunk`, `Skill`
- [x] `shared/logging.py` — logging terstruktur
- [x] `shared/security.py` — path validation, audit log, hashing
- [x] `shared/server_runner.py` — runner stdio/sse/ws

## servers/core

- [x] filesystem (sandbox ke allowed dirs)
- [x] shell (whitelist command)
- [x] system (info & env aman)
- [x] web (fetch + status check)
- [x] security (validate, sanitize, audit_log, hash)

## servers/memory

- [x] store / recall / search / update / quantize / delete / expiry / stats
- [x] semantic search (`memory_vec`) + fallback FTS5
- [x] unit test engine (`tests/servers/memory/test_engine.py`)

## servers/knowledge

- [x] harvester: scan workspace, filter file teks, chunk, embed
- [x] hybrid search (semantic + FTS5 keyword)
- [x] unit test (`tests/servers/knowledge/test_knowledge.py`)

## servers/skills

- [x] register / recall / list / load / update / delete + loader registry
- [x] unit test (`tests/servers/skills/test_skills.py`)

## servers/bridge

- [x] gmail — list / send / get message (skeleton, butuh OAuth flow)
- [x] telegram — send / get updates
- [x] gemini — generate text
- [x] vision — OCR (butuh service-account JSON)
- [x] unit test gemini (`tests/servers/bridge/test_gemini.py`, httpx mock)
- [ ] unit test gmail / telegram / vision
- [ ] verifikasi end-to-end dengan credential asli

## Infra & Kualitas

- [x] `scripts/start-all.sh`, `stop-all.sh`, `backup.sh`
- [x] `docker-compose.yml` (Ollama + Redis)
- [x] `Makefile` (install/dev/test/lint/format/clean/start/stop/backup)
- [x] config editor (`.cursor/mcp.json`, `config/*.json`)
- [x] Test suite **59 passed**, tanpa layanan eksternal (mock)
- [x] Lint & format bersih (`ruff check` / `ruff format`)
- [ ] Typecheck `mypy --strict` bersih
- [ ] CI (GitHub Actions) untuk lint + test

## Dokumentasi

- [x] `README.md`
- [x] `ARCHITECTURE.md`
- [x] `MEMORY.md`, `KNOWLEDGE.md`, `SKILLS.md`
- [x] `SECURITY.md`, `DEPLOYMENT.md`
- [x] `ROADMAP.md`, `TASKS.md`
- [ ] License file (MIT disebut di README)

## Skalabilitas (future)

- [ ] Migrasi PostgreSQL + pgvector
- [ ] Hardening transport ws
- [ ] Multi-user / multi-workspace