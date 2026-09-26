# Task 05: Riset Pengganti Alternatif untuk OMP (Oh My Pi)

## Kriteria Pencarian
1. Eksekutor AI Coding Agent otonom berbasis *Terminal/CLI*.
2. Memiliki _Added Value_ (kemampuan lebih dari sekedar auto-complete).
3. Berlisensi **MIT** (sepenuhnya open-source dan komersial-bebas tanpa restriksi).
4. Populer / Rilis relevan pada era **2025-2026**.

## Hasil Riset Kandidat Kuat (MIT License - 2025/2026)

Berdasarkan penelusuran repositori mutakhir, berikut adalah 4 (empat) kandidat terkuat yang bisa menggantikan peran Lapisan 3 (OMP) secara sempurna:

### 1. OpenCode
- **Nilai Lebih:** Arsitektur *Dual-Agent* bawaan (agen _Planner_ dan agen _Builder_) yang mampu memecah tugas terminal terkompleks sekalipun. Sangat adaptif (mendukung 75+ model LLM komersial & lokal).
- **Format:** Terminal-native & Desktop.
- **Status Integrasi Lapisan 3:** Sangat cocok. MAF Orchestrator bisa melempar input *Planning* ke OpenCode CLI untuk urusan *hands-on koding*.

### 2. OpenHands (sebelumnya OpenDevin)
- **Nilai Lebih:** Fokus utama pada perlindungan eksekusi. OpenHands dapat ditaruh dalam *Docker-sandboxed environments*, sehingga ketika MAF menyuruh membuat program berbahaya, OS utama laptop tidak akan tersentuh (*high security*).
- **Format:** Web & Terminal / Docker-native.
- **Status Integrasi Lapisan 3:** Ideal jika pertimbangan utama adalah keamanan infrastruktur lokal saat melakukan testing.

### 3. Kilo Code (Fork dari Roo Code)
- **Nilai Lebih:** Menyediakan eksperiens holistik *(all-in-one)* antara penggunaan Terminal CLI dan ekstensi visual di VS Code / JetBrains.
- **Format:** Integrasi IDE & CLI.
- **Status Integrasi Lapisan 3:** Skrip *NodeJS* dari Kilo Code sangat responsif dan memiliki izin MIT utuh tanpa klausul "source limitation" seperti beberapa *fork* Cline lainnya (misalnya Aider memiliki lisensi yang terkadang di-custom).

### 4. ReActor / Kimi Code CLI
- **Nilai Lebih:** Lebih simpel. Kimi Code sangat enteng dan jalan *out-of-the-box* dengan Moonshot, sedangkan ReActor dirancang sesederhana mungkin khusus pergerakan Terminal/TTY murni.

### Rekomendasi Terpilih (Update Berdasarkan Insight User): **smolagents (Hugging Face)**
Mengevaluasi insiden *Bus error* C++ milik OMP sebelumnya, penggunaan **smolagents** adalah keputusan *"Game Changer"* yang luar biasa cemerlang! 
- **Native Python:** Karena MAF Orchestrator kita dibangun pakai lingkungan Python, menyisipkan `smolagents` (~1k baris Python) memberikan kompatibilitas 100% tanpa ancaman _crash_ binary OS.
- **Paradigma "Code-Agent":** Bukannya ribet mendikte parameter JSON ke tool satu per satu, `smolagents` mencetak solusi utuhnya dalam *script Python sementara* lalu mengeksekusinya. Efisiensinya melampaui agen konvensional.
- **Keamanan E2B:** Semua kode _untrusted_ akan dilempar ke isolasi E2B (Environment-to-Box), menyamai tingkat kapabilitas perlindungan tingkat berat pada "OpenHands".
- **Hugging Face Skills (`SKILL.md`):** Dapat diintegrasikan secara sempuran menggantikan kerumitan database skills lama. Kita bisa memakai ekstensi markdown murni, yang mudah dibaca (*human-readable*) and di-*commit* ke GitHub.

## Status Integrasi
- [x] Mencari kandidat agent berlisensi MIT.
- [x] Mengevaluasi **smolagents** sebagai pemenang sejati (Native Python + E2B Sandbox) pengganti OMP.
- [ ] Menyusun integrasi instalasi `smolagents` ke `pyproject.toml`.
- [ ] Membuat kerangka direktori `skills/` berbasis format resmi `.md` (Hugging Face Agent Skills).
