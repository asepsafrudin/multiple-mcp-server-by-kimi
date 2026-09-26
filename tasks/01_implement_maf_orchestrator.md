# Task 01: Implementasi MAF Orchestrator

## Latar Belakang
Mengintegrasikan Microsoft Agent Framework (MAF) sebagai *Orchestrator Agent* sentral untuk suite MCP Aseps (`multiple-mcp-server-by-kimi`). Orchestrator ini akan bertindak sebagai MCP Server untuk editor/cleint, sekaligus menjadi MCP Client untuk server-server eksisting (`memory`, `knowledge`, `skills`, `bridge`, `decision`).

## Langkah-langkah Implementasi

1. **Update Dependensi (`pyproject.toml`)**
   - Tambahkan `agent-framework`, `mcp`, dan modul pendukung untuk client LLM (seperti `openai`).

2. **Buat Struktur Direktori `servers/orchestrator`**
   - Buat `servers/orchestrator/__init__.py`.
   - Buat `servers/orchestrator/main.py`.

3. **Tulis Logika `main.py`**
   - Konfigurasi `OpenAIChatClient` (atau client relevan).
   - Definisikan `MCPStreamableHTTPTool` untuk menyambung ke server `memory`, `knowledge`, `skills`, `bridge`, dan `decision`.
   - Definisikan `Agent` MAF dengan instruksi orkestrasi (cek *confidence*, delegasi, dsb).
   - Ekspos agen ini menjadi server menggunakan `agent.as_mcp_server()`.
   - Implementasikan fungsi `run()` mengggunakan `stdio_server` (`mcp.server.stdio`).

4. **Integrasi ke `Makefile`**
   - Tambahkan command `start-orchestrator` untuk menjalankan `python -m servers.orchestrator.main`.
   - Pastikan masuk ke alur `start-all`.

5. **Konfigurasi MCP Client Editor (`mcp_orchestrator.json`)**
   - Buat file JSON konfigurasi untuk mendaftarkan orchastrator ini di editor seperti Cursor, Cline, atau Claude Desktop.

## Status Eksekusi
- [x] Update dependensi
- [x] Buat struktur & `main.py` 
- [x] Update Makefile (start-all mereferensi endpoints dengan benar, orchestrator dijalankan editor)
- [x] Buat config client (`mcp_orchestrator.json`)
