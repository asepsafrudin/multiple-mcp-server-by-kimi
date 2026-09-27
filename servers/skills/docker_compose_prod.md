---
name: docker_compose_prod
namespace: devops
category: template
description: Secure and scalable docker-compose definitions.
triggers:
  - make docker-compose
  - containerize app
---

# Docker Compose untuk Produksi & Sandbox

Gunakan referensi struktur ini saat agen diminta membuatkan lingkungan isolasi berbasis Docker Compose. Standar ini memastikan *database* tidak terjemur *(exposed)* langsung ke *host* kecuali via instans *backend*.

## Docker Compose Berbasis Jaring Isolasi (Isolation Network Base)

```yaml
version: '3.8'

services:
  database:
    image: postgres:15-alpine
    restart: always
    environment:
      POSTGRES_USER: ${DB_USER:-admin}
      POSTGRES_PASSWORD: ${DB_PASSWORD:-securepassword}
      POSTGRES_DB: ${DB_NAME:-app_db}
    volumes:
      - pgdata:/var/lib/postgresql/data
    networks:
      - backend-net

  api:
    build: 
      context: ./backend
      dockerfile: Dockerfile
    restart: always
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://${DB_USER:-admin}:${DB_PASSWORD:-securepassword}@database:5432/${DB_NAME:-app_db}
    depends_on:
      - database
    networks:
      - backend-net
      - frontend-net

  web:
    build:
      context: ./frontend
      dockerfile: Dockerfile.prod
    restart: always
    ports:
      - "80:80"
    depends_on:
      - api
    networks:
      - frontend-net

volumes:
  pgdata:

networks:
  backend-net:
    internal: true # Sangat krusial! Memutus akses internet DB.
  frontend-net:
```

## Aturan Agen
1. Selalu buatkan *Volume* bernama (seperti `pgdata`) untuk persistensi data *database*.
2. Selalu pisahkan *Network* (jaring). `backend-net` harus diatur ke `internal: true` sehingga servis `database` sama sekali tidak bisa di-ping dari internet, hanya dari `api`.
