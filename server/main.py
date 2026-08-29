"""合同红绿灯 — FastAPI 主入口"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime

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
    import json

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

        # 如果法规库为空，导入默认法规
        from server.models.database import LegalReference

        law_count_stmt = select(func.count()).select_from(LegalReference)
        law_count = (await db.execute(law_count_stmt)).scalar() or 0
        laws_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "shared", "laws")

        if law_count == 0:
            logger.info("法规库为空，导入默认法规...")
            if os.path.isdir(laws_dir):
                for filename in os.listdir(laws_dir):
                    if not filename.endswith(".json"):
                        continue
                    filepath = os.path.join(laws_dir, filename)
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            laws_data = json.load(f)
                        for law in laws_data:
                            # 解析日期字符串为 date 对象
                            eff_date = None
                            if law.get("effective_date"):
                                try:
                                    from datetime import date as _date
                                    eff_date = _date.fromisoformat(law["effective_date"])
                                except (ValueError, TypeError):
                                    pass

                            verified_at = None
                            if law.get("verified_at"):
                                try:
                                    verified_at = datetime.fromisoformat(
                                        str(law["verified_at"]).replace("Z", "+00:00")
                                    )
                                except (ValueError, TypeError):
                                    pass

                            ref = LegalReference(
                                law_name=law["law_name"],
                                article_number=law.get("article_number", ""),
                                content=law.get("content", ""),
                                effective_date=eff_date,
                                source_url=law.get("source_url"),
                                verified_at=verified_at,
                                tags=json.dumps(law.get("tags", []), ensure_ascii=False),
                            )
                            db.add(ref)
                        logger.info("导入法规: %s (%d 条)", filename, len(laws_data))
                    except Exception as e:
                        logger.warning("导入法规失败 %s: %s", filename, e)

                await db.commit()

        elif os.path.isdir(laws_dir):
            # 已有法规数据也要补齐新来源字段，不能因非空而永久跳过。
            for filename in os.listdir(laws_dir):
                if not filename.endswith(".json"):
                    continue
                try:
                    with open(os.path.join(laws_dir, filename), "r", encoding="utf-8") as f:
                        laws_data = json.load(f)
                    for law in laws_data:
                        if not law.get("source_url"):
                            continue
                        stmt = select(LegalReference).where(
                            LegalReference.law_name == law.get("law_name"),
                            LegalReference.article_number == law.get("article_number", ""),
                        )
                        ref = (await db.execute(stmt)).scalar_one_or_none()
                        if ref is None:
                            continue
                        if not ref.source_url:
                            ref.source_url = law["source_url"]
                        if not ref.verified_at and law.get("verified_at"):
                            try:
                                ref.verified_at = datetime.fromisoformat(
                                    str(law["verified_at"]).replace("Z", "+00:00")
                                )
                            except (ValueError, TypeError):
                                pass
                    logger.info("补齐法规来源: %s", filename)
                except Exception as e:
                    logger.warning("补齐法规来源失败 %s: %s", filename, e)
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

# ── 认证中间件 ──

from starlette.middleware.base import BaseHTTPMiddleware

from server.core.auth import auth_middleware

app.add_middleware(BaseHTTPMiddleware, dispatch=auth_middleware)

# ── 请求日志 ──


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """请求日志"""
    logger.debug("%s %s", request.method, request.url.path)
    response = await call_next(request)
    return response


# ── 注册路由 ──

from server.api.chat import router as chat_router
from server.api.contracts import router as contracts_router
from server.api.knowledge import router as knowledge_router
from server.api.memory import router as memory_router
from server.api.models import router as models_router
from server.api.skills import router as skills_router
from server.api.sync import router as sync_router
from server.api.wiki import router as wiki_router
from server.api.ws import router as ws_router
from server.api.connection import router as connection_router

app.include_router(contracts_router)
app.include_router(chat_router)
app.include_router(knowledge_router)
app.include_router(memory_router)
app.include_router(skills_router)
app.include_router(wiki_router)
app.include_router(models_router)
app.include_router(sync_router)
app.include_router(ws_router)
app.include_router(connection_router)


# ── LLM 配置接口 ──

LLM_CONFIG_FILE = os.path.join("data", "llm_config.json")


def _deep_merge(base: dict, override: dict) -> dict:
    """递归深合并：override 中的值覆盖 base，缺失的键从 base 补齐"""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


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
                return _deep_merge(default_config, saved)
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
    """获取 LLM 配置（仅 localhost 访问，不脱敏）"""
    return _load_llm_config()


@app.put("/api/settings/llm")
async def update_llm_settings(request: Request):
    """更新 LLM 配置"""
    data = await request.json()

    if "remote" not in data and "local" not in data:
        return {"success": False, "error": "无效的配置格式"}

    current_config = _load_llm_config()

    if "remote" in data:
        incoming = data["remote"]
        # 保留原 apiKey 的情况：前端传 "__KEEP__" 或显式未修改标记
        if incoming.get("apiKey") == "__KEEP__":
            incoming["apiKey"] = current_config["remote"].get("apiKey", "")
        current_config["remote"] = _deep_merge(current_config["remote"], incoming)

    if "local" in data:
        current_config["local"] = _deep_merge(current_config["local"], data["local"])

    _save_llm_config(current_config)
    logger.info("LLM 配置已更新并保存")

    # 重新加载 LLM 网关配置
    try:
        from server.core.llm import get_llm_gateway
        llm_gateway = get_llm_gateway()
        llm_gateway.reload_config()
        logger.info("LLM 网关配置已重新加载")
    except Exception as e:
        logger.warning("重新加载 LLM 网关配置失败: %s", e)

    return {"success": True}


@app.post("/api/settings/llm/test")
async def test_llm_connection():
    """测试远程 API 连接性，返回延迟"""
    import time

    from openai import AsyncOpenAI

    config = _load_llm_config()
    remote = config.get("remote", {})
    api_key = remote.get("apiKey", "")
    base_url = remote.get("baseUrl", "")
    model = remote.get("models", {}).get("classify", "deepseek-chat")

    if not api_key:
        return {"success": False, "error": "未配置 API Key"}

    client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=30.0)

    start = time.monotonic()
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=1,
        )
        latency = int((time.monotonic() - start) * 1000)
        return {
            "success": True,
            "latency_ms": latency,
            "model": resp.model or model,
            "provider": remote.get("provider", "unknown"),
        }
    except Exception as e:
        latency = int((time.monotonic() - start) * 1000)
        return {
            "success": False,
            "latency_ms": latency,
            "error": str(e),
            "provider": remote.get("provider", "unknown"),
        }


@app.post("/api/settings/llm/test-local")
async def test_local_llm_connection():
    """测试本地 Ollama 连接性"""
    import time

    import httpx

    config = _load_llm_config()
    local = config.get("local", {})
    endpoint = local.get("endpoint", "http://localhost:11434")

    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{endpoint}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            latency = int((time.monotonic() - start) * 1000)
            models = [m.get("name", "") for m in data.get("models", [])]
            return {
                "success": True,
                "latency_ms": latency,
                "models": models,
                "endpoint": endpoint,
            }
    except httpx.ConnectError:
        latency = int((time.monotonic() - start) * 1000)
        return {
            "success": False,
            "latency_ms": latency,
            "error": f"无法连接到 Ollama（{endpoint}），请确认 Ollama 已启动",
            "endpoint": endpoint,
        }
    except Exception as e:
        latency = int((time.monotonic() - start) * 1000)
        return {
            "success": False,
            "latency_ms": latency,
            "error": str(e),
            "endpoint": endpoint,
        }


# ── 静态文件挂载 ──

# 前端管理面板
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/admin", StaticFiles(directory=static_dir, html=True), name="admin")

# 手机端 PWA（designs/clause-light-mobile/ 是可用的 PWA 原型）
mobile_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "designs", "clause-light-mobile")
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
