---
name: "remote_ssh_connection"
description: "Skill untuk mendiagnosis, mengatur, dan meluncurkan konfigurasi Remote SSH via IDE menggunakan konektivitas Tailscale VPN atau Cloudflare Zero Trust."
---

# Skill: Remote SSH Connection Setup & Troubeshooting

Gunakan instruksi ini ketika Anda diminta untuk menyiapkan koneksi jarak jauh ke server atau PC Remote, terutama untuk Sinkronisasi WSL ke Host Windows, Tailscale, dan Cloudflare Tunnel.

## Perintah Diagnostik yang Bermanfaat
1. Mengecek Konfigurasi Jaringan:
   - Terkait **Tailscale**: Cek ping ke node Tailscale `ping -c 2 100.78.237.113`. Jika gagal di WSL lokal, hubungi/periksa aplikasi *host* Windows `tailscale.exe status`
   - Terkait **Cloudflare**: Pastikan `cloudflared` terinstal. Perintah instal:
     ```bash
     mkdir -p ~/.local/bin && wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O ~/.local/bin/cloudflared && chmod +x ~/.local/bin/cloudflared
     ```

2. Problem: "Could not resolve hostname" atau "No such host is known" pada VS Code / Antigravity di dalam WSL
   Akar Permasalahannya: IDE GUI berjalan pada sistem Windows Host, ia mencari berkas `C:\Users\username\.ssh\config` BUKAN `/home/username/.ssh/config`.
   Solusi/SOP: Sinkronisasikan file dan kunci private dengan command bash berikut:
   ```bash
   mkdir -p /mnt/c/Users/aseps/.ssh
   cp /home/aseps/.ssh/config /mnt/c/Users/aseps/.ssh/config
   cp /home/aseps/.ssh/id_ed25519* /mnt/c/Users/aseps/.ssh/
   ```

## Menghubungkan Workspace ke IDE
Alih-alih menggunakan cara manual via GUI, hubungkan Remote Explorere Agent / Antigravity secara instan menggunakan perintah CLI:
```bash
antigravity --new-window --folder-uri "vscode-remote://ssh-remote+<NAMA_HOST_SSH>/<PATH_WORKSPACE_PROYEK>"
```
*Contoh spesifik: `vscode-remote://ssh-remote+antigravity-tailscale/home/aseps/MCP`*
