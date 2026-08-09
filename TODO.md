# TODO — Menulis Test Suite (Prioritas 1) — ✅ SELESAI

Tujuan: Test suite lengkap untuk semua server, hijau tanpa layanan eksternal (Ollama/Redis/network dimock).

> Status: Semua item selesai dan terverifikasi — test suite **59 passed** tanpa layanan eksternal (mock). File ini sekarang sebagai arsip; gunakan `TASKS.md` sebagai dokumen status aktif.

## Langkah
- [x] Memahami kode yang akan diuji (engine, server, shared, core, bridge)
- [x] Buat `tests/conftest.py` — setup env temp, reset settings/_db, mock embedding
- [x] `tests/shared/` — test security (SafePath, sanitize, validate_input)
- [x] `tests/servers/core/` — filesystem sandbox, security, shell, system, web
- [x] `tests/servers/memory/` — store/recall/search/update/quantize/delete/expiry/stats
- [x] `tests/servers/knowledge/` — chunking, index, search, delete, stats
- [x] `tests/servers/skills/` — register/recall/list/load/update/delete/loader
- [x] `tests/servers/bridge/` — gemini generate (mock httpx)

Tambahan (tidak tercatat di TODO asli tapi sudah ada di repo):
- [x] `tests/servers/bridge/test_gemini.py` — gemini generate (mock httpx)
- [x] Jalankan `make test` dan pastikan hijau
