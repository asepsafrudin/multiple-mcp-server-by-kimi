---
name: react_vite_tailwind_setup
namespace: frontend
category: template
description: Initialization and structural standard for React + Vite + Tailwind CSS with routing and Error Boundaries.
triggers:
  - make react app
  - setup vite frontend
  - frontend boilerplate
---

# React Vite & Tailwind Boilerplate

Panduan dan instruksi dasar untuk agen ketika mulai membangun *frontend* berbasis React.

## 1. Instalasi (Vite)
Jalankan di terminal menggunakan parameter `--template react-ts`:
```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
npm install react-router-dom axios
```

## 2. Struktur Folder
```text
src/
├── assets/
├── components/
│   ├── ui/
│   └── layout/
├── pages/
├── hooks/
├── context/
├── App.tsx
├── main.tsx
└── index.css
```

## 3. Konfigurasi Tailwind (tailwind.config.js)
```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: "#1d4ed8",
        secondary: "#9333ea",
      }
    },
  },
  plugins: [],
}
```
*Pastikan `@tailwind` directives dimasukkan ke `index.css`!*

## 4. Error Boundary (Standard Enterprise)
Selalu lindungi komponen *routing* dengan `ErrorBoundary` agar saat terjadi *runtime error*, UI tidak jadi blank (putih layar). Disarankan memakai library tambahan `react-error-boundary` atau mengimplementasikan class component manual.

## 5. Main App Routing (App.tsx)
Gunakan *React Router DOM* untuk struktur *routing* dasar:
```tsx
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Home from './pages/Home';
import NotFound from './pages/NotFound';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        {/* Fallback 404 Route */}
        <Route path="*" element={<NotFound />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
```
