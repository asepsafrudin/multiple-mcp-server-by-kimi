# TODO — Menulis Test Suite (Prioritas 1)

Tujuan: Test suite lengkap untuk semua server, hijau tanpa layanan eksternal (Ollama/Redis/network dimock).

## Langkah
- [x] Memahami kode yang akan diuji (engine, server, shared, core, bridge)
- [ ] Buat `tests/conftest.py` — setup env temp, reset settings/_db, mock embedding
- [ ] `tests/shared/` — test security (SafePath, sanitize, validate_input)
- [ ] `tests/servers/core/` — filesystem sandbox, security, shell, system, web
- [ ] `tests/servers/memory/` — store/recall/search/update/quantize/delete/expiry/stats
- [ ] `tests/servers/knowledge/` — chunking, index, search, delete, stats
- [ ] `tests/servers/skills/` — register/recall/list/load/update/delete/loader
- [ ] `tests/servers/bridge/` — gemini generate (mock httpx)
- [ ] Jalankan `make test` dan pastikan hijau
