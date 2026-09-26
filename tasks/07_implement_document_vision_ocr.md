# Task 07: Implementasi Document Harvester & Baidu OCR Integration

## Latar Belakang
Sistem membutuhkan kapabilitas untuk menelan (ingest), mengindeks, dan membaca dokumen PDF berskala besar (>100 halaman) tanpa mengorbankan memory context agen utama (mencegah *Softly Forget Effect*). Sesuai skema terbaru, kita akan memposisikan **Baidu Unlimited-OCR** sebagai 'alat pembaca buta/skimmer' berkecepatan tinggi dengan memori rendah (Lapisan 5), yang akan mensuplai teks transkrip mentah kepada Knowledge Server untuk di-chunk. Selain itu, agen akan dilengkapi server _Document Viewer_ lokal untuk menderender gambar/tabel beresolusi tinggi *(On-Demand Visual Rendering)* sebagai fallback dari kelemahan kompresi Baidu.

## Langkah-langkah Implementasi

1. **Pembuatan Server Dokumen & OCR Wrapper**
   - Membuat `servers/document/__init__.py` dan `servers/document/server.py`.
   - Mengintegrasikan pembungkus (*wrapper*) untuk mengeksekusi model Baidu Unlimited OCR secara lokal (atau mendirikan API mock-stubs-nya terlebih dahulu jika berat).
   - Menambahkan _tool_ `document_view_page` (berbasis `fitz` PyMuPDF) untuk melakukan _on-demand rendering_ halaman PDF ke Base64 (PNG).

2. **Pembaruan Knowledge Harvester (`servers/knowledge/harvester.py`)**
   - Menambahkan deteksi file `.pdf` ke dalam pola panen.
   - Mengalirkan file PDF yang dipanen ke server OCR sebagai pemroses linear, lalu di-_chunk_ seperti teks biasa dan disimpan ke `sqlite-vec`.

3. **Injeksi Dependensi di `pyproject.toml`**
   - Menambahkan pustaka pemroses dokumen PDF (contoh: `PyMuPDF` atau `pdfplumber`).
   - Menambahkan dependensi *vision / OCR* tambahan jika dibutuhkan untuk _local model run_.

4. **Integrasi ke MCP Orchestrator & Pencatatan**
   - Mendaftarkan port / server baru ini ke skrip eksekusi `start-all.sh`.
   - Memastikan `TASKS.md` dan `ROADMAP.md` diperbarui dengan penyelesaian modul visi dokumen.

## Status Eksekusi
- [x] Injeksi dependensi PDF parser (`PyMuPDF`) di pyproject.toml
- [x] Pembuatan `servers/document/server.py` dan alat render visual
- [x] Modifikasi `servers/knowledge/harvester.py` untuk mengarahkan dokumen PDF ke OCR
- [x] *Wiring* ke `start-all.sh` dan master checklist
