# Task 08: Implementasi Full-Stack App Dev Agentic Workflow

## Latar Belakang
Menindaklanjuti konsep penambahan agent spesialis ke dalam ekosistem MCP, tugas ini berfokus untuk membangun dan mengintegrasikan *Full-Stack App Developer Agentic Workflow* di atas Arsitektur 5-Lapis kita. Untuk mencegah loop eksekusi dan meningkatkan stabilitas sistem, orkestrasi ini akan menggunakan pendekatan *Deterministic State Machine Graph* yang memetakan jalannya peran satu arah, serta memproteksi kompilasi kode melalui isolasi (sandbox).

## Objektif Arsitektur
1. **Deterministic Graph Routing dengan Circuit Breaker**: Desain logika pergantian kerja (handoff) statis: `Architect -> Backend -> Frontend -> QA`. Terproteksi dari *infinite return loop* maksimal 2 kali reparasi via QA. 
2. **Context Summarization Node**: Rangkuman _state_ otomatis setiap fase untuk mencegah *Context Bloat* dan _Lost in the Middle_.
3. **Strict tapi Fleksibel Tool Constraining**: Mencegah halusinasi dengan membatasi *allowed_tools* dibantu *Regex Whitelist* terhadap akses eksekusi spesifik.
4. **Persistent Sandbox Execution**: Eksekusi perintah terminal berjalan di _environment_ terisolasi e2b/Docker yang menjaga *state (volume/session)* secara terus-menerus selama satu siklus rilis.

## Langkah-langkah Implementasi

### 1. Inisialisasi Graph Workflow di Orkesrator (MAF)
- Buat file routing baru, contoh: `servers/orchestrator/workflows/fullstack_graph.py`.
- Rancang *State Machine* (LangGraph / StateMachine) untuk memfasilitasi transisi fase.
- Inject mekanisme **Context Summarizer Node** antar fase, dan **Retry Counter** khusus pengembalian QA ke BE/FE untuk mencegah loop tak terbatas (*Circuit Breaker*).

### 2. Definisi *Role* dan *System Prompt*
- Mendefinisikan 4 (empat) entitas Agen dengan pembatasan hak memanggil MCP Tool:
  - **`Architect_Agent`**: Fokus pada pencarian dokumen. Akses: `knowledge:search`, `memory:recall`.
  - **`Backend_Agent`**: Fokus membuat logika di `workspace`. Akses: `core:filesystem`, `skills:recall`.
  - **`Frontend_Agent`**: Fokus membuat komponen UI. Akses: `core:filesystem`, `document:view` (OCR).
  - **`QA_Agent`**: Eksekutor _testing_ kode dan pencatatan riwayat. Akses: `core:shell`, `memory:store`.

### 3. Pemberdayaan MCP Suite dalam Pipa Eksekusi (*Pipeline Wiring*)
- **RAG Validation Policy**: Architect Agent mengirim blueprint ke `servers/decision (SemIf)` sebagai Validation Gate agar menjauhi isu *Garbage In, Garbage Out*.
- **Hindsight Loop Policy**: QA Agent wajib mencatat *Lesson Learned* ke Hindsight (`servers/memory`) bila menemukan error (terutama ketika sirkuit breaker dihentikan).
- **Bootstrapping Skills**: Menambahkan file markdown *skill* operasional di direktori `skills/` agar direcall oleh agen.

### 4. Konfigurasi Sandbox Terminal (Persistent State)
- Implementasi eksekusi terminal (e2b/Docker) untuk `QA_Agent` dengan perantara **Persistent Volume Mount** (mengikat direktori `workspace/` lokal atau ID session panjang) agar dependensi seperti `node_modules` tidak lenyap di per-invoke alat.
- Terbitkan sistem izin berbasis *Regex Whitelist* di sisi `servers/core` agar limitasi tool tidak mengakibatkan kemandekan _deadlock_.

### 5. Pengujian Simulasi (*End-to-End*)
- Menjalankan orkestrator Graph ini melalui testing prompt sederhana, misal: *"Desain dan tulis aplikasi kalkulator sederhana dengan Vite-React (FE) dan Flask (BE)."*
- Memastikan riwayat pencatatan masuk ke *Hindsight sqlite*.

## Status Eksekusi
- [x] Menyusun _State Machine/Graph Workflow_ di layer MAF.
- [x] Melakukan injeksi Summarization & Retry Counter Node.
- [x] Menulis _System Prompt_ 4 agen spesialis (Architect, BE, FE, QA).
- [x] Menambahkan gerbang logika SemIf antar Architect & BE untuk RAG Poisoning.
- [x] Melakukan implementasi Regex Whitelist di eksekusi Terminal core:shell.
- [x] Uji coba & verifikasi Persistent Sandbox Execution.
- [x] E2E Test - *Generation pipeline*.
