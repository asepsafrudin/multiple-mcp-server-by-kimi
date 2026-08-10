# Deployment Guide

## Instalasi

```bash
git clone https://github.com/asepsafrudin/multiple-mcp-server-by-kimi.git /home/aseps/MCP
cd /home/aseps/MCP
cp .env.example .env
# edit .env
make install
```

## Menjalankan Dependensi (Docker)

```bash
docker-compose up -d
```

Ini akan menjalankan:
- Ollama di port 11434
- Redis di port 6379

Pull model embedding:

```bash
docker exec -it mcp-ollama ollama pull nomic-embed-text
```

## Kredensial & .env

Server modular membaca `/home/aseps/MCP/.env` (gitignored, path dikunci otomatis ke
root proyek — tidak bergantung direktori kerja proses). Nilai env yang di-set lewat
variabel lingkungan OS menang di atas `.env`.

Key yang dipakai kode (modern):

| Env var | Dipakai server | Contoh |
|---------|----------------|--------|
| `GMAIL_CREDENTIALS_PATH` | mcp-gmail (OAuth2) | path ke client-secret / token JSON |
| `GMAIL_TOKEN_PATH` | mcp-gmail (OAuth2) | path ke token JSON |
| `GOOGLE_VISION_CREDENTIALS_PATH` | mcp-vision (service account) | path ke JSON |
| `GEMINI_API_KEY` | mcp-gemini | gemini key |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | mcp-telegram | bot token + chat id |
| `MIKROTIK_HOST` | mcp-mikrotik (REST+SSH) | IP routerboard |
| `MIKROTIK_USER` / `MIKROTIK_PASSWORD` | mcp-mikrotik | user + password RouterOS |
| `MIKROTIK_PORT` / `MIKROTIK_SCHEME` | mcp-mikrotik | `80` / `http` (www) atau `443` / `https` (www-ssl) |
| `OPENAI_API_KEY` | (cadangan) | — |

> Catatan kompatibilitas: `GOOGLE_VISION_KEY_PATH` (nama lama) tetap diterima sebagai
> alias `GOOGLE_VISION_CREDENTIALS_PATH`. Key legacy lain (`GOOGLE_GMAIL_KEY_PATH`,
> `GOOGLE_GMAIL_CLIENT_SECRET`, `OPEN_API_KEY`, `APP_CONFIG_PATH`,
> `MCP_SERVER_CONFIG_PATH`) **tidak** dipetakan ke server modular saat ini — pakai
> nama modern di atas. Jangan pernah commit `.env`.

### Setup Gmail (OAuth2, sekali saja)

1. Buka [Google Cloud Console](https://console.cloud.google.com) → *APIs & Services*
   → aktifkan **Gmail API** → *Credentials* → **OAuth 2.0 Client ID** (jenis Desktop).
2. Unduh JSON client secret ke `GMAIL_CREDENTIALS_PATH`
   (`config/credentials/gmail-client-secret.json`).
3. Jalankan bootstrap OAuth sekali (membuka browser untuk consent):
   ```bash
   ./.venv/bin/python scripts/gmail_oauth_setup.py
   ```
   Token tersimpan ke `GMAIL_TOKEN_PATH` (`config/credentials/gmail-token.json`).
4. Reload editor; tool `gmail_*` di mcp-gmail-bridge akan berfungsi.

### Setup MikroTik RouterOS bridge

Bridge `mcp-mikrotik-bridge` (`servers/bridge/mikrotik_server.py`) menghubungkan agent ke
RouterBoard dengan **dua jalur**:

| Jalur | Mekanisme | Kapan jalan |
|-------|-----------|-------------|
| **REST API** | `httpx` ke `/rest/...` (Basic auth) | RouterOS v7 / v6.48.2+, layanan `www`/`www-ssl` aktif |
| **SSH** | `asyncssh` perintah CLI (`/export`, `/log print`, dst.) | layanan `ssh` aktif + user dengan hak login |

Tools REST: `mikrotik_run_rest`, `mikrotik_get_identity`, `mikrotik_get_system_resource`,
`mikrotik_get_interfaces`, `mikrotik_get_ip_addresses`, `mikrotik_ping`.
Tools SSH: `mikrotik_ssh_command`, `mikrotik_export_config`.

**Konfigurasi `.env`:**

```dotenv
MIKROTIK_HOST=192.168.1.2
MIKROTIK_PORT=80          # REST via www (HTTP); pakai 443 jika www-ssl diaktifkan
MIKROTIK_SCHEME=http      # atau https
MIKROTIK_TLS_VERIFY=false # abaikan cert self-signed (hanya untuk https)
MIKROTIK_USER=admin
MIKROTIK_PASSWORD=password_router
MIKROTIK_SSH_PORT=22
```

**Aktivasi di router (dari Winbox/WebFig/SSH), hanya untuk jalur REST:**

- Pakai HTTP (paling mudah, port 80) — biasanya sudah aktif:
  ```
  /ip service set www disabled=no
  ```
- Pakai HTTPS (port 443) — butuh sertifikat self-signed. Prosedur (RouterOS v7) yang
  teruji:
  ```
  # 1) Buat CA, lalu self-sign
  /certificate add name=ca-key common-name=ca key-usage=key-cert-sign,crl-sign days-valid=3650
  /certificate sign ca-key
  /certificate set ca-key trusted=yes

  # 2) Buat sertifikat server, dikeluarkan oleh CA
  /certificate add name=server-key common-name=192.168.1.2 key-usage=digital-signature,key-encipherment,tls-server days-valid=3650
  /certificate sign server-key ca=ca-key
  /certificate set server-key trusted=yes

  # 3) Aktifkan www-ssl pakai sertifikat server
  /ip service set www-ssl disabled=no certificate=server-key
  ```
  Di `.env` pakai `MIKROTIK_SCHEME=https`, `MIKROTIK_PORT=443`, `MIKROTIK_TLS_VERIFY=false`
  (sertifikat self-signed tidak diverifikasi).

Jalur **SSH selalu lebih aman** (terenkripsi) untuk operasi sensitif; jalur REST via HTTP
mengirim kredensial dalam plaintext — disarankan hanya di jaringan LAN terpercaya.

> Keamanan: buat user khusus dengan group `full` (mis. `mcp`) daripada memakai `admin`
> untuk aktivitas dari agent.

## Menjalankan Server

### 1. Mode stdio untuk Editor

Server dibaca sebagai MCP *client* oleh editor; setiap entry me-spawn satu proses stdio.
Salin konfigurasi editor yang sesuai ke lokasi yang benar:

```bash
# Claude Desktop
mkdir -p ~/.config/claude
cp config/claude_desktop_config.json ~/.config/claude/config.json

# Cline (VS Code) — file aktif dibaca Cline dari ~/.cline/data/settings/
mkdir -p ~/.cline/data/settings
cp config/cline_mcp_settings.json ~/.cline/data/settings/cline_mcp_settings.json
```

> Catatan: path Cline adalah `~/.cline/data/settings/cline_mcp_settings.json`, bukan
> `~/.config/cline/mcp_settings.json`. Cline memakai format *nested* `transport`
> (`.mcpServers.<name>.transport.{type,command,args,env}`) seperti di template.
>
> Setelah mengubah config, **reload / restart editor** agar server MCP baru terbaca.

Pastikan path `/home/aseps/MCP/.venv/bin/python` sesuai dengan sistem Anda.

### 2. Mode SSE untuk Remote/Testing

```bash
make start
```

Akses endpoint:
- http://127.0.0.1:8000/sse — core
- http://127.0.0.1:8001/sse — memory
- http://127.0.0.1:8002/sse — knowledge
- http://127.0.0.1:8003/sse — skills
- http://127.0.0.1:8004/sse — gmail
- http://127.0.0.1:8005/sse — telegram
- http://127.0.0.1:8006/sse — gemini
- http://127.0.0.1:8007/sse — vision
- http://127.0.0.1:8008/sse — mikrotik

```bash
make stop
```

## Backup

```bash
make backup
```

Hasil backup disimpan di `backups/` dengan timestamp.

## Update

```bash
git pull origin main
make dev
make test
make restart
```

## Troubleshooting

| Masalah | Solusi |
|---------|--------|
| Ollama tidak terhubung | Pastikan Ollama berjalan dan model `nomic-embed-text` sudah di-pull. |
| Redis tidak terhubung | Embedding akan tetap jalan tanpa cache; periksa `REDIS_URL`. |
| Permission denied PostgreSQL | Saat ini memory/knowledge menggunakan SQLite local-first; PostgreSQL hanya disiapkan untuk masa depan. |
| Tool tidak muncul di editor | Periksa log editor dan `logs/mcp-*.log`; pastikan path Python benar. |
| MikroTik REST gagal "All connection attempts failed" | Pastikan `MIKROTIK_HOST` benar, dan layanan `www` (80) / `www-ssl` (443) aktif. Cek port terbuka, mis. `nc -vz <ip> 80`. |
| MikroTik REST "401/403" | `MIKROTIK_USER`/`MIKROTIK_PASSWORD` salah atau user tidak punya akses group `full`. |
| MikroTik SSH error auth | Aktifkan layanan `ssh` di router dan beri user hak login (group `full`). |
