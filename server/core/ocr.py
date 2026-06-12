"""OCR 封装 — PyMuPDF 文字提取 + PaddleOCR 图片识别"""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from server.config import settings

logger = logging.getLogger(__name__)

# PyMuPDF 提取文字的最低阈值：低于此长度认为是纯图片 PDF，需要 OCR
_PYMUPDF_MIN_TEXT_LEN = 100


@dataclass
class OCRResult:
    """OCR 识别结果"""

    full_text: str = ""
    pages: list[dict] = field(default_factory=list)
    confidence_avg: float = 0.0


class OCREngine:
    """OCR 引擎 — PDF 优先 PyMuPDF 提取文字，不够再走 PaddleOCR；图片走 PaddleOCR"""

    def __init__(self) -> None:
        self._ocr = None
        self._ocr_available: bool | None = None  # None=未检测, True/False=已检测

    def _is_paddle_available(self) -> bool:
        """检测 PaddleOCR 是否可用（只检测一次）"""
        if self._ocr_available is None:
            try:
                import paddleocr  # noqa: F401
                self._ocr_available = True
            except ImportError:
                self._ocr_available = False
                logger.warning(
                    "PaddleOCR 未安装，图片 OCR 不可用。"
                    "请运行: pip install paddleocr paddlepaddle"
                )
        return self._ocr_available

    def _get_ocr(self):
        """延迟导入并初始化 PaddleOCR"""
        if self._ocr is None:
            from paddleocr import PaddleOCR

            # 构建模型路径
            model_dir = Path(settings.OCR_MODEL_DIR)
            det_model_dir = str(model_dir / "ch_PP-OCRv4_det_infer")
            rec_model_dir = str(model_dir / "ch_PP-OCRv4_rec_infer")
            cls_model_dir = str(model_dir / "ch_ppocr_mobile_v2.0_cls_infer")

            # 检查模型是否已下载
            from server.core.model_manager import get_model_manager

            manager = get_model_manager()
            overall = manager.get_overall_status()

            if not overall["all_installed"]:
                if settings.OCR_AUTO_DOWNLOAD:
                    logger.info("OCR 模型未就绪，自动下载中...")
                    import asyncio

                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        import concurrent.futures

                        with concurrent.futures.ThreadPoolExecutor() as pool:
                            loop.run_in_executor(
                                pool,
                                lambda: asyncio.run(manager.download_all()),
                            )
                    else:
                        loop.run_until_complete(manager.download_all())
                else:
                    raise RuntimeError(
                        "OCR 模型未下载。请在管理面板的模型管理页面手动下载，"
                        "或设置 OCR_AUTO_DOWNLOAD=True 让系统自动下载。"
                    )

            self._ocr = PaddleOCR(
                use_angle_cls=True,
                lang="ch",
                use_gpu=settings.OCR_USE_GPU,
                det_model_dir=det_model_dir,
                rec_model_dir=rec_model_dir,
                cls_model_dir=cls_model_dir,
                show_log=False,
            )
            logger.info(
                "PaddleOCR 初始化完成 (gpu=%s, model_dir=%s)",
                settings.OCR_USE_GPU,
                settings.OCR_MODEL_DIR,
            )
        return self._ocr

    # ── PyMuPDF 文字提取（PDF 专用，不需要 PaddleOCR） ──

    def _extract_text_pymupdf(self, pdf_path: str) -> OCRResult:
        """用 PyMuPDF 直接提取 PDF 中的文字层（无需 OCR）"""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            logger.error("PyMuPDF 未安装，请运行: pip install PyMuPDF")
            return OCRResult()

        doc = fitz.open(pdf_path)
        all_texts: list[str] = []
        pages_data: list[dict] = []

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text = page.get_text("text")
            all_texts.append(text)
            pages_data.append({
                "page": page_num + 1,
                "text": text,
                "line_count": len(text.splitlines()),
            })

        doc.close()

        full_text = "\n\n".join(t for t in all_texts if t.strip())
        logger.info(
            "PyMuPDF 文字提取完成: pages=%d text_len=%d",
            len(pages_data),
            len(full_text),
        )
        return OCRResult(
            full_text=full_text,
            pages=pages_data,
            confidence_avg=1.0,  # PyMuPDF 提取的是原始文字，置信度 1.0
        )

    def _pdf_to_images(self, pdf_path: str) -> list[str]:
        """用 PyMuPDF 将 PDF 每页转为图片（用于 PaddleOCR）"""
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(pdf_path)
            image_paths: list[str] = []
            temp_dir = tempfile.mkdtemp(prefix="clause_ocr_")

            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                # 渲染为图片（2x 分辨率提升 OCR 精度）
                mat = fitz.Matrix(2, 2)
                pix = page.get_pixmap(matrix=mat)
                img_path = str(Path(temp_dir) / f"page_{page_num:03d}.png")
                pix.save(img_path)
                image_paths.append(img_path)

            doc.close()
            return image_paths
        except ImportError:
            logger.error("PyMuPDF 未安装，请运行: pip install PyMuPDF")
            return []

    # ── PaddleOCR 识别（图片 + PDF 图片层） ──

    async def _recognize_with_paddle(self, image_paths: list[str]) -> OCRResult:
        """用 PaddleOCR 识别图片列表"""
        import asyncio

        ocr = self._get_ocr()
        all_texts: list[str] = []
        all_confidences: list[float] = []
        pages_data: list[dict] = []

        for idx, img_path in enumerate(image_paths):
            result = await asyncio.to_thread(ocr.ocr, img_path, cls=True)

            page_texts: list[str] = []
            page_confidences: list[float] = []

            if result and result[0]:
                for line in result[0]:
                    text = line[1][0]
                    confidence = line[1][1]
                    page_texts.append(text)
                    page_confidences.append(confidence)

            page_text = "\n".join(page_texts)
            all_texts.append(page_text)
            pages_data.append({
                "page": idx + 1,
                "text": page_text,
                "line_count": len(page_texts),
            })
            if page_confidences:
                all_confidences.extend(page_confidences)

        full_text = "\n\n".join(t for t in all_texts if t.strip())
        avg_conf = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0

        return OCRResult(
            full_text=full_text,
            pages=pages_data,
            confidence_avg=round(avg_conf, 3),
        )

    # ── 公开接口 ──

    def _is_pdf(self, file_path: str) -> bool:
        return file_path.lower().endswith(".pdf")

    def _is_image(self, file_path: str) -> bool:
        return file_path.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".tiff"))

    async def recognize(self, file_path: str) -> OCRResult:
        """
        识别文件中的文字。

        策略：
        - PDF 文件：先用 PyMuPDF 提取文字层 → 如果文字足够（>=100字），直接返回；
                     否则转图片再走 PaddleOCR（如果可用）。
        - 图片文件：直接走 PaddleOCR（如果可用）。
        - 如果 PaddleOCR 不可用，只能靠 PyMuPDF 提取的文字（图片文件会返回空）。
        """
        if self._is_pdf(file_path):
            # ── PDF：先尝试 PyMuPDF 文字提取 ──
            pymupdf_result = self._extract_text_pymupdf(file_path)
            if len(pymupdf_result.full_text.strip()) >= _PYMUPDF_MIN_TEXT_LEN:
                logger.info(
                    "PDF 文字层足够（%d 字），直接使用 PyMuPDF 结果",
                    len(pymupdf_result.full_text),
                )
                return pymupdf_result

            # 文字不够，尝试 PaddleOCR
            logger.info(
                "PDF 文字层不足（%d 字），尝试 PaddleOCR 图片识别",
                len(pymupdf_result.full_text),
            )
            if not self._is_paddle_available():
                # PaddleOCR 不可用，返回 PyMuPDF 结果（可能不完整但聊胜于无）
                logger.warning("PaddleOCR 不可用，返回 PyMuPDF 提取的部分文字")
                return pymupdf_result

            image_paths = self._pdf_to_images(file_path)
            if not image_paths:
                # 无法转图片，返回 PyMuPDF 结果
                return pymupdf_result

            try:
                ocr_result = await self._recognize_with_paddle(image_paths)
                # 如果 OCR 结果也不好，合并两者
                if len(ocr_result.full_text.strip()) < _PYMUPDF_MIN_TEXT_LEN and pymupdf_result.full_text.strip():
                    merged_text = pymupdf_result.full_text + "\n\n" + ocr_result.full_text
                    ocr_result.full_text = merged_text
                    ocr_result.confidence_avg = (pymupdf_result.confidence_avg + ocr_result.confidence_avg) / 2
                return ocr_result
            finally:
                self._cleanup_images(image_paths)

        elif self._is_image(file_path):
            # ── 图片：必须走 PaddleOCR ──
            if not self._is_paddle_available():
                logger.error("图片文件需要 PaddleOCR，但未安装")
                return OCRResult()
            return await self._recognize_with_paddle([file_path])

        else:
            logger.warning("不支持的文件格式: %s", file_path)
            return OCRResult()

    def _cleanup_images(self, image_paths: list[str]) -> None:
        """清理临时图片文件"""
        import shutil

        for p in image_paths:
            try:
                Path(p).unlink(missing_ok=True)
            except OSError:
                pass
        if image_paths:
            temp_dir = str(Path(image_paths[0]).parent)
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except OSError:
                pass


# 全局单例
ocr_engine: OCREngine | None = None


def get_ocr_engine() -> OCREngine:
    """获取或创建 OCR 引擎单例"""
    global ocr_engine
    if ocr_engine is None:
        ocr_engine = OCREngine()
    return ocr_engine
