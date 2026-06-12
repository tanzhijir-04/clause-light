"""OCR 封装 — PaddleOCR + PyMuPDF"""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from server.config import settings

logger = logging.getLogger(__name__)


@dataclass
class OCRResult:
    """OCR 识别结果"""

    full_text: str = ""
    pages: list[dict] = field(default_factory=list)
    confidence_avg: float = 0.0


class OCREngine:
    """PaddleOCR 封装，延迟加载模型"""

    def __init__(self) -> None:
        self._ocr = None

    def _get_ocr(self):
        """延迟导入并初始化 PaddleOCR"""
        if self._ocr is None:
            try:
                from paddleocr import PaddleOCR

                self._ocr = PaddleOCR(
                    use_angle_cls=True,
                    lang="ch",
                    use_gpu=settings.OCR_USE_GPU,
                    show_log=False,
                )
                logger.info("PaddleOCR 初始化完成 (gpu=%s)", settings.OCR_USE_GPU)
            except ImportError:
                logger.error("PaddleOCR 未安装，请运行: pip install paddleocr paddlepaddle")
                raise
        return self._ocr

    def _pdf_to_images(self, pdf_path: str) -> list[str]:
        """用 PyMuPDF 将 PDF 每页转为图片"""
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

    def _is_pdf(self, file_path: str) -> bool:
        return file_path.lower().endswith(".pdf")

    def _is_image(self, file_path: str) -> bool:
        return file_path.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".tiff"))

    async def recognize(self, file_path: str) -> OCRResult:
        """
        识别文件中的文字。

        - 图片文件：直接识别
        - PDF 文件：逐页提取图片再识别
        """
        import asyncio

        ocr = self._get_ocr()

        # 确定要处理的文件列表
        image_paths: list[str] = []
        cleanup_paths: list[str] = []

        if self._is_pdf(file_path):
            image_paths = self._pdf_to_images(file_path)
            cleanup_paths = image_paths
        elif self._is_image(file_path):
            image_paths = [file_path]
        else:
            logger.warning("不支持的文件格式: %s", file_path)
            return OCRResult()

        all_texts: list[str] = []
        all_confidences: list[float] = []
        pages_data: list[dict] = []

        try:
            for idx, img_path in enumerate(image_paths):
                # PaddleOCR 是同步的，在线程池中运行
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

        finally:
            # 清理临时文件
            import shutil

            for p in cleanup_paths:
                try:
                    Path(p).unlink(missing_ok=True)
                except OSError:
                    pass
            if cleanup_paths:
                temp_dir = str(Path(cleanup_paths[0]).parent)
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except OSError:
                    pass

        full_text = "\n\n".join(t for t in all_texts if t.strip())
        avg_conf = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0

        logger.info(
            "OCR 识别完成: pages=%d text_len=%d avg_conf=%.2f",
            len(image_paths),
            len(full_text),
            avg_conf,
        )

        return OCRResult(
            full_text=full_text,
            pages=pages_data,
            confidence_avg=round(avg_conf, 3),
        )


# 全局单例
ocr_engine: OCREngine | None = None


def get_ocr_engine() -> OCREngine:
    """获取或创建 OCR 引擎单例"""
    global ocr_engine
    if ocr_engine is None:
        ocr_engine = OCREngine()
    return ocr_engine
