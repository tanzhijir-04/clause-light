"""配置管理 — Pydantic Settings"""

from __future__ import annotations

from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings


Environment = Literal["development", "test", "production"]


class Settings(BaseSettings):
    """全局配置，从 .env 文件和环境变量读取"""

    # ── 服务 ──
    HOST: str = "0.0.0.0"
    PORT: int = 8080
    DEBUG: bool = False

    # ── 2.0 运行时 ──
    ENVIRONMENT: Environment = "development"
    # 开发环境保留 SQLite，生产环境由配置注入 PostgreSQL。
    DATABASE_URL: str = "sqlite+aiosqlite:///data/clause_light.db"
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_REQUIRED: bool = False
    AUTH_PEPPER: str = "development-only-change-me"
    JOB_LEASE_SECONDS: int = 60
    JOB_POLL_INTERVAL_SECONDS: float = 1.0
    OTEL_ENABLED: bool = False
    OTEL_EXPORTER_OTLP_ENDPOINT: str = ""
    METRICS_ENABLED: bool = True

    # ── 数据库 ──
    # ── 文件存储 ──
    UPLOAD_DIR: str = "data/uploads"
    MAX_UPLOAD_SIZE: int = 20 * 1024 * 1024  # 20MB

    # ── LLM — 远程 API ──
    LLM_DEEPSEEK_API_KEY: str = ""
    LLM_OPENAI_API_KEY: str = ""
    LLM_QWEN_API_KEY: str = ""

    # ── LLM — 本地 Ollama ──
    OLLAMA_ENDPOINT: str = "http://localhost:11434"

    # ── OCR ──
    OCR_USE_GPU: bool = False
    OCR_MODEL_DIR: str = "data/models/paddleocr"
    OCR_AUTO_DOWNLOAD: bool = True

    # ── 认证 ──
    API_KEY: str = ""  # 空字符串表示禁用认证，设置后所有 API 请求需携带 X-API-Key 头

    # ── 同步 ──
    SYNC_ENABLED: bool = False
    WEBDAV_URL: str = ""
    WEBDAV_USERNAME: str = ""
    WEBDAV_PASSWORD: str = ""
    S3_ENDPOINT: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_BUCKET: str = ""

    # ── 分层记忆 ──
    MEMORY_RETRIEVE_CHAR_BUDGET: int = 3000
    MEMORY_MAX_L1: int = 8
    MEMORY_MAX_L2: int = 2
    MEMORY_MAX_L3: int = 3
    MEMORY_RETRIEVE_TIMEOUT_SEC: float = 3.0
    MEMORY_AUTO_ACTIVATE_THRESHOLD: float = 0.75

    # ── Outlines 结构化输出（失败自动回退 parse_json）──
    OUTLINES_ENABLED: bool = True

    # ── LightRAG（Wiki/法规图检索，默认可关）──
    LIGHT_RAG_ENABLED: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @model_validator(mode="after")
    def validate_runtime_dependencies(self) -> "Settings":
        """生产环境必须显式配置事实数据库、凭据 Pepper 和必需的 Redis。"""
        if self.ENVIRONMENT == "production":
            if not self.DATABASE_URL.startswith("postgresql+"):
                raise ValueError("production DATABASE_URL 必须使用 PostgreSQL async driver")
            if self.REDIS_REQUIRED and not self.REDIS_URL:
                raise ValueError("production REDIS_REQUIRED=true 时必须配置 REDIS_URL")
            if self.AUTH_PEPPER == "development-only-change-me":
                raise ValueError("production 必须设置 AUTH_PEPPER")
        return self


settings = Settings()

# ── 共享常量 ──

# 合同类型中文→英文映射
TYPE_EN_MAP = {
    "租赁合同": "rental",
    "劳动合同": "labor",
    "装修合同": "renovation",
    "外包合同": "outsourcing",
    "借款合同": "loan",
    "服务合同": "service",
    "采购合同": "procurement",
    "合作协议": "cooperation",
    "其他": "other",
}

# 合同类型→知识库规则类别映射
TYPE_CATEGORY_MAP = {
    "租赁合同": "租赁",
    "劳动合同": "劳动",
    "装修合同": "装修",
    "外包合同": "外包",
    "借款合同": "借款",
    "服务合同": "服务",
    "采购合同": "采购",
    "合作协议": "合作",
}
