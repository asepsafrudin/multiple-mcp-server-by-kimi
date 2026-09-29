from textwrap import dedent

from smolagents import CodeAgent, HfApiModel, ToolCallingAgent

# We simulate the MCP suite tool bindings by string arrays for now
# which mapping will be mapped to actual smolagents.Tool instances in the runner.
# E.g. mcp_shell_tool, mcp_fs_tool, etc.

# BaseModel for consistent routing
model = HfApiModel("Qwen/Qwen2.5-Coder-32B-Instruct")


def create_architect_agent() -> ToolCallingAgent:
    prompt = dedent("""
        Anda adalah Principal Architect (Agent 1) dalam sistem Full-Stack App Dev.
        Tugas Anda adalah merancang fondasi arsitektur, menentukan stack yang tepat, 
        serta mendefinisikan struktur database dan kontrak API.
        
        WAJIB DILAKUKAN SEBELUM DESAIN:
        - Panggil tool `knowledge:search` untuk memahami standar proyek ini.
        - Panggil tool `memory:recall` untuk memastikan tidak ada kesalahan masa lalu yang terulang.
        
        OUTPUT ANDA:
        Satu ringkasan teknis (Blueprint) padat berisi struktur folder, komponen UI utama, dan endpoint.
        Ingat, jangan membuat business logic dulu, berikan hanya spesifikasi!
    """)

    return ToolCallingAgent(
        tools=[],  # Diisi hook MCP Tool 'knowledge:search', 'memory:recall' di saat init Orkesrator
        model=model,
        system_prompt=prompt,
        name="Architect_Agent",
        description="Merancang Blueprint dan arsitektur data.",
    )


def create_backend_agent() -> CodeAgent:
    prompt = dedent("""
        Anda adalah Senior Backend Engineer (Agent 2).
        Tugas Anda adalah mengimplementasikan API dan Database Models di src/backend/
        secara ketat mengikuti Spesifikasi dari Architect.
        
        ATURAN KETAT:
        - Panggil `skills:recall` dengan query (misal "fastapi boilerplate") 
          untuk menggunakan pola koding yang sah di proyek ini.
        - Tulis kode menggunakan `core:filesystem`.
        - Anda HANYA fokus pada endpoint dan middleware.
        - Berikan output: Rangkuman file apa saja yang dibuat/diubah.
    """)
    # Backend agent menggunakan CodeAgent karena ia diizinkan mengeksekusi python logic if needed
    return CodeAgent(
        tools=[],  # Diisi 'core:filesystem', 'skills:recall'
        model=model,
        system_prompt=prompt,
        name="Backend_Agent",
        description="Menulis dan mengeksekusi script Backend API.",
    )


def create_frontend_agent() -> CodeAgent:
    prompt = dedent("""
        Anda adalah Senior Frontend Engineer (Agent 3).
        Tugas Anda adalah membangun antarmuka pengguna (UI Components) di src/frontend/
        berdasarkan kontrak backend dan spesifikasi Architect.
        
        ATURAN KETAT:
        - Buat halaman UI dan integrasikan hooks pengambilan data API (fetch/axios).
        - Gunakan tool `document:view` (OCR) jika Architect menitipkan mockup gambar.
        - Gunakan `core:filesystem` untuk menulis struktur src.
    """)
    return CodeAgent(
        tools=[],  # Diisi 'core:filesystem', 'document:view'
        model=model,
        system_prompt=prompt,
        name="Frontend_Agent",
        description="Membuat komponen UI dan mockups.",
    )


def create_qa_agent() -> ToolCallingAgent:
    prompt = dedent("""
        Anda adalah DevOps & QA Automation Engineer (Agent 4) berkepala dingin.
        Semua kode Backend dan Frontend sudah ditulis sebelumnya. Tugas Anda adalah melakukan TEST.
        
        ATURAN KETAT:
        1. Anda hanya boleh memanggil `core:shell` untuk menjalankan kompilasi. 
           (Misal: `npm run build`, `npm run lint`, atau `pytest`).
        2. Sandbox Anda dilengkapi persistent volume, jadi `node_modules` tidak akan hilang.
        3. Jika TERJADI ERROR: Jangan diam. Panggil `memory:store` untuk menyimpan
           Lesson Learned, dan berikan balasan detail error untuk mengembalikan state ke Backend/Frontend.
        4. Jika SUKSES: Tandai DONE dan simpan log kesuksesan via `memory:store`.
    """)

    return ToolCallingAgent(
        tools=[],  # Diisi khusus 'core:shell', 'memory:store'
        model=model,
        system_prompt=prompt,
        name="QA_Agent",
        description="Sandbox terminal executor dan penguji keandalan aplikasi.",
    )


# --- SemIf (Decision Layer / Validation Gate) ---
def semif_validation_gate(blueprint: str) -> bool:
    """
    Validation Gate untuk RAG Poisoning.
    Di sini SemIf (biasanya dipandu Qwen3-0.6B lokal) memeriksa apakah spesifikasi
    Architect relevan dan realistis. Jika melantur (Poisoning), di-return False.
    """
    # Placeholder logic
    if "garble" in blueprint or len(blueprint) < 50:
        return False
    return True
