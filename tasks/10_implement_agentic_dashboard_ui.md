# Task 10: Implement Agentic Dashboard UI & Visual HITL

## Latar Belakang
Pada Task 09, kita telah menghubungkan kapabilitas observabilitas (rekam telemetri, token, dan durasi) serta perlindungan keamanan berupa *Human-In-The-Loop* (HITL). Akan tetapi, mekanisme persetujuan saat ini berbasis perintah terminal CLI `input()`. Berdasarkan arsitektur yang berjalan di memori (*background*), implementasi `input()` berisiko menyebabkan pemblokiran sistem atau *hang*.
Oleh karena itu, antarmuka visual berupa Dashboard Agen mutlak diperlukan agar intervensi HITL dan visualisasi *Graph* proses (*Architect -> Backend -> Frontend -> QA*) dapat diawasi dan dikendalikan secara ergonomis melalui peramban web (*Web Browser*).

## Objektif
1. **Pembuatan Endpoint State Publikasi:** Mengubah state dari *Fullstack Graph* agar dapat mengabarkan *(broadcasting)* posisinya secara *real-time* (via SSE atau WebSocket/REST).
2. **Dashboard Observabilitas:** Menampilkan *Token Usage*, Cost berjalan, dan *Phase Metrics Latency* menggunakan *framework* web ringan (seperti Streamlit atau FastAPI + Jinja/Svelte).
3. **Mekanisme Visual HITL Gate:** Menggantikan terminal input `y/n` menjadi tombol interaktif (Approve / Reject / Steer) di dalam tampilan Dashboard, yang ketika ditekan, akan melanjutkan *resume* grafik.

## Rencana Implementasi Bertahap

### Phase 1: State Broadcasting & API Bridge
*(Fokus: Persiapan Data di Backend)*
*   [x] Modifikasi `FullstackAgenticWorkflow` agar menyimpan atau menyorongkan *state*-nya ke dalam SQLite/Redis temporal atau memancarkan *Server-Sent Events (SSE)*.
*   [x] Buat *endpoint* REST ringan (menggunakan FastAPI atau *built-in library*) di dalam Orchestrator untuk menerima perintah konfirmasi HITL (contoh: `POST /api/hitl/approve`).

### Phase 2: Konstruksi Antarmuka (Dashboard Base)
*(Fokus: Tampilan UI Visual)*
*   [x] Inisialisasi kerangka UI. (Direkomendasikan menggunakan perpaduan **FastAPI + HTML Statis/Vanilla JS** atau **Streamlit** agar tidak perlu installasi Node.js berlebihan di sisi *controller*).
*   [x] Buat komponen **Graph Visualizer** yang merepresentasikan *node* agen mana yang sedang menyala (Aktif: warna *hijau/blink*, Selesai: abu-abu/berkilau).
*   [x] Buat komponen **Telemetry Panel** memuat perincian total biaya (Token Calculation) & Durasi.

### Phase 3: Sinkronisasi HITL Component
*(Fokus: Interaksi User)*
*   [x] Saat sistem berada pada state `WAITING_APPROVAL`, UI akan meluncurkan notifikasi pop-up *(Modal/Alert)*.
*   [x] Tampilkan *Summary of actions* apa saja yang telah agen selesaikan.
*   [x] Tambahkan opsi interaktif penyaluran *State* menuju `DONE` atau penyisipan *Feedback Textbox* ke *Architect* jika diminta untuk direvisi.

## Metrik Keberhasilan
*   *Developer* sepenuhnya dapat mengontrol agen dan merilis *Full-Stack App* bermodal satu antarmuka peramban di `localhost:XXXX`.
*   Tidak ada lagi interupsi CLI yang berpotensi menyebabkan pembekuan terminal.
*   Dasbor berhasil merepresentasikan pergerakan agen *(real-time feedback)* yang ciamik layaknya memantau pabrik robot cerdas merakit kode aplikasi.
