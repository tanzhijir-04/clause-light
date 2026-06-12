"""配置管理 — Pydantic Settings"""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """全局配置，从 .env 文件和环境变量读取"""

    # ── 服务 ──
    HOST: str = "0.0.0.0"
    PORT: int = 8080
    DEBUG: bool = False

    # ── 数据库 ──
    DATABASE_URL: str = "sqlite+aiosqlite:///data/clause_light.db"

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

    # ── 同步 ──
    SYNC_ENABLED: bool = False
    WEBDAV_URL: str = ""
    WEBDAV_USERNAME: str = ""
    WEBDAV_PASSWORD: str = ""
    S3_ENDPOINT: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_BUCKET: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


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
