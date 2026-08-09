# Roadmap — MCP Aseps

Rencana pengembangan modular multi-server ini, dipetakan dari `ARCHITECTURE.md` dan progres yang sudah dikerjakan.

## Phase 1 — Fondasi ✅ Selesai

- [x] Skeleton modular multi-server (`04e1299`)
- [x] `shared/` — config, db, redis, embeddings, security, models, logging (`f25d555`)
- [x] `servers/core` — filesystem, shell, system, web, security tools (`6c33216`)

## Phase 2 — Memori, Pengetahuan, Skill ✅ Selesai

- [x] `servers/memory` — LTM engine (SQLite + sqlite-vec + FTS5 + Ollama) (`62fc423`)
- [x] `servers/knowledge` — workspace RAG harvester + hybrid search (`9709cf5`)
- [x] `servers/skills` — skill registry + semantic recall (`06c6afe`)

## Phase 3 — Integrasi & Infra 🟡 Sedang berjalan

- [x] `servers/bridge` — integrasi Gmail, Telegram, Gemini, Vision (skeleton) (`7446ee6`)
- [x] Infra & config editor: `start-all.sh`, `stop-all.sh`, `backup.sh`, docker-compose, Makefile, config stdio/sse (`e0e8c0f`)
- [x] Test suite server inti + memori + pengetahuan + skill (**59 passed**, lint bersih)
- [ ] Test end-to-end untuk Gmail, Telegram, Vision (saat ini hanya Gemini yang ter-cover)
- [ ] Pemantauan & metrik server (health check, log rotation)
- [ ] Backup DB terjadwal penuh (saat ini `backup.sh` manual)

## Phase 4 — Skalabilitas & Production ⏳ Direncanakan

- [ ] Migrasi storage ke PostgreSQL + pgvector untuk multi-node / jutaan entri
- [ ] Hardening transport `ws` (saat ini didukung, belum diuji produksi)
- [ ] Rate limiting & auth untuk mode remote (SSE)
- [ ] Multi-tenant / multi-workspace per-user
- [ ] CI pipeline (lint, format, typecheck `mypy --strict`, test) di setiap push

## Catatan

- Prinsip: agnostik agent, local-first, token-efficient, credential terpisah, modular.
- Detail teknis & data flow ada di [ARCHITECTURE.md](ARCHITECTURE.md).
- Status tugas terkini ada di [TASKS.md](TASKS.md) dan [TODO.md](TODO.md).