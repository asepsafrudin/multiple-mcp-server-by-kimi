# Task 09: Implementing Enterprise Agentic Features & HITL

## Latar Belakang
Setelah berhasil mengimplementasikan *Full-Stack App Dev Agentic Workflow* (Task 08), infrastruktur MCP sudah mampu mengeksekusi multi-agen untuk pengembangan aplikasi. Namun, agar solusi ini aman digunakan di tingkat *Enterprise* dan tidak bergantung pada asumsi (*hallucination*), diperlukan penambahan beberapa fitur krusial yang dianjurkan oleh pengguna, meliputi sistem kontrol intervensi manusia (HITL), optimalisasi logika pertanyaan agen (JEV refinement), manajemen template standar proyek (*Skill Seeding*), serta lapisan visibilitas metrik operasional (*Observability*).

## Objektif
1. **Keamanan Eksekusi (HITL):** Mencegah agen mengeksekusi perintah kritis atau modifikasi sistem/produk tanpa persetujuan manual.
2. **Triase Aset (JEV Refinement):** Memastikan JEV (SemIf) menunda eksekusi dan bertanya pada *user* jika spesifikasi awal ambigu, ketimbang meneruskan asumsi ke spesialis (Architect/Backend).
3. **Standarisasi Arsitektur (Skill Seeding):** Menyediakan *boilerplate* *(FastAPI, React Vite, Docker)* dalam bentuk memori prosedural di `servers/skills/` agar basis yang digunakan selalu seragam.
4. **Pemantauan (Observability):** Mempersiapkan fondasi *tracing*, *cost-tracking* (penggunaan token), dan waktu latensi eksekusi *workflow multi-node*.

## Rencana Implementasi Bertahap (Phased Approach)

### Phase 1: JEV Prompt Refinement & HITL Approval
*(Fokus: Keselamatan & Kendali)*
*   [x] **Modifikasi JEV/SemIf Prompt:** Perbarui instruksi dan *system prompt* JEV di `servers/decision/server.py` atau bagian relevan agar memprioritaskan "Bertanya kepada manusia bila requirement tidak mencapai skor konfidensi tertentu (misal < 80%)".
*   [x] **Injeksi Breakpoint pada LangGraph:** Menambahkan konfigurasi `interrupt_before=["Execute_QA_Feedback", "Final_Commit"]` pada modul `servers/orchestrator/workflows/fullstack_graph.py`.
*   [x] **Pembuatan Fitur Konfirmasi CLI/UI:** Membuat mekanisme tunggu di sisi *Orchestrator* bagi manusia untuk menyetujui *(approve)*, menolak *(reject)*, atau memodifikasi instruksi *(steer)* dari interupsi *Graph*.

### Phase 2: Advanced Skill Seeding (Enterprise Templates)
*(Fokus: Konsistensi Proyek & Efisiensi Token)*
*   [x] Buat file `servers/skills/fastapi_secure_boilerplate.md` dengan instruksi struktur Pydantic, Router, konfigurasi CORS, JWT middleware.
*   [x] Buat file `servers/skills/react_vite_tailwind_setup.md` dengan instruksi *routing*, penanganan *error boundary*, dan struktur folder standar.
*   [x] Buat file `servers/skills/docker_compose_prod.md` dengan arsitektur standar jaring isolasi *volume* dan perbaikan *network bridge*.
*   [x] *(Opsional)* Tulis *unit-test* memanggil *skill set* ini melalui memori *search/list skill*.

### Phase 3: Observability & Telemetry Framework
*(Fokus: Skalabilitas, Monitoring, & Cost Control)*
*   [x] Integrasikan *logging framework* berstruktur yang menyimpan durasi transisi *node* pada _state machine_ JEV & Graph di Orchestrator.
*   [x] Tambahkan pencatatan *Token Usage* (Prompt Tokens, Completion Tokens, Total Tokens) untuk estimasi *Cost*.
*   [x] Kaji penggunaan ekspor metrik ke standar *OpenTelemetry* (OTLP) atau integrasikan LangSmith *webhook*/.env setup untuk rekam jejak (*tracing*).

## Metrik Keberhasilan
*   *Workflow* akan berhenti berstatus *paused* apabila akan mengeksekusi bash command di luar *whitelist* atau melakukan operasi *commit/push*.
*   Instruksi awal yang sekadar menyebutkan "buat aplikasi X" langsung di-interupsi oleh JEV yang menanyakan preferensi basis data, UI *framework*, dll.
*   Pemanggilan *tool* `get_skill` untuk "FastAPI" sukses memunculkan standardisasi struktur yang langsung bisa dipakai *Architect Agent*.

## Referensi & Konteks Diskusi
*   **Diskusi Terdahulu:** Pemahaman JEV sebagai Penjaga Triage (*triage gating*) dan Opsi *Enterprise Readiness* (HITL, Skill Seeding, Observability).
