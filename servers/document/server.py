"""MCP server for Document capabilities (PDF parsing, visual rendering)."""

from __future__ import annotations

import base64
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import fitz  # PyMuPDF
from fastmcp import FastMCP

from shared.logging import configure_logging, get_logger

configure_logging()
logger = get_logger("mcp.document")

mcp = FastMCP(
    name="mcp-document-server",
    instructions="Provides capabilities to extract text and visually render large documents like PDFs.",
)


@mcp.tool()
def document_extract_text(file_path: str, start_page: int = 0, end_page: int = -1) -> dict:
    """
    Extract text from a PDF document sequentially. 
    Can be used by Harvester (Baidu OCR logic placeholder) or agent to read text.
    """
    path = Path(file_path)
    if not path.exists():
        return {"status": "error", "error": f"File not found: {file_path}"}
    
    try:
        doc = fitz.open(path)
        total_pages = len(doc)
        
        if end_page == -1 or end_page >= total_pages:
            end_page = total_pages - 1
            
        extracted_text = []
        for i in range(start_page, end_page + 1):
            page = doc.load_page(i)
            text = page.get_text()
            extracted_text.append(f"--- Page {i} ---\n{text}")
            
        full_text = "\n".join(extracted_text)
        return {
            "status": "ok", 
            "total_pages": total_pages, 
            "extracted_pages": end_page - start_page + 1,
            "text": full_text
        }
    except Exception as exc:
        logger.error("document_extract_text_failed", error=str(exc))
        return {"status": "error", "error": str(exc)}
    finally:
        if 'doc' in locals():
            doc.close()


@mcp.tool()
def document_view_page(file_path: str, page_number: int, zoom: int = 2) -> dict:
    """
    Render a specific page of a PDF document into a high-resolution base64 PNG image.
    Used for On-Demand Visual Rendering (bypassing OCR resolution degradation).
    """
    path = Path(file_path)
    if not path.exists():
        return {"status": "error", "error": f"File not found: {file_path}"}
    
    try:
        doc = fitz.open(path)
        total_pages = len(doc)
        
        if page_number < 0 or page_number >= total_pages:
            return {"status": "error", "error": f"Page number {page_number} out of bounds (0-{total_pages-1})"}
            
        page = doc.load_page(page_number)
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        
        img_bytes = pix.tobytes("png")
        b64_encoded = base64.b64encode(img_bytes).decode("utf-8")
        
        return {
            "status": "ok",
            "page_number": page_number,
            "total_pages": total_pages,
            "image_data": f"data:image/png;base64,{b64_encoded}"
        }
    except Exception as exc:
        logger.error("document_view_page_failed", error=str(exc))
        return {"status": "error", "error": str(exc)}
    finally:
        if 'doc' in locals():
            doc.close()


def main() -> None:
    from shared.server_runner import run
    run(mcp)


if __name__ == "__main__":
    main()
