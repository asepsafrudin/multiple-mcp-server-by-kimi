# System Workflow (Senior Architect Edition)

Dokumen ini menjelaskan alur kerja operasional dalam ekosistem MCP yang telah terpadu.

## 1. Alur Interaksi Global

Sistem beroperasi sebagai satu kesatuan di bawah `mcp_unified`, bertindak sebagai jembatan antara User/IDE dan kapabilitas otonom.

```mermaid
sequenceDiagram
    participant User
    participant IDE as Agent/IDE (Antigravity)
    participant Core as MCP Unified (Server)
    participant Intelligence as Cognitive Layer (Indexer/Healer)
    participant Memory as Vector Vault (Postgres)

    User->>IDE: Memberikan Perintah (e.g. "Audit Project")
    IDE->>Core: Request Eksekusi Tools
    
    rect rgb(240, 240, 240)
        Note right of Core: Phase 1: Contextual Awareness
        Core->>Memory: Hybrid Search (RAG)
        Memory-->>Core: Relevan Snippets (Code/Docs)
    end

    rect rgb(220, 240, 220)
        Note right of Core: Phase 2: Autonomous Action
        Core->>Intelligence: Self-Healing Check
        Core->>Core: Execute Action (Vision/Shell/File)
    end

    alt Error Terdeteksi
        Core->>Intelligence: Trigger Healer
        Intelligence->>Intelligence: Apply Fix based on SOP
        Intelligence->>Core: Retry Action
    end

    Core-->>IDE: Response Akhir & Insights
    IDE-->>User: Tampilkan Hasil
```

## 2. Alur Kerja Intelligence (Senior Architect Operations)

### A. Knowledge Synchronization (Indexer Loop)
Terjadi secara berkala via Janitor atau saat ada request indexing manual.
1.  **File Scan**: Indexer menelusuri `mcp_unified/`, `docs/`, dan `scripts/`.
2.  **Semantic Chunking**: 
    -   Markdown dipotong per-header.
    -   Python dipotong per-class/function.
3.  **Context Mapping**: Setiap chunk diberikan metadata `source`, `hash`, dan `part_index`.
4.  **Vector Store**: Disimpan ke PostgreSQL (`pgvector`) untuk pencarian masa depan.

### B. Self-Healing & Learning Loop
Mekanisme pertahanan diri agent.
1.  **Failure Detection**: Menangkap error seperti `ModuleNotFoundError` atau `ConnectionError`.
2.  **Autonomous Fix**: 
    -   Instalasi library via pip otomatis.
    -   Penanganan path yang salah.
3.  **Insight Recording**: Jika perbaikan berhasil, detailnya dicatat secara permanen ke `.agent_identity`.
4.  **Policy Update**: Agent memperbarui cara kerjanya sendiri (SOP) berdasarkan pengalaman tersebut.

## 3. Alur Kerja Keamanan (Security Sandbox)

1.  **Isolation**: Kredensial dipisahkan ke `config/credentials/`.
2.  **Permission Guard**: Sistem melakukan audit otomatis pada izin file (CHMOD) saat inisialisasi.
3.  **Env Mapping**: Seluruh akses kunci API melalui layer `.env` untuk mencegah kebocoran pada log atau audit trail.

---
*Status: Operasional & Otonom | Pembaruan Terakhir: 2026-02-22*