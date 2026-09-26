# Task 06: Implementasi Runtime `smolagents` & Ekosistem `SKILL.md`

## Latar Belakang
Menggantikan Oh My Pi (OMP) dengan arsitektur **smolagents** dari Hugging Face sebagai Lapisan 3 (Runtime Coding Agent) dalam sistem 5-Lapis kita. `smolagents` akan mengeksekusi instruksi koding murni via Python script, diproteksi sandbox E2B, serta didukung penuh oleh protokol keterampilan berbasis teks terbuka (Hugging Face Agent Skills / format `SKILL.md`).

## Langkah-langkah Implementasi

1. **Pemutakhiran Dependensi Repositori (`pyproject.toml`)**
   - Menambahkan library `smolagents>=1.2.0` ke konfigurasi utama.
   - Menambahkan library sandbox eksekutor opsional jika diperlukan.

2. **Inkubasi Folder _Hugging Face Skills_ (`/skills`)**
   - Menggantikan ketergantungan pada _database_ internal dengan direktori terpusat `/skills`.
   - Membuat templat resmi `SKILL.md` pertama (contoh: *Mikrotik Restarter* atau *General Python Tools*) yang mewarisi metadata spesifik agar bisa di-parsing oleh MAF Orchestrator / Cursor / Cline.

3. **Re-Wiring _Prompt_ Orchestrator (`servers/orchestrator/main.py`)**
   - Menyelaraskan teks instruktur (_instructions_) di MAF Agent.
   - Perintah sebelumnya yang merujuk delegasi eksekutor koding pada `OMP (Oh My Pi)` akan dideklerasikan ulang ke entitas `Smolagents CodeAgent`.

4. **Integrasi Checkpoints**
   - Memastikan catatan _master_ di `TASKS.md` mencerminkan pencapaian arsitektur ini.

## Status Eksekusi
- [x] Menyuntikkan `smolagents` di pyproject.toml
- [x] Membangun hirarki `/skills/` dan template `SKILL.md`
- [x] *Re-wiring* MAF Orchestrator
- [x] Membarui master checklist `TASKS.md`
