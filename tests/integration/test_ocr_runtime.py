from __future__ import annotations

import pytest

from server.core.ocr import OCREngine


@pytest.mark.ocr_integration
@pytest.mark.asyncio
async def test_paddleocr_runtime_reads_fixed_fixture() -> None:
    engine = OCREngine()
    result = await engine.recognize("tests/fixtures/ocr/simple_chinese_contract.png")
    assert result.full_text.strip()
    assert "合同" in result.full_text
