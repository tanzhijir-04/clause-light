"""DocumentIngress 单元测试"""

from __future__ import annotations

import pytest

from server.core.document_ingress import DocumentResult, OFFICE_EXTENSIONS


def test_document_result_fields():
    r = DocumentResult(
        full_text="# 合同",
        markdown="# 合同",
        source="anydoc",
        confidence_avg=1.0,
    )
    assert r.source == "anydoc"
    assert ".docx" in OFFICE_EXTENSIONS


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
