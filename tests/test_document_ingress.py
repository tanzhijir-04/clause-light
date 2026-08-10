"""DocumentIngress 单元测试"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from server.core.document_ingress import DocumentResult, OFFICE_EXTENSIONS, ALLOWED_UPLOAD_EXTENSIONS
from server.core.ocr import OCRResult


def test_document_result_fields():
    r = DocumentResult(
        full_text="# 合同",
        markdown="# 合同",
        source="anydoc",
        confidence_avg=1.0,
    )
    assert r.source == "anydoc"
    assert ".docx" in OFFICE_EXTENSIONS


def test_allowed_upload_includes_office_and_images():
    """上传白名单覆盖办公文档 + 图片扩展（含 webp/tif）"""
    assert ".docx" in ALLOWED_UPLOAD_EXTENSIONS
    assert ".pdf" in ALLOWED_UPLOAD_EXTENSIONS
    assert ".webp" in ALLOWED_UPLOAD_EXTENSIONS
    assert ".tif" in ALLOWED_UPLOAD_EXTENSIONS
    assert ".txt" not in ALLOWED_UPLOAD_EXTENSIONS  # 纯文本走 WS，不经 HTTP 上传白名单


@pytest.mark.asyncio
async def test_anydoc_path_returns_markdown(tmp_path, monkeypatch):
    f = tmp_path / "a.docx"
    f.write_bytes(b"PK\x03\x04fake")
    from server.core import document_ingress as di

    async def fake_anydoc(path: str) -> str:
        return "# 标题\n条款一"

    monkeypatch.setattr(di, "_convert_with_anydoc", fake_anydoc)
    result = await di.ingest(str(f), force_route="anydoc")
    assert "条款一" in result.full_text
    assert result.source == "anydoc"


@pytest.mark.asyncio
async def test_image_routes_to_paddle(tmp_path, monkeypatch):
    f = tmp_path / "scan.png"
    f.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    from server.core import document_ingress as di

    mock_engine = MagicMock()
    mock_engine.recognize = AsyncMock(
        return_value=OCRResult(
            full_text="图片合同条款",
            pages=[{"page": 1, "text": "图片合同条款", "line_count": 1}],
            confidence_avg=0.91,
        )
    )
    monkeypatch.setattr(di, "get_ocr_engine", lambda: mock_engine)

    result = await di.ingest(str(f))
    assert result.source == "paddle"
    assert "图片合同条款" in result.full_text
    assert result.confidence_avg == 0.91
    mock_engine.recognize.assert_awaited_once_with(str(f))


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["scan.webp", "scan.tif"])
async def test_webp_tif_routes_to_paddle(tmp_path, monkeypatch, name):
    """webp/tif 必须进入 Paddle，且 OCREngine 识别为图片（修复白名单不一致）"""
    f = tmp_path / name
    f.write_bytes(b"fake-image-bytes")
    from server.core import document_ingress as di
    from server.core.ocr import OCREngine

    assert OCREngine()._is_image(str(f)) is True

    mock_engine = MagicMock()
    mock_engine.recognize = AsyncMock(
        return_value=OCRResult(full_text="webp条款", confidence_avg=0.8)
    )
    monkeypatch.setattr(di, "get_ocr_engine", lambda: mock_engine)

    result = await di.ingest(str(f))
    assert result.source == "paddle"
    assert "webp条款" in result.full_text


@pytest.mark.asyncio
async def test_docx_routes_to_anydoc(tmp_path, monkeypatch):
    f = tmp_path / "contract.docx"
    f.write_bytes(b"PK\x03\x04fake")
    from server.core import document_ingress as di

    async def fake_anydoc(path: str) -> str:
        return "# 租房合同\n第一条"

    monkeypatch.setattr(di, "_convert_with_anydoc", fake_anydoc)
    result = await di.ingest(str(f))
    assert result.source == "anydoc"
    assert "第一条" in result.full_text


@pytest.mark.asyncio
async def test_pdf_short_text_routes_to_paddle(tmp_path, monkeypatch):
    f = tmp_path / "scan.pdf"
    f.write_bytes(b"%PDF-1.4 fake")
    from server.core import document_ingress as di

    async def fake_anydoc(path: str) -> str:
        return "短"  # < 100 字

    monkeypatch.setattr(di, "_convert_with_anydoc", fake_anydoc)

    mock_engine = MagicMock()
    mock_engine._extract_text_pymupdf = MagicMock(
        return_value=OCRResult(full_text="也短", pages=[], confidence_avg=1.0)
    )
    mock_engine.recognize = AsyncMock(
        return_value=OCRResult(
            full_text="扫描件识别出的长文本" + ("x" * 100),
            pages=[{"page": 1, "text": "扫描件", "line_count": 1}],
            confidence_avg=0.88,
        )
    )
    monkeypatch.setattr(di, "get_ocr_engine", lambda: mock_engine)

    result = await di.ingest(str(f))
    assert result.source == "paddle"
    assert "扫描件识别出的长文本" in result.full_text
    mock_engine.recognize.assert_awaited()


@pytest.mark.asyncio
async def test_pdf_hybrid_when_anydoc_and_paddle_both_contribute(tmp_path, monkeypatch):
    f = tmp_path / "mixed.pdf"
    f.write_bytes(b"%PDF-1.4 fake")
    from server.core import document_ingress as di

    async def fake_anydoc(path: str) -> str:
        return "AnyDoc片段不足一百"  # < 100

    monkeypatch.setattr(di, "_convert_with_anydoc", fake_anydoc)

    mock_engine = MagicMock()
    mock_engine._extract_text_pymupdf = MagicMock(
        return_value=OCRResult(full_text="", pages=[], confidence_avg=0.0)
    )
    mock_engine.recognize = AsyncMock(
        return_value=OCRResult(
            full_text="Paddle片段",
            pages=[],
            confidence_avg=0.8,
        )
    )
    monkeypatch.setattr(di, "get_ocr_engine", lambda: mock_engine)

    result = await di.ingest(str(f))
    assert result.source == "hybrid"
    assert "AnyDoc片段" in result.full_text
    assert "Paddle片段" in result.full_text
