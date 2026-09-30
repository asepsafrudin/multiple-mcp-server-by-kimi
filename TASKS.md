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
- [x] hindsight agent memory (`hindsight_engine.py` & tools)

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
- [x] mikrotik — RouterOS management via REST API + SSH (`servers/bridge/mikrotik_server.py`)
- [x] unit test gemini (`tests/servers/bridge/test_gemini.py`, httpx mock)
- [x] unit test mikrotik (`tests/servers/bridge/test_mikrotik.py`, httpx + asyncssh mock)
- [x] unit test gmail / telegram / vision
- [ ] verifikasi end-to-end dengan credential asli

## Infra & Kualitas

- [x] `scripts/start-all.sh`, `stop-all.sh`, `backup.sh`
- [x] `docker-compose.yml` (Ollama + Redis)
- [x] `Makefile` (install/dev/test/lint/format/clean/start/stop/backup)
- [x] config editor (`.cursor/mcp.json`, `config/*.json`)
- [x] Test suite **59 passed**, tanpa layanan eksternal (mock)
- [x] Lint & format bersih (`ruff check` / `ruff format`)
- [ ] Typecheck `mypy --strict` bersih
- [x] CI (GitHub Actions) untuk lint + test

## Dokumentasi

- [x] `README.md`
- [x] `ARCHITECTURE.md`
- [x] `MEMORY.md`, `KNOWLEDGE.md`, `SKILLS.md`
- [x] `SECURITY.md`, `DEPLOYMENT.md`
- [x] `ROADMAP.md`, `TASKS.md`
- [x] `TODO.md` (arsip test suite — selesai, 59 passed)
- [ ] License file (MIT disebut di README)

## Skalabilitas (future)

- [ ] Migrasi PostgreSQL + pgvector
- [ ] Hardening transport ws
- [ ] Multi-user / multi-workspace
## servers/orchestrator (MAF)

- [x] Setup module & dependencies (`agent-framework`, `mcp`)
- [x] Implementasi Orchestrator Agent dual mode (stdio server + SSE client)
- [x] Config client editor (`config/mcp_orchestrator.json`)

## servers/decision (SemIf / JEV-CPU)
- [x] Node MCP Server `servers/decision/server.py`
- [x] Routing & Triaging Logic Placeholder
- [x] Eksposur di port 8080 (Integrasi MAF Orchestrator)

## OMP Integration (Lapisan Runtime)
- [x] Setup OMP config mapping ke backend MCP (`.omp/mcp.json`)
- [x] Eksekutor skrip Terminal OMP (`scripts/start-omp.sh`)

## Alternatif OMP / Pengganti Lapisan Eksekusi
- [x] Riset kandidat pengganti berlisensi MIT 2025/2026 (OpenCode, OpenHands, dll).
- [x] Transisi ke Hugging Face smolagents dan e2b sandbox (Task 06)

## servers/document (Vision & OCR)
- [x] Inisialisasi modul & dependencies (PyMuPDF / pdfplumber)
- [x] Implementasi `document_server.py` dan alat render visual (`document_view_page`)
- [x] Modifikasi `harvester.py` agar mengalokasi parsing PDF ke Baidu OCR / Vision server
- [x] Eksekutor server OCR & visual viewer terdaftar di `start-all.sh`

## Task 08 (Full-Stack App Dev Agentic Workflow)
- [x] Menyusun Graph Workflow MAF State Machine (routing Architect -> Backend -> Frontend -> QA)
- [x] Melakukan injeksi Summarization & Retry Counter Node.
- [x] Menulis _System Prompt_ 4 agen spesialis (Architect, BE, FE, QA).
- [x] Menambahkan gerbang logika SemIf antar Architect & BE untuk RAG Poisoning.
- [x] Melakukan implementasi Regex Whitelist di eksekusi Terminal core:shell.
- [x] Konfigurasi e2b sandbox / docker untuk eksekusi terminal yang persisten & aman
- [ ] Uji coba End-to-End untuk generasi *Full-Stack App* (misal: SvelteKit + FastAPI)

## Task 09 (Enterprise Agentic Features & HITL)
- [x] Implementasi Human-in-the-Loop (HITL) Approval Gate di Graph Workflow
- [x] Refinement JEV (SemIf) System Prompt untuk pencegahan asumsi (Ask Before Act)
- [x] Penambahan Skill Seeding Boilerplates (FastAPI, React Vite, Docker, dll)
- [x] Setup dan dokumentasi kerangka kerja Observability (Logging & Cost Tracking)

## Task 10 (Agentic Dashboard UI & Visual HITL)
- [x] Modifikasi Workflow State untuk *Broadcasting* (SSE / Redis / REST).
- [x] Konstruksi Antarmuka Dasbor Web Ringan (Status Agen, Telemetri, Token).
- [x] Integrasi Komponen Tombol Visual Persetujuan (HITL Web UI).
