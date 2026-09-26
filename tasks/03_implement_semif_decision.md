# Task 03: Implementasi Lapisan Keputusan (SemIf / JEV-CPU)

## Latar Belakang
Berdasarkan wawasan Arsitektur 5-Lapis, Lapisan Keputusan (SemIf) bertanggung jawab sebagai *Router*, *Guardrails*, dan *Triage* menggunakan model parameter rendah (Qwen3-0.6B) yang berjalan murni di CPU (JEV-CPU) dengan kebutuhan RAM ~3 GB. Node ini terekspos di `http://127.0.0.1:8080/mcp` agar dapat dikonsumsi oleh Orchestrator MAF.

## Langkah-langkah Implementasi

1. **Buat Direktori Server `servers/decision`**
   - Buat `servers/decision/__init__.py`.
   - Buat `servers/decision/server.py` berbasis `FastMCP`.

2. **Implementasikan Logic Keputusan (Mock/Skeleton)**
   - Buat MCP Tool `decision_triage(task_description)`.
   - Siapkan *placeholder* atau mekanisme asinkron untuk inferensi lokal menggunakan HuggingFace `transformers` atau `onnxruntime`. Jika resource Qwen3-0.6B belum diunduh, server akan menggunakan kalkulasi heuristik/LLM *fallback* (misal via Ollama) sebagai jembatan sementara menuju JEV-CPU sungguhan.

3. **Integrasi Ekosistem**
   - Tambahkan `mcp-decision-server="servers.decision.server:main"` di `pyproject.toml`.
   - Modifikasi `scripts/start-all.sh` untuk menjalankan server `decision` secara paralel di port 8080.
   - Perbarui status di `TASKS.md`.

## Status Eksekusi
- [x] Buat struktur direktori `decision`
- [x] Tulis MCP server untuk SemIf/JEV-CPU (port 8080)
- [x] Update `pyproject.toml`
- [x] Update `scripts/start-all.sh` & master checklist
