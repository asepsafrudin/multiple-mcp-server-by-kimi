# Task 04: Setup Subagent & Runtime Engine (Oh My Pi / OMP)

## Latar Belakang
Menurut wawasan Arsitektur 5-Lapis, OMP berfungsi sebagai "Runtime Coding Agent". OMP beroperasi di terminal atau editor dengan menyediakan eksekutor (bash, LSP, read/write file). Ia mewarisi kapabilitas (tools) dari MCP Suite kita. OMP terintegrasi natif dengan Hindsight memori yang kita kembangkan.

## Langkah-langkah Implementasi

1. **Konfigurasi Spesifik OMP (`.omp/mcp.json`)**
   - Buat direktori `.omp/` di *workspace* root.
   - Sambungkan konfigurasi `mcp.json` khusus agar OMP bisa mengenali backend Hindsight (`mcp-memory-server`) dan tool *core/bridge* lain yang kita operasikan.
   
2. **Setup Skrip Eksekusi (`scripts/start-omp.sh`)**
   - Siapkan skrip Bash yang menjalankan *command* terminal `omp` (mengecek dependensi Node/Bun, dan mendelegasikan OMP ke ACP/RPC session).
   - Pastikan variabel `HINDSIGHT_API_LLM_API_KEY` (atau environment Hindsight/Ollama yang dipakai lokal) disetup.

3. **Dokumentasikan Penggunaan**
   - Perbarui checklist proyek di `TASKS.md` agar integrasi OMP tercatat resmi.

## Status Eksekusi
- [x] Buat konfigurasi `.omp/mcp.json`
- [x] Tulis skrip `scripts/start-omp.sh`
- [x] Update master checklist `TASKS.md`
