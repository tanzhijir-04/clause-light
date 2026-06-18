"""Embedding 引擎 — 基于 sentence-transformers 的向量化工具

使用懒加载模式：首次调用时才加载模型，如果 sentence-transformers
未安装则自动降级为纯关键词搜索（不报错）。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

logger = logging.getLogger(__name__)

# 模型单例
_model = None
_model_available: bool | None = None  # None = 未检测, True/False = 已检测


def _get_model():
    """懒加载 SentenceTransformer 模型"""
    global _model, _model_available

    if _model_available is False:
        return None

    if _model is not None:
        return _model

    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("shibing624/text2vec-base-chinese")
        _model_available = True
        logger.info("Embedding 模型加载完成: text2vec-base-chinese")
        return _model
    except ImportError:
        logger.warning(
            "sentence-transformers 未安装，知识库降级为纯关键词搜索。"
            "如需语义搜索，请运行: pip install sentence-transformers"
        )
        _model_available = False
        return None
    except Exception as e:
        logger.warning("Embedding 模型加载失败: %s", e)
        _model_available = False
        return None


def is_available() -> bool:
    """检查 embedding 模型是否可用"""
    return _get_model() is not None


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
