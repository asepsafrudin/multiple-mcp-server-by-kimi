---
name: hello_world_system
description: Mengembalikan pesan sapaan untuk mengetes kesiapan eksekutor smolagents dan sandbox E2B.
---

# Keterampilan: Hello World & System Check

Keterampilan (Skill) ini digunakan oleh agen (seperti smolagents, Cursor, atau Claude) untuk memverifikasi bahwa lingkungan sandbox / python eksekutor sudah stabil dan mampu memproses operasi matematis dasar.

## Mekanisme
1. Eksekutor koding (misal CodeAgent di `smolagents`) diminta membaca struktur file ini.
2. Agen menulis baris kode Python yang mampu mengeksekusi sapaan dan perhitungan.

## Contoh Eksekusi Kode Python

Saat agen dipanggil, Anda dapat menggunakan potongan panduan di bawah ini untuk menghasilkan operasi:

```python
def check_environment():
    import sys
    print("Halo Dunia! Smolagents Sandbox Test.")
    print(f"Versi Python: {sys.version}")
    # Uji kalkulasi otonom
    return 19 * 21

print(f"Kalkulasi agen: {check_environment()}")
```

## Parameter Kesuksesan (Post-Condition)
- Agen berhasil mendapatkan _exit-code_ 0 dari eksekusi `python`.
- Output standar (_stdout_) mencetak teks "Halo Dunia!".
- Setelah ini tereksekusi, *workflow* dapat diteruskan kembali ke Lapisan 1 (MAF Orchestrator).
