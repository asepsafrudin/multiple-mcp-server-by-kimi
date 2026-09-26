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


def _python_ast_outline(text: str) -> str | None:
    """Generate a high-level AST outline (classes/functions) enriched with graph dependencies."""
    import ast
    try:
        tree = ast.parse(text)
    except Exception:
        return None
        
    class DependencyExtractor(ast.NodeVisitor):
        def __init__(self):
            self.deps = set()
        def visit_Call(self, node):
            if isinstance(node.func, ast.Name):
                self.deps.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name):
                    self.deps.add(f"{node.func.value.id}.{node.func.attr}")
                else:
                    self.deps.add(node.func.attr)
            self.generic_visit(node)

    outline = ["# [METADATA: PYTHON FILE OUTLINE & SYMBOLS]"]
    found_symbols = False
    
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            found_symbols = True
            bases = [ast.unparse(b) for b in node.bases] if hasattr(ast, 'unparse') else []
            base_str = f"({', '.join(bases)})" if bases else ""
            
            methods = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            extractor = DependencyExtractor()
            extractor.visit(node)
            deps = ", ".join(sorted(extractor.deps)[:10]) # Limit to 10 for token brevity
            
            outline.append(f"class {node.name}{base_str}:")
            if methods:
                outline.append(f"    # Methods: {', '.join(methods)}")
            if deps:
                outline.append(f"    # Dependencies: {deps}")
            outline.append("    ...")
            
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            found_symbols = True
            extractor = DependencyExtractor()
            extractor.visit(node)
            deps = ", ".join(sorted(extractor.deps)[:10])
            
            args = ast.unparse(node.args) if hasattr(ast, 'unparse') else "..."
            outline.append(f"def {node.name}({args}):")
            if deps:
                outline.append(f"    # Dependencies: {deps}")
            outline.append("    ...")
            
    if found_symbols:
        return "\n".join(outline)
    return None


def chunk_file(path: Path, text: str) -> list[str]:
    """Chunk a file's text with format-aware defaults and AST outlines."""
    suffix = path.suffix.lower()
    chunks = []
    
    if suffix in {".md", ".markdown"}:
        # Markdown: keep sections together if small enough.
        chunks.extend(chunk_text(text, max_tokens=400, overlap_tokens=40))
    elif suffix == ".py":
        # Python Code: Generate AST Outline for 5% token efficiency on symbol searches
        outline = _python_ast_outline(text)
        if outline:
            chunks.append(outline)
        # Fallback to standard chunking for the detail body 
        chunks.extend(chunk_text(text, max_tokens=300, overlap_tokens=30))
    elif suffix in {".js", ".ts", ".java", ".go", ".rs", ".c", ".cpp", ".h"}:
        # Other Code: Currently falls back to standard text chunking
        chunks.extend(chunk_text(text, max_tokens=300, overlap_tokens=30))
    else:
        chunks.extend(chunk_text(text, max_tokens=500, overlap_tokens=50))
        
    return chunks
