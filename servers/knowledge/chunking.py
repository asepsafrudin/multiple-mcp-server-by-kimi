"""Simple text chunking utilities for workspace knowledge."""

from __future__ import annotations

from pathlib import Path


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~0.75 words per token on average."""
    return max(1, len(text.split()))


def _split_by_size(parts: list[str], max_tokens: int, overlap_tokens: int) -> list[str]:
    """Merge small parts into chunks respecting max_tokens with overlap."""
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for part in parts:
        part_tokens = _estimate_tokens(part)
        if part_tokens > max_tokens:
            # Oversized single part: hard-split by characters approximating tokens.
            words = part.split()
            buffer: list[str] = []
            buffer_tokens = 0
            for word in words:
                buffer.append(word)
                buffer_tokens += 1
                if buffer_tokens >= max_tokens:
                    chunks.append(" ".join(buffer))
                    # overlap
                    if overlap_tokens > 0:
                        overlap = (
                            buffer[-overlap_tokens:] if overlap_tokens < len(buffer) else buffer
                        )
                        buffer = overlap
                        buffer_tokens = len(overlap)
                    else:
                        buffer = []
                        buffer_tokens = 0
            if buffer:
                current = [" ".join(buffer)]
                current_tokens = buffer_tokens
            continue

        if current_tokens + part_tokens > max_tokens and current:
            chunks.append("\n\n".join(current))
            if overlap_tokens > 0:
                overlap = []
                overlap_tokens_count = 0
                for piece in reversed(current):
                    piece_tokens = _estimate_tokens(piece)
                    if overlap_tokens_count + piece_tokens <= overlap_tokens:
                        overlap.insert(0, piece)
                        overlap_tokens_count += piece_tokens
                    else:
                        break
                current = overlap
                current_tokens = overlap_tokens_count
            else:
                current = []
                current_tokens = 0

        current.append(part)
        current_tokens += part_tokens

    if current:
        chunks.append("\n\n".join(current))

    return chunks


def chunk_text(
    text: str,
    max_tokens: int = 500,
    overlap_tokens: int = 50,
) -> list[str]:
    """Split text into overlapping chunks by paragraph boundary when possible."""
    parts = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not parts:
        parts = [text]
    return _split_by_size(parts, max_tokens, overlap_tokens)


def chunk_file(path: Path, text: str) -> list[str]:
    """Chunk a file's text with format-aware defaults."""
    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown"}:
        # Markdown: keep sections together if small enough.
        return chunk_text(text, max_tokens=400, overlap_tokens=40)
    if suffix in {".py", ".js", ".ts", ".java", ".go", ".rs", ".c", ".cpp", ".h"}:
        # Code: prefer function/class boundaries, but chunk_text does not parse AST.
        return chunk_text(text, max_tokens=300, overlap_tokens=30)
    return chunk_text(text, max_tokens=500, overlap_tokens=50)
