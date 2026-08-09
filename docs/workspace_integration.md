# MCP Intelligence — Panduan Integrasi dengan /home/aseps/Workspace

> Dokumen ini menjelaskan cara memanfaatkan kecerdasan `mcp_unified` saat bekerja di Workspace.

---

## 🧠 Arsitektur: Mengapa MCP Bisa Bekerja di Mana Saja

MCP Unified Server bukanlah "fitur yang terikat ke satu folder."
Ia adalah **layanan independen (daemon)** yang:
1. Berjalan sebagai proses terpisah
2. Menerima request via stdio dari IDE/Claude/Cline
3. Mengeksekusi tools berdasarkan **absolute path** yang diberikan

```
Workspace/Projects/govt-archive-scraper/
              ↕ (absolute path)
         mcp_unified (server)
              ↕
         Memory / Vision / Gemini / Gmail / Telegram
```

---

## ✅ Tools yang Langsung Bekerja di Workspace

### 📂 File & Shell Operations
```
read_file(path="/home/aseps/Workspace/Projects/...")
write_file(path="/home/aseps/Workspace/...")

run_shell(command="python3 analyze.py", cwd="/home/aseps/Workspace/Projects/...")
run_shell(command="git log --oneline -10", cwd="/home/aseps/Workspace/Projects/govt-archive-scraper")
run_shell(command="pip install -r requirements.txt", cwd="/home/aseps/Workspace/Tools/image-to-excel")
run_shell(command="streamlit run app.py", cwd="/home/aseps/Workspace/Projects/verification report system")
```

### 🧠 Memory — Simpan Knowledge dari Workspace
```
memory_save(content="...", metadata={"project": "govt-archive-scraper", "type": "finding"})
memory_search(query="temuan korupsi dari scraper...") 
# → Hasilnya bisa dipakai di project mana saja!
```

### 🔍 Document Processing
```
process_govdoc(file_path="/home/aseps/Workspace/Data/surat_masuk.pdf")
# → OCR + AI extraction langsung ke file di Workspace/Data
```

### 🌐 Web Fetch (untuk project scraper)
```
fetch_url(url="https://target.gov.id/laporan")
check_url(url="https://...")
```

### 🤖 Gemini AI (untuk analysis)
```
gemini_analyze(text="<isi dokumen pemerintah>", analysis_type="legal")
gemini_summarize(text="<laporan panjang>", style="executive")
gemini_translate(text="<teks Inggris>", target_language="Bahasa Indonesia")
```

### 📧 Gmail & Telegram (untuk notifikasi/laporan)
```
telegram_send(message="✅ Scraping selesai: 1200 records berhasil")
gmail_send_email(to="stakeholder@email.com", subject="Laporan Bulanan", body="...")
```

---

## 🛠️ Workflow Contoh

### Skenario: Setelah scraping selesai, analisis + kirim laporan

```
1. run_shell("scrapy crawl laporan", cwd="/home/.../govt-archive-scraper")
2. gemini_analyze(text=hasil_scrapy, analysis_type="government")  
3. memory_save(content=insights, metadata={"project": "govt-archive", "date": "2026-02"})
4. telegram_send(message=f"✅ Analisis selesai: {summary}")
5. gmail_send_email(to="boss@email.com", subject="Laporan Scraping Feb 2026", body=full_report)
```

---

## ⚙️ Konfigurasi IDE

File konfigurasi yang sudah terhubung ke Workspace:
- **Cline**: `/home/aseps/MCP/config/cline_mcp_settings.json`
- **Claude Desktop**: `/home/aseps/MCP/config/claude_desktop_config.json`
- **Symlinks aktif**:
  - `/home/aseps/Workspace/.agent` → `/home/aseps/MCP/.agent`
  - `/home/aseps/Workspace/mcp_config.json` → `/home/aseps/MCP/mcp_config.json`

---

## 🔒 Batasan Keamanan

| Batasan | Alasan |
|---------|--------|
| `cwd` harus dalam `/home/aseps`, `/tmp`, atau `/var/log` | Mencegah eksekusi di direktori sistem sensitif |
| Shell command harus ada di whitelist 76 commands | Mencegah arbitrary code injection |
| Output dibatasi 50KB | Mencegah response explosion ke MCP protocol |
| Gmail Service Account perlu DWD | Keamanan akses inbox |

---

## 📋 Projects di Workspace yang Paling Diuntungkan

| Project | Tools MCP yang Relevan |
|---------|----------------------|
| `govt-archive-scraper` | `fetch_url`, `run_shell` (scrapy), `memory_save`, `gemini_analyze` |
| `verification report system` | `process_govdoc`, `gemini_analyze`, `gmail_send_email`, `telegram_send` |
| `aceh-monev-dashboard` | `gemini_summarize`, `memory_search`, `telegram_send` |
| `image-to-excel` | `process_govdoc`, `run_shell` (python3 img2xlsx.py), `telegram_send_file` |
| `robust-pdf-converter` | `process_govdoc`, `run_shell`, `gemini_analyze` |
