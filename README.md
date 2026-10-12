# MCP Aseps — Modular Multi-Server Suite

> **STATUS: ⛔ DEPRECATED (2026-10-12)**
> Suite legacy ini digantikan oleh **[`servers/`](../../servers/README.md)** (`:8002–:8010`) dan **tidak aktif** di Cline
> (lihat [`../../.agents/AGENTS.md`](../../.agents/AGENTS.md) §6). **Jangan menambah fitur baru di sini** — pindahkan/tambahkan di `servers/`.
> Stack MCP aktif: `core/mcp-unified` (monolith, kanonik IDE) + `servers/` (modular, target migrasi).
> Rujukan status: root [`README.md`](../../README.md) → §Stack Kanonik. Pemetaan historis: [`docs/audit-cline-mcp-settings.md`](../../docs/audit-cline-mcp-settings.md).

Agnostik, modular MCP (Model Context Protocol) server suite untuk agent yang berbasis memori, pengetahuan, skill, dan integrasi eksternal. Dirancang untuk efisiensi token, local-first storage, dan mudah di-deploy di berbagai editor (Claude Desktop, Cline, Cursor, dll).

## Fitur Utama

- **servers/core** — filesystem, shell, system, web, dan security tools.
- **servers/memory** — long-term memory (LTM) dengan SQLite + sqlite-vec + FTS5 + Ollama embeddings.
- **servers/knowledge** — workspace RAG: indexing file teks, chunking, hybrid semantic + keyword search.
- **servers/skills** — procedural memory / skill registry dengan semantic recall.
- **servers/bridge** — integrasi Gmail, Telegram, Gemini, Vision OCR, Mikrotik, OpenHands (credential dari `.env`).
- **servers/bridge/github_server** — integrasi GitHub (baca+tulis: repo, issues, PR, search). Env: `GITHUB_PAT`.
- **servers/bridge/supabase_server** — integrasi Supabase (CRUD via PostgREST + DDL via Management API). Env: `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_TOKEN`.
- **shared/** — konfigurasi terpusat, embedding client, Redis cache, model, logging, security.
- **config/** — konfigurasi editor universal (`mcp_universal.json`, `claude_desktop_config.json`, `cline_mcp_settings.json`).
- **scripts/** — `start-all.sh`, `stop-all.sh`, `backup.sh`, `run_github_bridge.sh`, `run_supabase_bridge.sh`.

## Prasyarat

- Python 3.12+
- Ollama (untuk embedding) — default `http://localhost:11434`, model `nomic-embed-text`
- Redis opsional — untuk embedding cache dan working memory
- Docker + docker-compose opsional — untuk menjalankan Ollama & Redis

## Instalasi Cepat

```bash
git clone https://github.com/asepsafrudin/multiple-mcp-server-by-kimi.git /home/aseps/MCP
cd /home/aseps/MCP
cp .env.example .env
# edit .env sesuai environment Anda
make install
```

## Menjalankan Server

### Mode SSE (background, untuk testing/remote)

```bash
make start
# Akses endpoint: http://127.0.0.1:8000/sse (core), 8001 (memory), dst.
make stop
```

### Mode stdio (untuk integrasi editor)

Gunakan file konfigurasi di `config/`:
- `config/claude_desktop_config.json`
- `config/cline_mcp_settings.json`
- `config/mcp_universal.json`

Salin konfigurasi yang sesuai ke editor Anda.

## Struktur Direktori

```
.
├── config/              # konfigurasi editor & universal
├── data/                # SQLite databases (memory_v2.db, knowledge_v2.db, skills_v2.db)
├── servers/
│   ├── core/
│   ├── memory/
│   ├── knowledge/
│   ├── skills/
│   └── bridge/
├── shared/              # library bersama
├── scripts/             # start-all, stop-all, backup
├── tests/               # pytest suite
├── docker-compose.yml
├── Makefile
├── pyproject.toml
└── .env.example
```

## Perintah Makefile

```bash
make install   # buat venv & install editable + dev deps
make dev       # install editable
make test      # jalankan pytest
make lint      # ruff check
make format    # ruff format & auto-fix
make clean     # bersihkan cache
make start     # start semua server SSE
make stop      # stop semua server
make backup    # backup SQLite databases
```

## Dokumentasi Detail

- [ARCHITECTURE.md](ARCHITECTURE.md) — arsitektur & data flow
- [MEMORY.md](MEMORY.md) — konsep dan penggunaan memory
- [KNOWLEDGE.md](KNOWLEDGE.md) — workspace RAG
- [SKILLS.md](SKILLS.md) — skill registry / procedural memory
- [SECURITY.md](SECURITY.md) — keamanan & credentials
- [DEPLOYMENT.md](DEPLOYMENT.md) — deployment & editor integration
- [ROADMAP.md](ROADMAP.md) — rencana pengembangan
- [TASKS.md](TASKS.md) — daftar tugas & status

## Lisensi

MIT — lihat [LICENSE](LICENSE) jika tersedia.
