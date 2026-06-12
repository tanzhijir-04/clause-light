# OCR 模型管理 — CC 开发提示词

## 背景

PaddleOCR 在首次调用时会自动从百度服务器下载模型文件（检测模型 + 识别模型 + 方向分类模型，总计约 100-200MB），存储在 `~/.paddleocr/` 目录下。

**问题**：
- 国内用户访问百度模型服务器可能不稳定
- 离线/断网环境无法使用 OCR
- 用户无法感知模型是否已下载、下载进度、是否可用
- 没有 UI 让用户管理模型

**目标**：在软件管理面板中提供模型管理页面，让用户可以看到模型状态、手动触发下载、配置模型路径。

---

## 需要做的事

### 1. 新增配置项（`server/config.py`）

```python
# ── OCR 模型 ──
OCR_MODEL_DIR: str = "data/models/paddleocr"  # 模型本地存储路径
OCR_AUTO_DOWNLOAD: bool = True                  # 首次使用时是否自动下载
```

- 默认存到 `data/models/paddleocr/`（项目目录内），而不是 `~/.paddleocr/`
- `OCR_AUTO_DOWNLOAD` 设为 False 时，不会自动下载，只在用户手动触发时下载
- 在 `.env` 文件和管理面板的设置页都可配置

### 2. 新增模型管理模块（`server/core/model_manager.py`）

```python
"""OCR 模型管理 — 下载、状态检查、路径管理"""

from __future__ import annotations

import json
import logging
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncGenerator

import httpx

from server.config import settings

logger = logging.getLogger(__name__)

# PaddleOCR 模型文件清单
# 格式：(模型类型, 文件名, 大小估算bytes, 下载URL)
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

# 国内镜像（当百度源不可用时使用）
MIRROR_URLS: list[str] = [
    "https://paddleocr.bj.bcebos.com",
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
            installed = model_path.exists() and any(model_path.iterdir()) if model_path.exists() else False

            installed_size = 0
            if installed and model_path.exists():
                for f in model_path.rglob("*"):
                    if f.is_file():
                        installed_size += f.stat().st_size

            total_size = sum(f["size"] for f in model["files"])

            statuses.append(ModelStatus(
                type=model["type"],
                name=model["name"],
                description=model["description"],
                installed=installed,
                total_size=total_size,
                installed_size=installed_size,
                path=str(model_path),
            ))
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
            yield {"status": "error", "model": model_type, "message": f"未知模型类型: {model_type}"}
            return

        model_name = model_info["name"]
        model_path = self._model_path(model_name)
        model_path.mkdir(parents=True, exist_ok=True)

        url = model_info["url"]
        tar_path = model_path / f"{model_name}.tar"

        yield {"status": "downloading", "model": model_type, "progress": 0, "message": f"开始下载 {model_info['description']}"}

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
            yield {"status": "extracting", "model": model_type, "progress": 0.99, "message": "解压模型文件..."}
            import tarfile
            with tarfile.open(tar_path, "r:*") as tar:
                tar.extractall(path=model_path)

            # 清理 tar 文件
            tar_path.unlink(missing_ok=True)

            yield {"status": "done", "model": model_type, "message": f"{model_info['description']} 下载完成"}

        except Exception as e:
            logger.error("模型下载失败: %s - %s", model_type, e)
            yield {"status": "error", "model": model_type, "message": f"下载失败: {str(e)}"}
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

    def set_model_dir(self, new_dir: str) -> dict:
        """更新模型存储路径（需重启生效）"""
        # 不在这里修改 settings，只返回提示
        return {
            "success": True,
            "message": f"模型路径将在重启后生效，请在 .env 中设置 OCR_MODEL_DIR={new_dir}",
            "current_path": self.model_dir,
            "new_path": new_dir,
        }


# 全局单例
_model_manager: OCRModelManager | None = None


def get_model_manager() -> OCRModelManager:
    global _model_manager
    if _model_manager is None:
        _model_manager = OCRModelManager()
    return _model_manager
```

### 3. 新增 API 接口（`server/api/models.py`）

```python
"""模型管理 API"""

from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from server.core.model_manager import get_model_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/models", tags=["模型管理"])


@router.get("/status")
async def get_model_status():
    """获取所有模型的状态"""
    manager = get_model_manager()
    return manager.get_overall_status()


@router.post("/download/{model_type}")
async def download_model(model_type: str):
    """下载指定模型（SSE 流式返回进度）"""
    from fastapi.responses import StreamingResponse
    import json

    manager = get_model_manager()

    async def event_stream():
        async for event in manager.download_model(model_type):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/download-all")
async def download_all_models():
    """下载所有模型"""
    from fastapi.responses import StreamingResponse
    import json

    manager = get_model_manager()

    async def event_stream():
        async for event in manager.download_all():
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.delete("/{model_type}")
async def delete_model(model_type: str):
    """删除指定模型"""
    manager = get_model_manager()
    result = manager.delete_model(model_type)
    return JSONResponse(content=result)
```

在 `server/main.py` 中注册这个 router：
```python
from server.api.models import router as models_router
app.include_router(models_router)
```

### 4. 修改 `server/core/ocr.py`

在初始化 PaddleOCR 时指定模型路径：

```python
# 修改 _get_ocr 方法
def _get_ocr(self):
    if self._ocr is None:
        try:
            from paddleocr import PaddleOCR
            from server.config import settings

            # 使用配置的模型目录
            det_model_dir = str(Path(settings.OCR_MODEL_DIR) / "ch_PP-OCRv4_det_infer")
            rec_model_dir = str(Path(settings.OCR_MODEL_DIR) / "ch_PP-OCRv4_rec_infer")
            cls_model_dir = str(Path(settings.OCR_MODEL_DIR) / "ch_ppocr_mobile_v2.0_cls_infer")

            # 检查模型是否已下载
            from server.core.model_manager import get_model_manager
            manager = get_model_manager()
            overall = manager.get_overall_status()

            if not overall["all_installed"]:
                if settings.OCR_AUTO_DOWNLOAD:
                    logger.info("OCR 模型未就绪，自动下载中...")
                    # 同步下载（在初始化阶段）
                    import asyncio
                    asyncio.get_event_loop().run_until_complete(manager.download_all())
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
            logger.info("PaddleOCR 初始化完成 (gpu=%s, model_dir=%s)", settings.OCR_USE_GPU, settings.OCR_MODEL_DIR)
        except ImportError:
            logger.error("PaddleOCR 未安装，请运行: pip install paddleocr paddlepaddle")
            raise
    return self._ocr
```

### 5. 新增管理面板页面（`server/static/pages/models.js`）

在管理面板中新增"模型管理"页面，展示：

**页面布局**：

```
┌─────────────────────────────────────────────────────┐
│  模型管理                                            │
├─────────────────────────────────────────────────────┤
│                                                     │
│  OCR 模型状态                                        │
│  ┌─────────────────────────────────────────────┐    │
│  │ 模型          状态    大小      操作          │    │
│  │─────────────────────────────────────────────│    │
│  │ 文字检测      ✓已安装  4.8MB   [删除]        │    │
│  │ 文字识别      ✗未安装  10.2MB  [下载]        │    │
│  │ 方向分类      ✗未安装  1.4MB   [下载]        │    │
│  └─────────────────────────────────────────────┘    │
│                                                     │
│  [一键下载全部模型]  共需下载: ~15.0 MB               │
│                                                     │
│  模型存储路径: data/models/paddleocr                  │
│  [修改路径]                                          │
│                                                     │
│  ─────────────────────────────────────────────────  │
│                                                     │
│  LLM 配置状态（已有，保持不变）                        │
│  DeepSeek: ✓已配置 / ✗未配置                         │
│  OpenAI:   ✓已配置 / ✗未配置                         │
│  Ollama:   ✓运行中 / ✗未运行                         │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**前端交互逻辑**：

1. 页面加载时调用 `GET /api/models/status` 获取所有模型状态
2. 每个模型显示名称、状态（已安装/未安装）、大小
3. 点击"下载"按钮 → 调用 `POST /api/models/download/{type}`，用 EventSource 接收进度
4. 下载过程中显示进度条和百分比
5. 下载完成自动刷新状态
6. "一键下载全部" → 调用 `POST /api/models/download-all`
7. "删除"按钮 → 二次确认后调用 `DELETE /api/models/{type}`
8. 模型路径旁有"修改路径"按钮，点击后弹出输入框，提示需重启生效

**进度条实现**：

```javascript
// 用 EventSource 接收 SSE 流
async function downloadModel(modelType, progressBarId) {
    const response = await fetch(`/api/models/download/${modelType}`, { method: 'POST' });
    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const text = decoder.decode(value);
        const lines = text.split('\n').filter(l => l.startsWith('data: '));
        for (const line of lines) {
            const event = JSON.parse(line.slice(6));
            updateProgress(progressBarId, event);
        }
    }
}
```

### 6. 路由注册（`server/static/js/router.js`）

在路由配置中新增：
```javascript
{ path: '/models', page: 'models', title: '模型管理', icon: 'box' }
```

在侧边栏导航中加入"模型管理"入口（使用 lucide 的 `box` 或 `hard-drive` 图标）。

### 7. 启动时检查（`server/main.py`）

在 FastAPI 启动事件中检查模型状态，如果模型未安装且 `OCR_AUTO_DOWNLOAD=False`，在日志中输出提示：

```python
@app.on_event("startup")
async def check_model_status():
    from server.core.model_manager import get_model_manager
    manager = get_model_manager()
    status = manager.get_overall_status()
    if not status["all_installed"]:
        missing = [m["name"] for m in status["models"] if not m["installed"]]
        logger.warning(
            "OCR 模型未完整安装，缺失: %s。请在管理面板的模型管理页面下载。",
            ", ".join(missing),
        )
```

---

## 需要改动的文件清单

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `server/config.py` | 修改 | 新增 `OCR_MODEL_DIR` 和 `OCR_AUTO_DOWNLOAD` 配置项 |
| `server/core/model_manager.py` | **新增** | 模型管理核心模块 |
| `server/api/models.py` | **新增** | 模型管理 API 接口 |
| `server/core/ocr.py` | 修改 | `_get_ocr()` 方法改为从配置路径加载模型 |
| `server/main.py` | 修改 | 注册 models router + 启动检查 |
| `server/static/pages/models.js` | **新增** | 模型管理页面前端 |
| `server/static/js/router.js` | 修改 | 注册模型管理页面路由 |
| `server/static/css/pages.css` | 修改 | 新增模型管理页面样式（进度条等） |

## 注意事项

- 下载依赖 `httpx`，需确认 `requirements.txt` 中已包含（如果没有则添加）
- 模型下载是耗时操作，必须用 SSE 流式返回进度，不能用普通 REST 响应
- 删除模型前必须二次确认
- 模型路径修改后需重启才能生效，UI 上要有明确提示
- 所有新代码使用 type hints，异常不能裸 except
- Commit message 用中文
