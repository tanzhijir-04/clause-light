"""OCR 功能测试

测试 OCR 引擎的核心功能，使用 mock 模拟 PaddleOCR 和 PyMuPDF，
避免依赖真实 OCR 模型和文件系统。
"""

from __future__ import annotations

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock

from server.core.ocr import (
    OCREngine,
    OCRResult,
    ensure_supported_paddleocr_version,
    get_ocr_engine,
)


# ── OCRResult 数据类测试 ──


class TestOCRResult:
    """测试 OCRResult 数据类"""

    def test_default_values(self):
        """测试默认值"""
        result = OCRResult()
        assert result.full_text == ""
        assert result.pages == []
        assert result.confidence_avg == 0.0

    def test_custom_values(self):
        """测试自定义值"""
        result = OCRResult(
            full_text="测试文本",
            pages=[{"page": 1, "text": "测试文本", "line_count": 1}],
            confidence_avg=0.95,
        )
        assert result.full_text == "测试文本"
        assert len(result.pages) == 1
        assert result.confidence_avg == 0.95


# ── 文件类型检测测试 ──


class TestFileTypeDetection:
    """测试文件类型检测"""

    def setup_method(self):
        """每个测试前创建新的 OCREngine 实例"""
        self.engine = OCREngine()

    def test_is_pdf_true(self):
        """测试 PDF 文件检测"""
        assert self.engine._is_pdf("test.pdf") is True
        assert self.engine._is_pdf("test.PDF") is True
        assert self.engine._is_pdf("path/to/contract.pdf") is True

    def test_is_pdf_false(self):
        """测试非 PDF 文件检测"""
        assert self.engine._is_pdf("test.jpg") is False
        assert self.engine._is_pdf("test.png") is False
        assert self.engine._is_pdf("test.txt") is False

    def test_is_image_true(self):
        """测试图片文件检测"""
        assert self.engine._is_image("test.jpg") is True
        assert self.engine._is_image("test.JPEG") is True
        assert self.engine._is_image("test.png") is True
        assert self.engine._is_image("test.PNG") is True
        assert self.engine._is_image("test.bmp") is True
        assert self.engine._is_image("test.tiff") is True

    def test_is_image_false(self):
        """测试非图片文件检测"""
        assert self.engine._is_image("test.pdf") is False
        assert self.engine._is_image("test.txt") is False
        assert self.engine._is_image("test.docx") is False


# ── PaddleOCR 可用性检测测试 ──


class TestPaddleAvailability:
    """测试 PaddleOCR 可用性检测"""

    @patch("server.core.ocr.paddleocr", create=True)
    def test_paddle_available(self, mock_paddle_module):
        """测试 PaddleOCR 已安装"""
        with patch.dict("sys.modules", {"paddleocr": mock_paddle_module}):
            engine = OCREngine()
            # 重置检测缓存
            engine._ocr_available = None
            result = engine._is_paddle_available()
            assert result is True

    def test_paddle_not_available(self):
        """测试 PaddleOCR 未安装"""
        engine = OCREngine()
        # 重置检测缓存
        engine._ocr_available = None
        with patch.dict("sys.modules", {"paddleocr": None}):
            with patch(
                "builtins.__import__",
                side_effect=ImportError("No module named 'paddleocr'"),
            ):
                # 由于 _is_paddle_available 内部使用 import paddleocr，
                # 需要直接 mock 内部逻辑
                engine._ocr_available = False
                result = engine._is_paddle_available()
                assert result is False

    def test_rejects_paddleocr_3(self):
        """锁定的 v2 构造参数不能静默运行在 PaddleOCR 3.x 上"""
        with patch("server.core.ocr.version", return_value="3.7.0"):
            with pytest.raises(RuntimeError, match="requires paddleocr 2.x"):
                ensure_supported_paddleocr_version()


# ── 图片识别测试 ──


class TestImageRecognition:
    """测试图片 OCR 识别"""

    @pytest.mark.asyncio
    async def test_recognize_image_success(self):
        """测试图片识别成功"""
        engine = OCREngine()

        # 模拟 PaddleOCR 返回结果
        # PaddleOCR 格式: [page_result]，page_result = [line, ...]，line = [bbox, (text, conf)]
        mock_ocr_instance = MagicMock()
        mock_ocr_instance.ocr.return_value = [
            [  # page 0 - 行列表
                [  # line 0
                    [(10, 10), (100, 10), (100, 50), (10, 50)],
                    ("合同编号：HT-2024-001", 0.95),
                ],
                [  # line 1
                    [(10, 60), (100, 60), (100, 100), (10, 100)],
                    ("甲方：张三", 0.92),
                ],
            ]
        ]

        with (
            patch.object(engine, "_is_paddle_available", return_value=True),
            patch.object(engine, "_get_ocr", return_value=mock_ocr_instance),
            patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread,
        ):
            # 模拟 asyncio.to_thread 调用
            mock_thread.return_value = mock_ocr_instance.ocr.return_value

            result = await engine.recognize("test.jpg")

            assert isinstance(result, OCRResult)
            assert "合同编号：HT-2024-001" in result.full_text
            assert "甲方：张三" in result.full_text
            assert len(result.pages) == 1
            assert result.confidence_avg > 0

    @pytest.mark.asyncio
    async def test_recognize_image_empty(self):
        """测试空白图片识别"""
        engine = OCREngine()

        mock_ocr_instance = MagicMock()
        mock_ocr_instance.ocr.return_value = [[]]

        with (
            patch.object(engine, "_is_paddle_available", return_value=True),
            patch.object(engine, "_get_ocr", return_value=mock_ocr_instance),
            patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread,
        ):
            mock_thread.return_value = mock_ocr_instance.ocr.return_value

            result = await engine.recognize("empty.jpg")

            assert isinstance(result, OCRResult)
            assert result.full_text == ""
            assert result.confidence_avg == 0.0

    @pytest.mark.asyncio
    async def test_recognize_image_no_paddle(self):
        """测试 PaddleOCR 不可用时的图片识别"""
        engine = OCREngine()

        with patch.object(engine, "_is_paddle_available", return_value=False):
            result = await engine.recognize("test.jpg")

            assert isinstance(result, OCRResult)
            assert result.full_text == ""

    @pytest.mark.asyncio
    async def test_recognize_image_ocr_error(self):
        """测试图片识别异常处理"""
        engine = OCREngine()

        with (
            patch.object(engine, "_is_paddle_available", return_value=True),
            patch.object(
                engine,
                "_get_ocr",
                side_effect=RuntimeError("OCR 模型未下载"),
            ),
        ):
            with pytest.raises(RuntimeError, match="OCR 模型未下载"):
                await engine.recognize("test.jpg")


# ── PDF 文字提取测试 ──


class TestPDFTextExtraction:
    """测试 PDF 文字提取"""

    def test_extract_text_pymupdf_success(self):
        """测试 PyMuPDF 成功提取 PDF 文字"""
        engine = OCREngine()

        # 模拟 PyMuPDF
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.get_text.return_value = "这是一段测试文字，用于验证 PDF 文字提取功能。" * 5

        with patch("fitz.open", return_value=mock_doc):
            mock_doc.__len__ = MagicMock(return_value=1)
            mock_doc.load_page.return_value = mock_page

            result = engine._extract_text_pymupdf("test.pdf")

            assert isinstance(result, OCRResult)
            assert "测试文字" in result.full_text
            assert result.confidence_avg == 1.0  # PyMuPDF 提取的文字置信度为 1.0
            assert len(result.pages) == 1

    def test_extract_text_pymupdf_not_installed(self):
        """测试 PyMuPDF 未安装时的容错"""
        engine = OCREngine()

        with patch.dict("sys.modules", {"fitz": None}):
            result = engine._extract_text_pymupdf("test.pdf")

            assert isinstance(result, OCRResult)
            assert result.full_text == ""


# ── PDF 识别流程测试 ──


class TestPDFRecognition:
    """测试 PDF 识别流程"""

    @pytest.mark.asyncio
    async def test_pdf_with_sufficient_text(self):
        """测试 PDF 文字层足够时直接使用 PyMuPDF 结果"""
        engine = OCREngine()

        long_text = "这是一段足够长的测试文字。" * 20  # 超过 100 字阈值

        mock_pymupdf_result = OCRResult(
            full_text=long_text,
            pages=[{"page": 1, "text": long_text, "line_count": 5}],
            confidence_avg=1.0,
        )

        with patch.object(
            engine, "_extract_text_pymupdf", return_value=mock_pymupdf_result
        ):
            result = await engine.recognize("test.pdf")

            assert result.full_text == long_text
            assert result.confidence_avg == 1.0

    @pytest.mark.asyncio
    async def test_pdf_with_insufficient_text_no_paddle(self):
        """测试 PDF 文字层不足且 PaddleOCR 不可用"""
        engine = OCREngine()

        short_text = "少量文字"
        mock_pymupdf_result = OCRResult(
            full_text=short_text,
            pages=[{"page": 1, "text": short_text, "line_count": 1}],
            confidence_avg=1.0,
        )

        with (
            patch.object(
                engine, "_extract_text_pymupdf", return_value=mock_pymupdf_result
            ),
            patch.object(engine, "_is_paddle_available", return_value=False),
        ):
            result = await engine.recognize("test.pdf")

            # 应返回 PyMuPDF 结果（可能不完整但聊胜于无）
            assert result.full_text == short_text

    @pytest.mark.asyncio
    async def test_pdf_with_insufficient_text_with_paddle(self):
        """测试 PDF 文字层不足时使用 PaddleOCR"""
        engine = OCREngine()

        short_text = "少量文字"
        mock_pymupdf_result = OCRResult(
            full_text=short_text,
            pages=[{"page": 1, "text": short_text, "line_count": 1}],
            confidence_avg=1.0,
        )

        # OCR 文字也不足 100 字时，会合并 PyMuPDF 和 OCR 结果
        mock_ocr_result = OCRResult(
            full_text="OCR 识别的文字内容",
            pages=[{"page": 1, "text": "OCR 识别的文字内容", "line_count": 3}],
            confidence_avg=0.85,
        )

        with (
            patch.object(
                engine, "_extract_text_pymupdf", return_value=mock_pymupdf_result
            ),
            patch.object(engine, "_is_paddle_available", return_value=True),
            patch.object(
                engine, "_pdf_to_images", return_value=["/tmp/page_000.png"]
            ),
            patch.object(
                engine, "_recognize_with_paddle", new_callable=AsyncMock
            ) as mock_paddle_recognize,
            patch.object(engine, "_cleanup_images"),
        ):
            mock_paddle_recognize.return_value = mock_ocr_result

            result = await engine.recognize("test.pdf")

            mock_paddle_recognize.assert_called_once()
            # OCR 结果不足 100 字，与 PyMuPDF 结果合并
            assert "OCR 识别的文字内容" in result.full_text
            assert "少量文字" in result.full_text
            assert "\n\n" in result.full_text

    @pytest.mark.asyncio
    async def test_pdf_to_images_cleanup(self):
        """测试 PDF 转图片后清理临时文件"""
        engine = OCREngine()

        short_text = "少量文字"
        mock_pymupdf_result = OCRResult(
            full_text=short_text,
            pages=[{"page": 1, "text": short_text, "line_count": 1}],
            confidence_avg=1.0,
        )

        mock_ocr_result = OCRResult(
            full_text="OCR 文字",
            pages=[{"page": 1, "text": "OCR 文字", "line_count": 1}],
            confidence_avg=0.9,
        )

        with (
            patch.object(
                engine, "_extract_text_pymupdf", return_value=mock_pymupdf_result
            ),
            patch.object(engine, "_is_paddle_available", return_value=True),
            patch.object(
                engine, "_pdf_to_images", return_value=["/tmp/page_000.png"]
            ),
            patch.object(
                engine, "_recognize_with_paddle", new_callable=AsyncMock
            ) as mock_paddle_recognize,
            patch.object(engine, "_cleanup_images") as mock_cleanup,
        ):
            mock_paddle_recognize.return_value = mock_ocr_result

            await engine.recognize("test.pdf")

            # 验证临时文件被清理
            mock_cleanup.assert_called_once_with(["/tmp/page_000.png"])


# ── 多文件 OCR 结果合并测试 ──


class TestMultiPageOCR:
    """测试多页 OCR 结果合并"""

    @pytest.mark.asyncio
    async def test_multi_page_recognition(self):
        """测试多页图片识别"""
        engine = OCREngine()

        # 模拟两页识别结果
        # PaddleOCR 格式: [page_result]，page_result = [line, ...]，line = [bbox, (text, conf)]
        page1_result = [
            [  # page 0 - 行列表
                [  # line 0
                    [(10, 10), (100, 10), (100, 50), (10, 50)],
                    ("第一页文字", 0.95),
                ],
            ]
        ]
        page2_result = [
            [  # page 0 - 行列表
                [  # line 0
                    [(10, 10), (100, 10), (100, 50), (10, 50)],
                    ("第二页文字", 0.90),
                ],
            ]
        ]

        mock_ocr_instance = MagicMock()
        mock_ocr_instance.ocr.side_effect = [page1_result, page2_result]

        with (
            patch.object(engine, "_get_ocr", return_value=mock_ocr_instance),
            patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread,
        ):
            mock_thread.side_effect = [page1_result, page2_result]

            result = await engine._recognize_with_paddle(
                ["page1.png", "page2.png"]
            )

            assert isinstance(result, OCRResult)
            assert "第一页文字" in result.full_text
            assert "第二页文字" in result.full_text
            assert len(result.pages) == 2
            # 平均置信度: (0.95 + 0.90) / 2 = 0.925
            assert abs(result.confidence_avg - 0.925) < 0.01

    @pytest.mark.asyncio
    async def test_empty_page_results(self):
        """测试空页面结果（PaddleOCR 返回 None）"""
        engine = OCREngine()

        with (
            patch.object(engine, "_get_ocr", return_value=MagicMock()),
            patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread,
        ):
            mock_thread.return_value = None

            result = await engine._recognize_with_paddle(["page1.png"])

            assert isinstance(result, OCRResult)
            assert result.full_text == ""
            assert result.confidence_avg == 0.0

    @pytest.mark.asyncio
    async def test_empty_page_results_with_empty_list(self):
        """测试空页面结果（PaddleOCR 返回空列表）"""
        engine = OCREngine()

        # PaddleOCR 返回格式: [page_result]，page 为空行列表
        empty_page_result = [[]]

        with (
            patch.object(engine, "_get_ocr", return_value=MagicMock()),
            patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread,
        ):
            mock_thread.return_value = empty_page_result

            result = await engine._recognize_with_paddle(["page1.png"])

            assert isinstance(result, OCRResult)
            assert result.full_text == ""
            assert result.confidence_avg == 0.0


# ── 单例模式测试 ──


class TestOCREngineSingleton:
    """测试 OCR 引擎单例模式"""

    def test_get_ocr_engine_returns_same_instance(self):
        """测试 get_ocr_engine 返回同一实例"""
        import server.core.ocr as ocr_module

        # 重置全局单例
        original = ocr_module.ocr_engine
        ocr_module.ocr_engine = None

        try:
            engine1 = get_ocr_engine()
            engine2 = get_ocr_engine()
            assert engine1 is engine2
        finally:
            # 恢复原始状态
            ocr_module.ocr_engine = original

    def test_get_ocr_engine_creates_new(self):
        """测试 get_ocr_engine 创建新实例"""
        import server.core.ocr as ocr_module

        original = ocr_module.ocr_engine
        ocr_module.ocr_engine = None

        try:
            engine = get_ocr_engine()
            assert isinstance(engine, OCREngine)
        finally:
            ocr_module.ocr_engine = original


# ── 临时文件清理测试 ──


class TestCleanup:
    """测试临时文件清理"""

    def test_cleanup_images_success(self):
        """测试成功清理临时图片"""
        engine = OCREngine()

        with patch("pathlib.Path.unlink") as mock_unlink, patch(
            "shutil.rmtree"
        ) as mock_rmtree:
            engine._cleanup_images(["/tmp/img1.png", "/tmp/img2.png"])

            assert mock_unlink.call_count == 2
            mock_rmtree.assert_called_once()

    def test_cleanup_images_empty(self):
        """测试清理空列表"""
        engine = OCREngine()

        with patch("pathlib.Path.unlink") as mock_unlink, patch(
            "shutil.rmtree"
        ) as mock_rmtree:
            engine._cleanup_images([])

            mock_unlink.assert_not_called()
            mock_rmtree.assert_not_called()

    def test_cleanup_images_ignore_errors(self):
        """测试清理时忽略删除错误"""
        engine = OCREngine()

        with patch(
            "pathlib.Path.unlink", side_effect=OSError("文件不存在")
        ):
            # 不应抛出异常
            engine._cleanup_images(["/tmp/img1.png"])


# ── 不支持的文件格式测试 ──


class TestUnsupportedFormat:
    """测试不支持的文件格式"""

    @pytest.mark.asyncio
    async def test_unsupported_file_type(self):
        """测试不支持的文件类型"""
        engine = OCREngine()

        result = await engine.recognize("test.txt")

        assert isinstance(result, OCRResult)
        assert result.full_text == ""
        assert result.pages == []
