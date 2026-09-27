#!/bin/bash
# Script ini digunakan di WSL / REMOTE OFFICE PC untuk menjalankan/menginstal Cloudflare Tunnel SSH

# Token khusus untuk antigravity-wsl-ssh
TOKEN="eyJhIjoiOTM1MzVmMzJiM2FkOTZjZDM0ZGQzNzRmNWNmNDdjZWUiLCJ0IjoiOWY2OGY0YjAtMGQzOS00NWM4LTkwYzQtODYyYTQxZWE0YTZkIiwicyI6ImMzVndaWEp6WldOeVpYUjBkVzV1Wld4elpXTnlaWFF4TWpNME5UWTNPRGt3In0="

if ! command -v cloudflared &> /dev/null; then
    echo "Menginstal cloudflared..."
    mkdir -p ~/.local/bin
    wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O ~/.local/bin/cloudflared
    chmod +x ~/.local/bin/cloudflared
    export PATH="$PATH:$HOME/.local/bin"
fi

echo "============================================================"
echo "Menjalankan Cloudflare SSH Tunnel dengan Token: $TOKEN"
echo "Anda dapat menjalankan perintah ini agar tunnel aktif secara otomatis sebagai Service:"
echo "sudo cloudflared service install $TOKEN"
echo "============================================================"
echo "Memulai tunnel untuk SSH secara background..."

nohup cloudflared tunnel run --token $TOKEN > ~/.cloudflared_ssh.log 2>&1 &
echo "[✔] Tunnel SSH berjalan. Cek log di: ~/.cloudflared_ssh.log"
