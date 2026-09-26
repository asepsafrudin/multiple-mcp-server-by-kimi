# Task 02: Implementasi Hindsight Agent Memory

## Konsep
Mengadopsi konsep *Hindsight* (agent memory that learns) di mana agen menyimpan pengalaman (Experience) dari tugas sebelumnya (berhasil/gagal), melakukan refleksi (Reflection) untuk mendapatkan pelajaran (Learnings), dan menggunakannya kembali sebagai saran (Advice) di masa mendatang ketika menjumpai tugas serupa.

## Langkah-langkah Implementasi

1. **Update Schema & Models (`shared/models.py`)**
   - Tambahkan model `HindsightExperience` (menyimpan task, action, outcome, success, dsb)
   - Tambahkan model `HindsightLearning` (menyimpan lesson/advice, embedding, dsb)

2. **Buat Engine Hindsight (`servers/memory/hindsight.py`)**
   - **`store_experience`**: Menyimpan log eksekusi/tugas agen.
   - **`reflect_on_experience`**: Fungsi (biasanya menggunakan prompt LLM / delegasi via alat yg ada) untuk menghasilkan `HindsightLearning` dari obyek `HindsightExperience` yang sukses maupun gagal.
   - **`get_advice`**: Fungsi *semantic search* yang mencari *learnings* relevan berdasarkan deskripsi *task* yang akan dieksekusi sekarang.

3. **Expose MCP Tools di (`servers/memory/server.py`)**
   - `hindsight_store_experience`
   - `hindsight_generate_reflection`
   - `hindsight_get_advice`

4. **Persiapkan integrasi database db/SQL (`shared/db.py` atau spesifik di hindsight)**
   - Buat tabel `hindsight_experiences` dan `hindsight_learnings` jika diperlukan di SQLite.

## Status Eksekusi
- [x] Update models 
- [x] Buat Engine Hindsight (plus storage SQL)
- [x] Register tools di memory server
- [x] Testing & Verifikasi
