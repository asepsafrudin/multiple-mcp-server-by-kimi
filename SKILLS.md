# Skill Registry (Procedural Memory)

MCP Skills Server menyimpan **procedural memory**: reusable prompt patterns, workflows, dan instruksi coding agentic yang bisa di-recall oleh agent saat dibutuhkan.

## Konsep

- **Skill** — unit procedural memory dengan name, description, prompt_template, triggers, tools_required, examples.
- **Namespace** — isolasi skill (default `global`).
- **Category** — bebas, misal `coding`, `devops`, `writing`, `analysis`.
- **Triggers** — kata kunci yang memicu recall skill.
- **Semantic Recall** — skill dicari berdasarkan deskripsi, trigger, dan prompt template.

## Tools

| Tool | Fungsi |
|------|--------|
| `skill_register` | Register skill baru |
| `skill_recall` | Cari skill berdasarkan query |
| `skill_list` | List semua skill |
| `skill_load` | Load skill by name |
| `skill_update` | Update field skill |
| `skill_delete` | Hapus skill |
| `skill_load_registry` | Bulk load dari folder YAML/JSON |

## Backend

- **SQLite** local-first: `data/skills_v2.db`
- **sqlite-vec** + **FTS5** untuk recall
- **Ollama** embedding

## Format Disk Registry

Buat file YAML/JSON di `skills/registry/`:

```yaml
name: python-refactor
namespace: coding
category: coding
description: Refactor Python code using type hints and clean architecture.
triggers:
  - refactor
  - python
  - type hints
prompt_template: |
  You are a Python expert. Refactor the provided code to use type hints,
  dataclasses, and small functions. Explain each change.
tools_required:
  - filesystem
  - shell
examples:
  - Refactor legacy script into modules
version: 1
```

## Contoh Penggunaan

```python
await skill_register(
    name="python-refactor",
    namespace="coding",
    description="Refactor Python code using type hints and clean architecture.",
    prompt_template="You are a Python expert...",
    triggers=["refactor", "python"],
    tools_required=["filesystem", "shell"],
)

skills = await skill_recall(query="refactor python", namespace="coding", limit=3)
```

## Implementasi

Lihat `servers/skills/engine.py`, `servers/skills/loader.py`, `servers/skills/server.py`.

---

## Protokol Agent Skill (Open Standard) — ringkasan §14

> ⚠️ **Jangan tertukar.** *Skill* di dokumen ini = **procedural memory registry** (runtime, SQLite + sqlite-vec) milik suite ini. Berbeda dari **Agent Skill** standar terbuka (https://agentskills.io) — folder berisi `SKILL.md` yang dibaca agent untuk membakukan alur kerja.

Saat membakukan alur kerja berulang agar dipakai ulang lintas agent, ikuti rulebook kanonik **[`.agents/AGENTS.md` §14](../../.agents/AGENTS.md)** dan prosedur lengkap di **[`docs/00-meta/08-agent-skill-authoring.md`](../../docs/00-meta/08-agent-skill-authoring.md)**.

Ringkas:

1. **Satu skill = satu pekerjaan.** `SKILL.md` berisi frontmatter (`name` = nama folder; `description` memuat *apa* + *kapan dipakai* dengan kata pemicu) + body imperatif. Materi panjang → `references/`; kode → `scripts/`.
2. **Lokasi & prioritas:** `.commandcode/skills/<nama>/` (proyek, prioritas tertinggi) · `.agents/skills/<nama>/` (lintas tool) · `~/.commandcode/skills` | `~/.agents/skills` (user). Mirror ke `.agents/` agar terdeteksi Cline/Kimi/Cursor.
3. **Nama wajib** lowercase-huruf-angka-tanda-hubung (≤64), tanpa `-` di ujung/ganda, **sama persis dengan nama folder**.
4. **Verifikasi sebelum selesai:** skill termuat tanpa warning, dipanggil minimal sekali, dan bila membawa `scripts/` jalankan uji nyata.

> Suite ini berstatus **DEPRECATED**; ringkasan di atas hanya rujukan dokumentasi — fitur/kode baru diletakkan di `servers/` atau `core/mcp-unified/`.
