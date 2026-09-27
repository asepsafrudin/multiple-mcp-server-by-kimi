---
description: Panduan menyambungkan IDE Antigravity / Agent ke PC Kantor via Remote SSH (Tailscale / Cloudflare)
---

# Remote SSH Connection Setup

Workflow ini digunakan ketika USER ingin menghubungkan IDE Antigravity atau Agent AI lokal di Windows/WSL ke mesin kantor (Remote PC) dengan menggunakan koneksi Tailscale atau Cloudflare Tunnel.

## Langkah 1: Persiapan Kredensial dan Host
Pastikan file konfigurasi `.env.remote` sudah dipopulasi dengan kredensial yang tepat (biasanya ada di `/home/aseps/MCP/env/.env.remote`).
- **Tailscale Host:** 100.78.237.113
- **Port SSH:** 8022

## Langkah 2: Evaluasi Jaringan lokal
Pastikan klien (laptop ini) memiliki aplikasi VPN yang menyala.
// turbo
1. Lakukan ping untuk menguji sambungan Tailscale
`ping -c 2 100.78.237.113`
2. Jika ada status "Time Out", infokan pengguna untuk menyalakan/login ke aplikasi Tailscale Windows di system tray.

## Langkah 3: Menyelaraskan Konfigurasi SSH antara WSL & Windows Host
IDE Antigravity di Windows akan menggunakan konfigurasi dari lingkungan host `C:\Users\username\.ssh`. Jika IDE melaporkan `Could not resolve hostname` atau `No such host is known`, berarti konfigurasinya belum sinkron.
// turbo-all
1. Salin konfigurasi ssh WSL ke direktori ssh host Windows
`mkdir -p /mnt/c/Users/aseps/.ssh`
`cp /home/aseps/.ssh/config /mnt/c/Users/aseps/.ssh/config`
2. Salin Private Key dari WSL ke lingkungan Host Windows
`cp /home/aseps/.ssh/id_ed25519 /mnt/c/Users/aseps/.ssh/id_ed25519`
`cp /home/aseps/.ssh/id_ed25519.pub /mnt/c/Users/aseps/.ssh/id_ed25519.pub`

## Langkah 4: Membuka Workspace di IDE
Setelah SSH tersinkronisasi dan jaringan aktif, *Remote Editor* dapat diluncurkan.
Jalankan perintah ini di terminal WSL untuk otomatis meluncurkan `antigravity` atau `code` di ruang kerja Remote Host.

`antigravity --new-window --folder-uri "vscode-remote://ssh-remote+antigravity-tailscale/home/aseps/MCP"`

## Opsi Tambahan: Menggunakan Cloudflare Tunnel
Jika menggunakan *Cloudflare Tunnel* (`antigravity-cf`), pastikan terminal lokal menginstal ekstensi `cloudflared`.
1. Unduh binary `cloudflared` (jika belum ada)
`mkdir -p ~/.local/bin && wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O ~/.local/bin/cloudflared && chmod +x ~/.local/bin/cloudflared`
2. Konfigurasi `proxyCommand` pada `~/.ssh/config` diisi dengan:
`ProxyCommand ~/.local/bin/cloudflared access ssh --hostname %h`
