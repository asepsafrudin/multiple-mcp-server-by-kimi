# CLINE TASK: Bangun MCP Server — GovDoc Vision HTR

> **Instruksi untuk Cline:** Baca seluruh dokumen ini sebelum menulis satu baris kode pun.
> Ikuti urutan fase secara ketat. Jangan melompat fase.
> Setiap fase harus diverifikasi sebelum lanjut ke fase berikutnya.

---

## Konteks & Tujuan

Kamu diminta membangun sebuah **MCP (Model Context Protocol) Server** bernama `mcp-govdoc-vision` menggunakan Python.

Server ini akan dipanggil oleh Cline melalui protokol MCP standar (stdio) dan berfungsi sebagai pipeline ekstraksi teks dari dokumen pemerintah Indonesia — termasuk teks cetak, tulisan tangan, checkbox, dan tanda tangan.

**Stack yang harus digunakan:**
- Runtime: Python 3.11+
- OCR Engine: `marker-pdf` (Surya-based, sudah memiliki block type Handwriting)
- LLM Lokal: Ollama (sudah terinstall, gunakan model `llava` atau `minicpm-v`)
- MCP Framework: `mcp` (package resmi dari Anthropic, via `pip install mcp`)
- Image Processing: `Pillow`, `opencv-python`
- Cloud Fallback: `openai` SDK (GPT-4o-mini, dipanggil hanya jika confidence < threshold)

---

## Struktur Direktori yang Harus Dibuat

```
mcp-govdoc-vision/
├── server.py                  # Entry point MCP server
├── tools/
│   ├── __init__.py
│   ├── preprocessor.py        # Grayscale, contrast, deskew
│   ├── local_extractor.py     # Marker + Ollama integration
│   ├── confidence_scorer.py   # Scoring logic per blok teks
│   ├── crop_handler.py        # Smart crop dari bounding box
│   └── cloud_fallback.py      # GPT-4o-mini untuk snippet sulit
├── schema/
│   └── govdoc_output.py       # Pydantic model output JSON
├── templates/
│   └── kemendagri_layouts.py  # Template layout surat disposisi, dll
├── tests/
│   └── test_pipeline.py       # Unit test minimal
├── requirements.txt
└── README.md
```

---

## FASE 1 — Setup & Scaffolding

### Langkah 1.1: Buat struktur direktori
Buat semua folder dan file kosong sesuai struktur di atas.

### Langkah 1.2: Buat `requirements.txt`
```
mcp>=1.0.0
marker-pdf>=1.0.0
ollama>=0.3.0
openai>=1.0.0
Pillow>=10.0.0
opencv-python>=4.9.0
pydantic>=2.0.0
python-dotenv>=1.0.0
```

### Langkah 1.3: Verifikasi instalasi Ollama
Sebelum lanjut, jalankan perintah berikut dan tampilkan hasilnya:
```bash
ollama list
```
Jika model vision belum ada, jalankan:
```bash
ollama pull minicpm-v
```
**STOP jika Ollama tidak merespons. Laporkan error ke user sebelum lanjut.**

### Checkpoint Fase 1 ✓
- [ ] Semua folder dan file terbuat
- [ ] `requirements.txt` lengkap
- [ ] Ollama merespons dan ada minimal 1 model vision

---

## FASE 2 — Bangun Tools (urutan wajib)

### Tool 1: `preprocessor.py`

Fungsi yang harus ada:
```python
def preprocess_image(image_path: str) -> str:
    """
    Input  : path file gambar asli (JPG, PNG, PDF halaman)
    Output : path file gambar hasil preprocessing (simpan ke /tmp/)
    Steps  :
      1. Load dengan Pillow
      2. Convert ke Grayscale
      3. Contrast Enhancement (ImageEnhance.Contrast, factor=2.0)
      4. Deskew jika kemiringan > 1 derajat (gunakan OpenCV)
      5. Simpan sebagai PNG ke /tmp/govdoc_preprocessed_{hash}.png
      6. Return path file hasil
    """
```

**Validasi wajib:** path input harus divalidasi dengan `os.path.realpath()` dan dipastikan berada dalam direktori yang diizinkan. Tolak path yang mengandung `..` atau symlink ke luar direktori kerja.

### Tool 2: `confidence_scorer.py`

Ini adalah komponen paling kritis. Implementasikan scoring dengan aturan deterministik berikut:

```python
def score_text_block(text: str, block_type: str) -> float:
    """
    Mengembalikan confidence score 0.0 - 1.0 berdasarkan aturan:

    ATURAN 1 — Rasio karakter valid:
      Hitung rasio: (huruf + angka + spasi) / total karakter
      Jika rasio < 0.6 → score maksimal 0.4

    ATURAN 2 — Deteksi noise OCR:
      Jika ada substring yang cocok dengan pattern r'[a-z]\d[a-z]'
      (contoh: "s3gr4") → kurangi score 0.3

    ATURAN 3 — Singkatan birokrasi Indonesia (whitelist):
      Jika teks mengandung: ["u/p", "ttd", "yth", "kasubag",
      "kabid", "sekda", "kadis", "plt", "pj", "disposisi",
      "segera", "mohon", "diteruskan"]
      → Jangan kurangi score meskipun terlihat pendek/ambigu

    ATURAN 4 — Block type Handwriting dari Marker:
      Jika block_type == "Handwriting" → mulai dengan base score 0.5
      (tulisan tangan diasumsikan lebih sulit, threshold fallback lebih rendah)

    Return: float antara 0.0 dan 1.0
    """
```

**Threshold routing:**
- Score >= 0.75 → gunakan hasil lokal, tidak perlu cloud
- Score 0.5–0.74 → re-run dengan Ollama menggunakan prompt yang lebih spesifik
- Score < 0.5 → trigger `crop_handler` + `cloud_fallback`

### Tool 3: `crop_handler.py`

```python
def crop_snippet(
    image_path: str,
    polygon: list[tuple[float, float]],
    padding_px: int = 10
) -> str:
    """
    Input  : path gambar + polygon koordinat dari Marker output
             [(x1,y1), (x2,y2), (x3,y3), (x4,y4)]
    Output : path file PNG snippet yang sudah di-crop + di-preprocess ulang
    Steps  :
      1. Hitung bounding rect dari polygon
      2. Tambah padding_px di semua sisi (clamp ke batas gambar)
      3. Crop dengan Pillow
      4. Jalankan preprocess_image() pada snippet hasil crop
      5. Return path snippet
    """
```

### Tool 4: `local_extractor.py`

```python
def extract_with_marker(file_path: str) -> dict:
    """
    Jalankan Marker pada file_path.
    Return dict berisi list blok dengan format:
    {
      "blocks": [
        {
          "block_type": "Handwriting" | "Text" | "Table" | "Checkbox",
          "text": "...",
          "polygon": [(x1,y1),(x2,y2),(x3,y3),(x4,y4)],
          "confidence": float  # dari confidence_scorer
        }
      ],
      "page_count": int
    }
    """

def extract_with_ollama(image_path: str, context_hint: str = "") -> str:
    """
    Panggil Ollama dengan model vision untuk re-ekstraksi snippet.
    context_hint: keterangan konteks (misal: "ini adalah kolom disposisi")
    Gunakan prompt yang eksplisit:

    prompt = f'''Kamu adalah OCR engine untuk dokumen pemerintah Indonesia.
    Baca SEMUA teks yang terlihat pada gambar ini dengan tepat.
    Jika ada tulisan tangan, baca sesuai yang tertulis.
    Singkatan seperti u/p, ttd, Kasubag adalah singkatan resmi — pertahankan.
    {context_hint}
    Output: hanya teks saja, tanpa penjelasan tambahan.'''
    '''
    """
```

### Tool 5: `cloud_fallback.py`

```python
def send_snippet_to_cloud(
    snippet_path: str,
    context_hint: str = ""
) -> dict:
    """
    Kirim snippet ke GPT-4o-mini HANYA untuk area yang gagal lokal.
    API key diambil dari environment variable OPENAI_API_KEY.
    Jika OPENAI_API_KEY tidak ada → raise ValueError dengan pesan yang jelas.

    Return:
    {
      "text": "hasil ekstraksi",
      "tokens_used": int,
      "model": "gpt-4o-mini"
    }
    """
```

### Checkpoint Fase 2 ✓
- [ ] Semua 5 tool terbuat dan tidak ada syntax error
- [ ] `confidence_scorer.py` sudah memiliki whitelist singkatan birokrasi
- [ ] `crop_handler.py` menerima polygon (bukan hanya x,y,w,h)
- [ ] `cloud_fallback.py` gagal dengan pesan jelas jika API key tidak ada

---

## FASE 3 — Output Schema

Buat `schema/govdoc_output.py` menggunakan Pydantic:

```python
from pydantic import BaseModel
from typing import Literal, Optional
from datetime import datetime

class CheckboxItem(BaseModel):
    label: str
    status: Literal["checked", "unchecked", "unclear"]

class TextBlock(BaseModel):
    block_type: Literal["Text", "Handwriting", "Table", "Checkbox", "Signature"]
    content: str
    confidence_score: float          # 0.0 - 1.0, WAJIB ada, bukan string
    processed_by: Literal["local_marker", "local_ollama", "cloud_gpt4o"]
    polygon: Optional[list] = None

class TokenEfficiency(BaseModel):
    total_blocks: int
    local_only_blocks: int
    cloud_fallback_blocks: int
    cloud_tokens_used: int           # integer, bukan string deskriptif
    local_percentage: float          # dihitung otomatis

class GovDocOutput(BaseModel):
    # Metadata dokumen
    document_type: Literal[
        "Surat_Disposisi",
        "Nota_Dinas",
        "SK",
        "Surat_Masuk",
        "Unknown"
    ]
    source_file: str
    processed_at: datetime
    page_count: int
    schema_version: str = "1.0.0"   # versioning wajib

    # Konten
    printed_text: str
    handwritten_notes: str
    checkboxes: list[CheckboxItem]
    blocks: list[TextBlock]

    # Efisiensi
    token_efficiency: TokenEfficiency
```

---

## FASE 4 — Template Kemendagri

Buat `templates/kemendagri_layouts.py`:

```python
# Template layout untuk deteksi zona dokumen pemerintah Indonesia
# Koordinat dalam persentase dari ukuran halaman (0.0 - 1.0)
# agar tidak tergantung resolusi scan

SURAT_DISPOSISI_LAYOUT = {
    "nomor_surat": {
        "zone": (0.0, 0.0, 1.0, 0.15),   # (x1%, y1%, x2%, y2%)
        "hint": "Nomor surat ada di bagian kop, format: xxx/xxx/xxx/xxxx"
    },
    "perihal": {
        "zone": (0.0, 0.15, 1.0, 0.30),
        "hint": "Berisi ringkasan isi surat"
    },
    "kolom_disposisi": {
        "zone": (0.0, 0.30, 0.5, 0.85),
        "hint": "Kolom kiri berisi instruksi disposisi dari pimpinan, kemungkinan tulisan tangan"
    },
    "kolom_penerima": {
        "zone": (0.5, 0.30, 1.0, 0.85),
        "hint": "Kolom kanan berisi daftar penerima disposisi dengan checkbox"
    },
    "tanda_tangan": {
        "zone": (0.5, 0.85, 1.0, 1.0),
        "hint": "Area tanda tangan pejabat"
    }
}

NOTA_DINAS_LAYOUT = {
    "kepada": {"zone": (0.0, 0.0, 1.0, 0.12), "hint": "Kepada Yth."},
    "dari": {"zone": (0.0, 0.12, 1.0, 0.22), "hint": "Dari pejabat pengirim"},
    "body": {"zone": (0.0, 0.22, 1.0, 0.85), "hint": "Isi nota dinas"},
    "tanda_tangan": {"zone": (0.5, 0.85, 1.0, 1.0), "hint": "TTD"}
}

def detect_document_type(first_page_text: str) -> str:
    """
    Deteksi jenis dokumen dari teks halaman pertama.
    Return salah satu dari: Surat_Disposisi, Nota_Dinas, SK, Surat_Masuk, Unknown
    """
    text_lower = first_page_text.lower()
    if "disposisi" in text_lower:
        return "Surat_Disposisi"
    elif "nota dinas" in text_lower:
        return "Nota_Dinas"
    elif "surat keputusan" in text_lower or " sk " in text_lower:
        return "SK"
    elif "yth." in text_lower or "kepada" in text_lower:
        return "Surat_Masuk"
    return "Unknown"
```

---

## FASE 5 — MCP Server (`server.py`)

Ini adalah entry point utama. Implementasikan dengan `mcp` SDK:

```python
#!/usr/bin/env python3
"""
MCP Server: mcp-govdoc-vision
Dipanggil oleh Cline via stdio.
"""

import asyncio
import json
import os
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

# Import semua tools
from tools.preprocessor import preprocess_image
from tools.local_extractor import extract_with_marker, extract_with_ollama
from tools.confidence_scorer import score_text_block
from tools.crop_handler import crop_snippet
from tools.cloud_fallback import send_snippet_to_cloud
from templates.kemendagri_layouts import detect_document_type, SURAT_DISPOSISI_LAYOUT
from schema.govdoc_output import GovDocOutput

app = Server("mcp-govdoc-vision")

@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="process_govdoc",
            description="""
            Pipeline lengkap untuk ekstraksi teks dokumen pemerintah Indonesia.
            Mendukung: Surat Disposisi, Nota Dinas, SK, Surat Masuk.
            Mendeteksi otomatis teks cetak, tulisan tangan, checkbox, dan tanda tangan.
            Menggunakan Ollama lokal terlebih dahulu, cloud hanya untuk area sulit.
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path absolut ke file gambar atau PDF"
                    },
                    "confidence_threshold": {
                        "type": "number",
                        "description": "Threshold minimum untuk tidak trigger cloud fallback. Default: 0.75",
                        "default": 0.75
                    },
                    "force_cloud": {
                        "type": "boolean",
                        "description": "Paksa semua blok diproses cloud (untuk debugging). Default: false",
                        "default": False
                    }
                },
                "required": ["file_path"]
            }
        ),
        types.Tool(
            name="health_check",
            description="Cek status Ollama, Marker, dan koneksi cloud",
            inputSchema={"type": "object", "properties": {}}
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "health_check":
        # Implementasikan pengecekan: ollama list, import marker, cek env OPENAI_API_KEY
        pass

    if name == "process_govdoc":
        file_path = arguments["file_path"]
        threshold = arguments.get("confidence_threshold", 0.75)

        # PIPELINE UTAMA — ikuti urutan ini:
        # 1. Validasi path file
        # 2. preprocess_image()
        # 3. extract_with_marker()
        # 4. detect_document_type() dari teks awal
        # 5. Loop setiap blok:
        #    a. score_text_block()
        #    b. Jika score < threshold:
        #       - crop_snippet() menggunakan polygon dari Marker
        #       - extract_with_ollama() pada snippet
        #       - Re-score hasil Ollama
        #       - Jika masih < 0.5: send_snippet_to_cloud()
        #    c. Kumpulkan semua hasil
        # 6. Hitung token_efficiency
        # 7. Return GovDocOutput sebagai JSON

        pass

if __name__ == "__main__":
    asyncio.run(stdio_server(app))
```

**PENTING:** Isi bagian `pass` dengan implementasi nyata sesuai komentar pipeline di atas. Jangan tinggalkan `pass` di versi final.

### Checkpoint Fase 5 ✓
- [ ] `server.py` berjalan tanpa error: `python server.py`
- [ ] Tool `health_check` memberikan status semua komponen
- [ ] Tool `process_govdoc` dapat menerima path file dan mengembalikan JSON valid

---

## FASE 6 — Registrasi ke Cline

Buat instruksi registrasi di `README.md`. Cline membaca MCP server dari file konfigurasi. Tambahkan entry berikut ke file konfigurasi Cline MCP (`cline_mcp_settings.json`):

```json
{
  "mcpServers": {
    "mcp-govdoc-vision": {
      "command": "python",
      "args": ["/path/absolut/ke/mcp-govdoc-vision/server.py"],
      "env": {
        "OPENAI_API_KEY": "isi_jika_ingin_pakai_cloud_fallback"
      }
    }
  }
}
```

**Ganti `/path/absolut/ke/` dengan path aktual di mesin user.**

---

## FASE 7 — Test Minimal

Buat `tests/test_pipeline.py`:

```python
"""
Test dengan dokumen dummy. Jalankan: python -m pytest tests/
"""
import pytest
from tools.confidence_scorer import score_text_block
from tools.preprocessor import preprocess_image
from templates.kemendagri_layouts import detect_document_type

def test_confidence_noise_ocr():
    score = score_text_block("s3gr4 lanjytk4n", "Text")
    assert score < 0.5, "Teks noise OCR harus mendapat score rendah"

def test_confidence_birokrasi_whitelist():
    score = score_text_block("u/p Kasubag", "Handwriting")
    assert score >= 0.5, "Singkatan birokrasi tidak boleh dihukum"

def test_document_type_detection():
    assert detect_document_type("LEMBAR DISPOSISI No. 001/2025") == "Surat_Disposisi"
    assert detect_document_type("NOTA DINAS") == "Nota_Dinas"
    assert detect_document_type("dokumen random") == "Unknown"

def test_preprocessor_rejects_path_traversal():
    with pytest.raises(ValueError):
        preprocess_image("../../etc/passwd")
```

### Checkpoint Fase 7 ✓
- [ ] Semua test lulus: `python -m pytest tests/ -v`

---

## Aturan Global untuk Cline

1. **Jangan skip fase.** Setiap fase memiliki checkpoint. Verifikasi sebelum lanjut.
2. **Jangan install package yang tidak ada di `requirements.txt`.** Jika butuh tambahan, tanya user dulu.
3. **Semua path file harus divalidasi** sebelum diproses. Security bukan opsional.
4. **Confidence score harus berupa float**, bukan string atau deskripsi kualitatif.
5. **Cloud API hanya dipanggil jika score < threshold**, bukan untuk seluruh dokumen.
6. **Laporkan error dengan jelas** — jangan silent fail. Jika Ollama tidak merespons, hentikan pipeline dan kembalikan error message yang actionable.
7. **Setelah semua fase selesai**, jalankan seluruh test dan tampilkan hasilnya ke user.

---

*Task ini dirancang untuk environment: VS Code + Cline + Ollama (lokal) + Python 3.11+*
*Versi task: 1.0.0 | Target: mcp-govdoc-vision*
