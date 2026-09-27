---
name: fastapi_secure_boilerplate
namespace: backend
category: template
description: Boilerplate for a production-ready, secure FastAPI application with CORS, JWT, and Pydantic.
triggers:
  - make a fastapi app
  - python backend
  - fastapi standard
---

# FastAPI Secure Boilerplate

Gunakan struktur dan *code snippet* ini sebagai basis saat menginisiasi *backend* FastAPI.

## 1. Struktur Folder (Standard Layout)
```text
src/
├── main.py
├── core/
│   ├── config.py
│   └── security.py (JWT, Hashing)
├── api/
│   └── v1/
│       ├── router.py
│       └── endpoints/
│           ├── auth.py
│           └── items.py
├── schemas/
│   └── item.py (Pydantic Models)
└── models/
    └── database.py (SQLAlchemy / SQLModel)
```

## 2. Pydantic Validation & Security (core/security.py)
Selalu gunakan skema validasi yang ketat.
```python
from datetime import datetime, timedelta, UTC
from jose import jwt
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = "CHANGE_THIS_TO_SECURE_SECRET_IN_PROD"
ALGORITHM = "HS256"

def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
```

## 3. main.py (Entrypoint)
Pastikan CORS selalu terkonfigurasi dengan benar untuk mencegah akses dari *origin* yang tidak dikenal.
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.v1.router import api_router

app = FastAPI(title="Enterprise App API")

# Konfigurasi CORS
origins = [
    "http://localhost:3000",
    "http://localhost:5173", # Vite default
    # "https://production-domain.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")

@app.get("/health")
def health_check():
    return {"status": "ok"}
```
