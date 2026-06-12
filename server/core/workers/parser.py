"""Stage 1: 结构解析 Worker — 合同分类 + 条款拆解 + 模型路由"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from server.core.llm import LLMGateway

logger = logging.getLogger(__name__)


# ── 条款类型枚举 ──

CLAUSE_TYPES = [
    "payment",            # 付款/结算条件
    "liability_cap",      # 赔偿上限/责任限制
    "penalty",            # 违约金/赔偿金
    "confidentiality",    # 保密义务
    "ip_ownership",       # 知识产权归属
    "non_compete",        # 竞业限制
    "termination",        # 合同解除/终止
    "dispute_resolution", # 争议解决
    "unilateral",         # 单方面权利/变更权
    "warranty",           # 质保/担保
    "force_majeure",      # 不可抗力
    "assignment",         # 合同转让/分包
    "other",              # 其他/未分类
]

# 条款类型 → Worker 维度的映射
TYPE_TO_WORKERS: dict[str, list[str]] = {
    "payment": ["financial"],
    "liability_cap": ["equity", "financial"],
    "penalty": ["equity", "financial"],
    "confidentiality": ["ip"],
    "ip_ownership": ["ip"],
    "non_compete": ["ip", "equity"],
    "termination": ["equity", "dispute"],
    "dispute_resolution": ["dispute"],
    "unilateral": ["equity"],
    "warranty": ["equity", "financial"],
    "force_majeure": ["general"],
    "assignment": ["equity"],
    "other": ["general"],
}

# 中文合同类型 → 英文 slug 映射
TYPE_EN_MAP: dict[str, str] = {
    "劳动合同": "labor",
    "租赁合同": "rental",
    "装修合同": "renovation",
    "外包合同": "outsourcing",
    "借款合同": "loan",
    "服务合同": "service",
    "采购合同": "procurement",
    "合作协议": "cooperation",
    "保密协议": "nda",
    "NDA": "nda",
    "其他": "other",
}


# ── 数据结构 ──

@dataclass
class ClauseItem:
    """单个条款"""
    id: str = ""
    type: str = "other"
    title: str = ""
    text: str = ""
    relevance: list[str] = field(default_factory=lambda: ["general"])


@dataclass
class ParseResult:
    """Stage 1 解析结果"""
    contract_type: str = "其他"
    contract_type_en: str = "other"
    complexity: str = "standard"       # standard / complex
    recommended_model: str = "fast"    # fast / strong
    clauses: list[ClauseItem] = field(default_factory=list)


# ── Stage 1: 结构解析 ──

async def parse_contract(
    full_text: str,
    llm: LLMGateway,
    contract_type_hint: str | None = None,
) -> ParseResult:
    """
    Stage 1: 一次 LLM 调用，完成分类 + 拆解 + 路由决策。

    返回 ParseResult，包含合同类型、条款数组、模型路由建议。
    """

    system_prompt = (
        "你是一个合同结构解析专家。你的任务是对合同进行三个操作：\n"
        "1. 判断合同类型\n"
        "2. 将合同拆解为独立条款\n"
        "3. 判断合同复杂度\n\n"
        "## 合同类型（必须从以下选项中选择）\n"
        "租赁合同、劳动合同、装修合同、外包合同、借款合同、服务合同、"
        "采购合同、合作协议、保密协议/NDA、其他\n\n"
        "## 条款类型（每个条款必须从以下类型中选择）\n"
        f"{', '.join(CLAUSE_TYPES)}\n\n"
        "## 条款 relevance 字段\n"
        "每个条款需要标注 relevance 字段，表示该条款需要哪些维度的 Worker 分析。\n"
        "可选维度：equity（权责对等）、financial（财务风险）、ip（知识产权）、dispute（争议解决）、general（通用）\n"
        "参考映射：payment→financial, liability_cap→[equity,financial], penalty→[equity,financial], "
        "confidentiality→ip, ip_ownership→ip, non_compete→[ip,equity], "
        "termination→[equity,dispute], dispute_resolution→dispute, unilateral→equity, "
        "warranty→[equity,financial], force_majeure→general, assignment→equity, other→general\n\n"
        "## 复杂度判断\n"
        "- standard: 常见合同类型，条款类型都在上述枚举内，条款数 ≤ 15\n"
        "- complex: 出现 other 类型条款，或条款数 > 15，或合同类型不在常见列表中\n\n"
        "## 输出格式\n"
        "只返回 JSON 对象，不要包含任何其他文字、解释或 markdown 格式：\n"
        "{\n"
        '  "contract_type": "合同类型",\n'
        '  "complexity": "standard 或 complex",\n'
        '  "clauses": [\n'
        "    {\n"
        '      "id": "条款编号（如3.2）",\n'
        '      "type": "条款类型",\n'
        '      "title": "条款标题",\n'
        '      "text": "条款原文",\n'
        '      "relevance": ["维度1", "维度2"]\n'
        "    }\n"
        "  ]\n"
        "}"
    )

    user_content = f"请解析以下合同：\n\n{full_text[:8000]}"

    if contract_type_hint:
        user_content = f"合同类型提示：{contract_type_hint}\n\n{user_content}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    resp = await llm.chat(messages, task="analysis")

    result = ParseResult()

    if not resp.content:
        logger.error("Stage 1 LLM 返回空内容")
        result.clauses = [ClauseItem(
            id="1", type="other", title="全文",
            text=full_text[:2000], relevance=["general"],
        )]
        return result

    parsed = llm.parse_json(resp.content)

    if not isinstance(parsed, dict):
        logger.warning("Stage 1 JSON 解析失败，使用兜底方案")
        result.clauses = [ClauseItem(
            id="1", type="other", title="全文",
            text=full_text[:2000], relevance=["general"],
        )]
        return result

    # 解析合同类型
    result.contract_type = parsed.get("contract_type", contract_type_hint or "其他")
    result.contract_type_en = TYPE_EN_MAP.get(result.contract_type, "other")

    # 解析复杂度和模型路由
    result.complexity = parsed.get("complexity", "standard")
    result.recommended_model = parsed.get("recommended_model", "fast")

    # 如果出现 other 类型条款，强制 complex
    raw_clauses = parsed.get("clauses", [])
    has_other = any(c.get("type") == "other" for c in raw_clauses)
    if has_other or len(raw_clauses) > 15:
        result.complexity = "complex"
        result.recommended_model = "strong"

    # 解析条款
    for c in raw_clauses:
        clause_type = c.get("type", "other")
        if clause_type not in CLAUSE_TYPES:
            clause_type = "other"

        relevance = c.get("relevance", TYPE_TO_WORKERS.get(clause_type, ["general"]))
        if not isinstance(relevance, list):
            relevance = ["general"]

        result.clauses.append(ClauseItem(
            id=c.get("id", ""),
            type=clause_type,
            title=c.get("title", ""),
            text=c.get("text", ""),
            relevance=relevance,
        ))

    if not result.clauses:
        result.clauses = [ClauseItem(
            id="1", type="other", title="全文",
            text=full_text[:2000], relevance=["general"],
        )]

    logger.info(
        "Stage 1 完成: type=%s complexity=%s clauses=%d",
        result.contract_type, result.complexity, len(result.clauses),
    )
    return result
