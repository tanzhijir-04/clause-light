"""DocumentIngress 单元测试"""

from __future__ import annotations

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
