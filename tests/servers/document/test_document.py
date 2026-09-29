"""Tests for document server."""

from unittest.mock import MagicMock, patch

import pytest

from servers.document.server import document_extract_text, document_view_page


@pytest.fixture
def mock_fitz():
    with patch("servers.document.server.fitz") as mock_fitz_module:
        mock_doc = MagicMock()
        mock_doc.__len__.return_value = 2  # 2 pages

        mock_page_0 = MagicMock()
        mock_page_0.get_text.return_value = "Hello Page 0"
        mock_pixmap = MagicMock()
        mock_pixmap.tobytes.return_value = b"mockpngdata"
        mock_page_0.get_pixmap.return_value = mock_pixmap

        mock_page_1 = MagicMock()
        mock_page_1.get_text.return_value = "Hello Page 1"

        def load_page_side_effect(idx):
            if idx == 0:
                return mock_page_0
            elif idx == 1:
                return mock_page_1
            raise ValueError(f"Page {idx} not found in mock")

        mock_doc.load_page.side_effect = load_page_side_effect
        mock_fitz_module.open.return_value = mock_doc
        yield mock_fitz_module


@patch("servers.document.server.Path.exists")
def test_document_extract_text(mock_exists, mock_fitz):
    mock_exists.return_value = True

    result = document_extract_text("dummy.pdf")

    assert result["status"] == "ok"
    assert result["total_pages"] == 2
    assert result["extracted_pages"] == 2
    assert "Hello Page 0" in result["text"]
    assert "Hello Page 1" in result["text"]


@patch("servers.document.server.Path.exists")
def test_document_view_page(mock_exists, mock_fitz):
    mock_exists.return_value = True

    result = document_view_page("dummy.pdf", 0)

    assert result["status"] == "ok"
    assert result["page_number"] == 0
    assert result["total_pages"] == 2
    assert "image_data" in result
    assert result["image_data"].startswith("data:image/png;base64,")


@patch("servers.document.server.Path.exists")
def test_document_view_page_out_of_bounds(mock_exists, mock_fitz):
    mock_exists.return_value = True

    result = document_view_page("dummy.pdf", 5)

    assert result["status"] == "error"
    assert "out of bounds" in result["error"]
