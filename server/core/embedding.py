"""Embedding 引擎 — 基于 sentence-transformers 的向量化工具

使用懒加载模式：首次调用时才加载模型，如果 sentence-transformers
未安装则自动降级为纯关键词搜索（不报错）。

重要：所有模型加载操作都使用线程池执行，避免阻塞 asyncio 事件循环。
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import numpy as np

logger = logging.getLogger(__name__)

# 模型单例
_model = None
_model_available: bool | None = None  # None = 未检测, True/False = 已检测
_loading_lock = asyncio.Lock() if hasattr(asyncio, 'Lock') else None


def _load_model_sync():
    """同步加载 SentenceTransformer 模型（在线程池中执行）"""
    from sentence_transformers import SentenceTransformer
    logger.info("正在下载 Embedding 模型: text2vec-base-chinese (首次需下载约 400MB，请耐心等待)")
    model = SentenceTransformer("shibing624/text2vec-base-chinese")
    logger.info("Embedding 模型加载完成: text2vec-base-chinese")
    return model


def _get_model_sync():
    """同步获取模型（用于非 async 上下文）"""
    global _model, _model_available

    if _model_available is False:
        return None

    if _model is not None:
        return _model

    try:
        _model = _load_model_sync()
        _model_available = True
        return _model
    except ImportError:
        logger.warning(
            "sentence-transformers 未安装，知识库降级为纯关键词搜索。"
            "如需语义搜索，请运行: pip install sentence-transformers"
        )
        _model_available = False
        return None
    except Exception as e:
        logger.warning("Embedding 模型加载失败: %s (将降级为纯关键词搜索)", e)
        _model_available = False
        return None


async def _get_model_async():
    """异步获取模型（使用线程池避免阻塞事件循环）"""
    global _model, _model_available

    if _model_available is False:
        return None

    if _model is not None:
        return _model

    try:
        # 使用线程池执行同步的模型下载，避免阻塞事件循环
        loop = asyncio.get_event_loop()
        _model = await loop.run_in_executor(None, _load_model_sync)
        _model_available = True
        return _model
    except ImportError:
        logger.warning(
            "sentence-transformers 未安装，知识库降级为纯关键词搜索。"
            "如需语义搜索，请运行: pip install sentence-transformers"
        )
        _model_available = False
        return None
    except Exception as e:
        logger.warning("Embedding 模型加载失败: %s (将降级为纯关键词搜索)", e)
        _model_available = False
        return None


def is_available() -> bool:
    """检查 embedding 模型是否可用（同步版本，不触发下载）"""
    # 只检查是否已加载，不触发懒加载
    return _model is not None


async def is_available_async() -> bool:
    """检查 embedding 模型是否可用（异步版本，会触发懒加载）"""
    model = await _get_model_async()
    return model is not None


def encode(texts: list[str]) -> np.ndarray | None:
    """
    将文本列表编码为向量。

    返回 shape=(N, dim) 的 numpy 数组，如果模型不可用返回 None。
    """
    model = _get_model()
    if model is None:
        return None

    try:
        embeddings = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
        return embeddings
    except Exception as e:
        logger.error("Embedding 编码失败: %s", e)
        return None


def encode_single(text: str) -> list[float] | None:
    """将单条文本编码为向量（列表格式，用于存入数据库）"""
    result = encode([text])
    if result is None or len(result) == 0:
        return None
    return result[0].tolist()


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """计算两个向量的余弦相似度（假设已归一化）"""
    return float(np.dot(a, b))


def batch_similarity(query_vec: np.ndarray, corpus_vecs: np.ndarray) -> np.ndarray:
    """
    计算查询向量与语料库向量的相似度。

    query_vec: shape=(dim,)
    corpus_vecs: shape=(N, dim)
    返回: shape=(N,) 的相似度数组
    """
    return corpus_vecs @ query_vec
