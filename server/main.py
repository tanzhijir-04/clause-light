"""合同红绿灯 — FastAPI 主入口"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from server.config import settings

# ── 日志配置 ──

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── 生命周期 ──


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/关闭"""
    # 启动
    logger.info("合同红绿灯 启动中...")

    # 确保 data 目录存在
    os.makedirs("data", exist_ok=True)
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    # 初始化数据库
    from server.models.database import init_db

    await init_db()
    logger.info("数据库初始化完成")

    # 导入基础规则（如果知识库为空）
    await _init_default_rules()

    # 检查 OCR 模型状态
    from server.core.model_manager import get_model_manager

    manager = get_model_manager()
    status = manager.get_overall_status()
    if not status["all_installed"]:
        missing = [m["name"] for m in status["models"] if not m["installed"]]
        logger.warning(
            "OCR 模型未完整安装，缺失: %s。请在管理面板的模型管理页面下载。",
            ", ".join(missing),
        )

    logger.info("合同红绿灯 启动完成 ✅")
    yield

    # 关闭
    logger.info("合同红绿灯 已关闭")


async def _init_default_rules():
    """如果知识库为空，导入默认规则"""
    from sqlalchemy import func, select

    from server.models.database import KnowledgeRule, async_session_factory

    async with async_session_factory() as db:
        count_stmt = select(func.count()).select_from(KnowledgeRule)
        result = await db.execute(count_stmt)
        count = result.scalar() or 0

        if count == 0:
            logger.info("知识库为空，导入默认规则...")
            # 尝试从 shared/rules/ 导入
            rules_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "shared", "rules")
            if os.path.isdir(rules_dir):
                import json

                for filename in os.listdir(rules_dir):
                    if filename.endswith(".json"):
                        filepath = os.path.join(rules_dir, filename)
                        try:
                            with open(filepath, "r", encoding="utf-8") as f:
                                rules_data = json.load(f)
                            for rule in rules_data:
                                kr = KnowledgeRule(
                                    category=rule.get("category", "通用"),
                                    rule_text=rule["rule_text"],
                                    trigger_keywords=json.dumps(
                                        rule.get("trigger_keywords", []), ensure_ascii=False
                                    ),
                                    confidence=rule.get("confidence", 0.5),
                                    source=rule.get("source", "manual"),
                                )
                                db.add(kr)
                            logger.info("导入规则: %s (%d 条)", filename, len(rules_data))
                        except Exception as e:
                            logger.warning("导入规则失败 %s: %s", filename, e)

                await db.commit()


# ── 创建 App ──

app = FastAPI(
    title="合同红绿灯",
    version="1.0.0",
    description="合同红绿灯 — 智能合同风险审查工具",
    lifespan=lifespan,
)

# ── CORS ──

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 请求日志 ──


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """请求日志"""
    logger.debug("%s %s", request.method, request.url.path)
    response = await call_next(request)
    return response


# ── 注册路由 ──

from server.api.contracts import router as contracts_router
from server.api.knowledge import router as knowledge_router
from server.api.models import router as models_router
from server.api.sync import router as sync_router
from server.api.ws import router as ws_router

app.include_router(contracts_router)
app.include_router(knowledge_router)
app.include_router(models_router)
app.include_router(sync_router)
app.include_router(ws_router)


# ── 设备列表（临时 mock） ──


@app.get("/api/devices")
async def list_devices():
    """连接设备列表"""
    return [
        {
            "id": "1",
            "name": "iPhone 15 Pro",
            "type": "mobile",
            "status": "online",
            "lastSeen": "刚刚",
            "ip": "192.168.1.105",
        },
        {
            "id": "2",
            "name": "iPad Air",
            "type": "tablet",
            "status": "offline",
            "lastSeen": "2 小时前",
            "ip": "192.168.1.108",
        },
    ]


# ── LLM 配置接口 ──

LLM_CONFIG_FILE = os.path.join("data", "llm_config.json")


def _load_llm_config() -> dict:
    """从文件加载 LLM 配置"""
    import json

    default_config = {
        "remote": {
            "enabled": bool(settings.LLM_DEEPSEEK_API_KEY),
            "provider": "deepseek" if settings.LLM_DEEPSEEK_API_KEY else "openai",
            "baseUrl": "https://api.deepseek.com/v1",
            "apiKey": settings.LLM_DEEPSEEK_API_KEY or "",
            "models": {
                "classify": "deepseek-chat",
                "analyze": "deepseek-chat",
                "explain": "deepseek-chat",
            },
        },
        "local": {
            "enabled": False,
            "endpoint": settings.OLLAMA_ENDPOINT,
            "models": {
                "classify": "qwen2.5:7b",
                "analyze": "qwen2.5:32b",
                "explain": "qwen2.5:7b",
            },
        },
    }

    if os.path.exists(LLM_CONFIG_FILE):
        try:
            with open(LLM_CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                # 合并默认配置和保存的配置
                for key in default_config:
                    if key not in saved:
                        saved[key] = default_config[key]
                    elif isinstance(default_config[key], dict):
                        for subkey in default_config[key]:
                            if subkey not in saved[key]:
                                saved[key][subkey] = default_config[key][subkey]
                return saved
        except Exception as e:
            logger.warning("加载 LLM 配置失败: %s", e)

    return default_config


def _save_llm_config(config: dict) -> None:
    """保存 LLM 配置到文件"""
    import json

    os.makedirs("data", exist_ok=True)
    with open(LLM_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


@app.get("/api/settings/llm")
async def get_llm_settings():
    """获取 LLM 配置"""
    config = _load_llm_config()
    # 脱敏 API Key
    if config["remote"].get("apiKey"):
        config["remote"]["apiKey"] = "***"
    return config


@app.put("/api/settings/llm")
async def update_llm_settings(request: Request):
    """更新 LLM 配置"""
    data = await request.json()

    # 验证数据结构
    if "remote" not in data and "local" not in data:
        return {"success": False, "error": "无效的配置格式"}

    # 加载现有配置
    current_config = _load_llm_config()

    # 更新配置
    if "remote" in data:
        current_config["remote"].update(data["remote"])
        # 如果前端传了 "***"，保留原 API Key
        if current_config["remote"].get("apiKey") == "***":
            current_config["remote"]["apiKey"] = _load_llm_config()["remote"].get("apiKey", "")

    if "local" in data:
        current_config["local"].update(data["local"])

    # 保存配置
    _save_llm_config(current_config)
    logger.info("LLM 配置已更新并保存")

    return {"success": True}


# ── 静态文件挂载 ──

# 前端管理面板
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/admin", StaticFiles(directory=static_dir, html=True), name="admin")

# 手机端 PWA
mobile_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "mobile")
if os.path.isdir(mobile_dir):
    app.mount("/mobile", StaticFiles(directory=mobile_dir, html=True), name="mobile")

# 资源文件（logo、图标等）
asset_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "asset")
if os.path.isdir(asset_dir):
    app.mount("/asset", StaticFiles(directory=asset_dir), name="asset")


# ── 根路径重定向 ──


@app.get("/")
async def root():
    """重定向到管理面板"""
    return RedirectResponse(url="/admin/")


# ── 直接运行 ──

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
