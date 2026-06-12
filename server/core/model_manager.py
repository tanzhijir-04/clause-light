"""OCR 模型管理 — 下载、状态检查、路径管理"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncGenerator

import httpx

from server.config import settings

logger = logging.getLogger(__name__)

# PaddleOCR 模型文件清单
MODELS_MANIFEST: list[dict] = [
    {
        "type": "det",
        "name": "ch_PP-OCRv4_det_infer",
        "description": "中文文字检测模型",
        "files": [
            {"name": "inference.pdiparams", "size": 4800000},
            {"name": "inference.pdiparams.info", "size": 100},
            {"name": "inference.pdmodel", "size": 3200000},
        ],
        "url": "https://paddleocr.bj.bcebos.com/PP-OCRv4/chinese/ch_PP-OCRv4_det_infer.tar",
    },
    {
        "type": "rec",
        "name": "ch_PP-OCRv4_rec_infer",
        "description": "中文文字识别模型",
        "files": [
            {"name": "inference.pdiparams", "size": 10000000},
            {"name": "inference.pdiparams.info", "size": 100},
            {"name": "inference.pdmodel", "size": 3200000},
        ],
        "url": "https://paddleocr.bj.bcebos.com/PP-OCRv4/chinese/ch_PP-OCRv4_rec_infer.tar",
    },
    {
        "type": "cls",
        "name": "ch_ppocr_mobile_v2.0_cls_infer",
        "description": "文字方向分类模型",
        "files": [
            {"name": "inference.pdiparams", "size": 1400000},
            {"name": "inference.pdiparams.info", "size": 100},
            {"name": "inference.pdmodel", "size": 1200000},
        ],
        "url": "https://paddleocr.bj.bcebos.com/dygraph_v2.0/ch/ch_ppocr_mobile_v2.0_cls_infer.tar",
    },
]


@dataclass
class ModelStatus:
    """单个模型的状态"""

    type: str = ""
    name: str = ""
    description: str = ""
    installed: bool = False
    total_size: int = 0
    installed_size: int = 0
    path: str = ""


@dataclass
class OCRModelManager:
    """OCR 模型管理器"""

    model_dir: str = ""

    def __post_init__(self) -> None:
        if not self.model_dir:
            self.model_dir = settings.OCR_MODEL_DIR

    def _model_path(self, model_name: str) -> Path:
        return Path(self.model_dir) / model_name

    def get_all_status(self) -> list[ModelStatus]:
        """获取所有模型的安装状态"""
        statuses: list[ModelStatus] = []
        for model in MODELS_MANIFEST:
            model_path = self._model_path(model["name"])
            installed = (
                model_path.exists() and any(model_path.iterdir())
                if model_path.exists()
                else False
            )

            installed_size = 0
            if installed and model_path.exists():
                for f in model_path.rglob("*"):
                    if f.is_file():
                        installed_size += f.stat().st_size

            total_size = sum(f["size"] for f in model["files"])

            statuses.append(
                ModelStatus(
                    type=model["type"],
                    name=model["name"],
                    description=model["description"],
                    installed=installed,
                    total_size=total_size,
                    installed_size=installed_size,
                    path=str(model_path),
                )
            )
        return statuses

    def get_overall_status(self) -> dict:
        """获取总体状态"""
        statuses = self.get_all_status()
        all_installed = all(s.installed for s in statuses)
        total_size = sum(s.total_size for s in statuses)
        installed_size = sum(s.installed_size for s in statuses)

        return {
            "all_installed": all_installed,
            "models": [
                {
                    "type": s.type,
                    "name": s.name,
                    "description": s.description,
                    "installed": s.installed,
                    "total_size_mb": round(s.total_size / 1024 / 1024, 1),
                    "installed_size_mb": round(s.installed_size / 1024 / 1024, 1),
                    "path": s.path,
                }
                for s in statuses
            ],
            "total_size_mb": round(total_size / 1024 / 1024, 1),
            "installed_size_mb": round(installed_size / 1024 / 1024, 1),
            "model_dir": self.model_dir,
        }

    async def download_model(
        self,
        model_type: str,
    ) -> AsyncGenerator[dict, None]:
        """
        下载指定模型，yield 进度事件。

        yield 格式：
        {"status": "downloading", "model": "xxx", "progress": 0.5, "message": "下载中 50%"}
        {"status": "done", "model": "xxx", "message": "下载完成"}
        {"status": "error", "model": "xxx", "message": "下载失败: xxx"}
        """
        model_info = None
        for m in MODELS_MANIFEST:
            if m["type"] == model_type:
                model_info = m
                break

        if not model_info:
            yield {
                "status": "error",
                "model": model_type,
                "message": f"未知模型类型: {model_type}",
            }
            return

        model_name = model_info["name"]
        model_path = self._model_path(model_name)
        model_path.mkdir(parents=True, exist_ok=True)

        url = model_info["url"]
        tar_path = model_path / f"{model_name}.tar"

        yield {
            "status": "downloading",
            "model": model_type,
            "progress": 0,
            "message": f"开始下载 {model_info['description']}",
        }

        try:
            total_size = sum(f["size"] for f in model_info["files"])
            downloaded = 0

            async with httpx.AsyncClient(timeout=300.0) as client:
                async with client.stream("GET", url) as response:
                    response.raise_for_status()
                    with open(tar_path, "wb") as f:
                        async for chunk in response.aiter_bytes(chunk_size=8192):
                            f.write(chunk)
                            downloaded += len(chunk)
                            progress = downloaded / total_size if total_size > 0 else 0
                            yield {
                                "status": "downloading",
                                "model": model_type,
                                "progress": round(progress, 2),
                                "message": f"下载中 {int(progress * 100)}%",
                            }

            # 解压 tar 文件
            yield {
                "status": "extracting",
                "model": model_type,
                "progress": 0.99,
                "message": "解压模型文件...",
            }
            import tarfile

            with tarfile.open(tar_path, "r:*") as tar:
                tar.extractall(path=model_path)

            # 清理 tar 文件
            tar_path.unlink(missing_ok=True)

            yield {
                "status": "done",
                "model": model_type,
                "message": f"{model_info['description']} 下载完成",
            }

        except Exception as e:
            logger.error("模型下载失败: %s - %s", model_type, e)
            yield {
                "status": "error",
                "model": model_type,
                "message": f"下载失败: {str(e)}",
            }
            # 清理不完整的文件
            if tar_path.exists():
                tar_path.unlink(missing_ok=True)

    async def download_all(self) -> AsyncGenerator[dict, None]:
        """下载所有模型"""
        for model in MODELS_MANIFEST:
            async for event in self.download_model(model["type"]):
                yield event

    def delete_model(self, model_type: str) -> dict:
        """删除指定模型"""
        model_info = None
        for m in MODELS_MANIFEST:
            if m["type"] == model_type:
                model_info = m
                break

        if not model_info:
            return {"success": False, "message": f"未知模型类型: {model_type}"}

        model_path = self._model_path(model_info["name"])
        if model_path.exists():
            shutil.rmtree(model_path)
            return {"success": True, "message": f"{model_info['description']} 已删除"}

        return {"success": False, "message": "模型未安装"}


# 全局单例
_model_manager: OCRModelManager | None = None


def get_model_manager() -> OCRModelManager:
    global _model_manager
    if _model_manager is None:
        _model_manager = OCRModelManager()
    return _model_manager
