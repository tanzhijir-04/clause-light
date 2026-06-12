# ClauseLight — Agent 层重构：CC 开发提示词

## 你的任务

重构 `server/core/agent.py`，将现有的固定 7 步流水线替换为 Prompt Chaining + Parallelization 的三段式 Pipeline。

**先读** `docs/AGENT_ARCHITECTURE.md`，里面有完整的架构设计文档。本文档是实现指引。

---

## 第一步：创建 Worker 模块

在 `server/core/workers/` 下创建以下文件：

### 1.1 `server/core/workers/__init__.py`

导出所有 Worker。

### 1.2 `server/core/workers/parser.py`

Stage 1 结构解析 Worker。

```python
"""Stage 1: 结构解析 Worker — 合同分类 + 条款拆解 + 模型路由"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from server.core.llm import LLMGateway

logger = logging.getLogger(__name__)


# 条款类型枚举 — Stage 1 必须从这里选择
CLAUSE_TYPES = [
    "payment",           # 付款/结算条件
    "liability_cap",     # 赔偿上限/责任限制
    "penalty",           # 违约金/赔偿金
    "confidentiality",   # 保密义务
    "ip_ownership",      # 知识产权归属
    "non_compete",       # 竞业限制
    "termination",       # 合同解除/终止
    "dispute_resolution",# 争议解决
    "unilateral",        # 单方面权利/变更权
    "warranty",          # 质保/担保
    "force_majeure",     # 不可抗力
    "assignment",        # 合同转让/分包
    "other",             # 其他/未分类
]

# Worker 维度 → 条款类型的映射（哪些类型送哪些 Worker）
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

# 常见合同类型（用于模型路由判断）
STANDARD_CONTRACT_TYPES = ["劳动合同", "NDA", "保密协议", "租赁合同", "借款合同"]

# 常见合同类型的英文映射
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
        f"租赁合同、劳动合同、装修合同、外包合同、借款合同、服务合同、"
        f"采购合同、合作协议、保密协议/NDA、其他\n\n"
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
        # 兜底：全文作为一个条款
        result.clauses = [ClauseItem(
            id="1",
            type="other",
            title="全文",
            text=full_text[:2000],
            relevance=["general"],
        )]
        return result

    parsed = llm.parse_json(resp.content)

    if not isinstance(parsed, dict):
        logger.warning("Stage 1 JSON 解析失败，使用兜底方案")
        result.clauses = [ClauseItem(
            id="1",
            type="other",
            title="全文",
            text=full_text[:2000],
            relevance=["general"],
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
            id="1",
            type="other",
            title="全文",
            text=full_text[:2000],
            relevance=["general"],
        )]

    logger.info(
        "Stage 1 完成: type=%s complexity=%s clauses=%d",
        result.contract_type, result.complexity, len(result.clauses),
    )
    return result
```

### 1.3 `server/core/workers/equity.py`（以及其他 4 个 Worker）

5 个 Worker 共享同一个基类，只是维度名和关注点不同。创建一个通用 Worker 模板：

```python
"""Stage 2: 通用风险评估 Worker 模板"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from server.core.llm import LLMGateway
from server.core.workers.parser import ClauseItem

logger = logging.getLogger(__name__)


@dataclass
class ClauseRisk:
    """单条条款的风险评估结果"""
    clause_id: str = ""
    risk_level: str = "green"       # red / yellow / green
    risk_type: str = ""
    issue: str = ""
    unfavorable_to: str = ""
    severity: int = 1
    suggestion: str = ""
    legal_basis: str = ""


# 维度配置：每个 Worker 的维度名、中文名、关注点描述
WORKER_DIMENSIONS: dict[str, dict[str, str]] = {
    "equity": {
        "name": "权责对等",
        "focus": (
            "双方义务是否对等，是否存在单方面宽松/严苛条款。\n"
            "重点关注：甲方是否有单方面解除权而乙方没有、是否有单方面变更权、\n"
            "通知义务是否对等、免责条款是否对等。"
        ),
    },
    "financial": {
        "name": "财务风险",
        "focus": (
            "付款周期、违约金比例、赔偿上限、滞纳金、预付款风险。\n"
            "重点关注：付款周期是否过长（超过60天需警惕）、违约金是否过高（年化超24%需标记红色）、\n"
            "赔偿上限是否合理（低于合同总价20%需警惕）、是否有不合理的预付款要求。"
        ),
    },
    "ip": {
        "name": "知识产权",
        "focus": (
            "知识产权归属、保密义务范围、竞业限制合理性、数据使用权限。\n"
            "重点关注：工作成果IP是否全部归甲方、保密义务是否无限期、\n"
            "竞业限制是否超出合理范围、是否有数据使用的过度授权。"
        ),
    },
    "dispute": {
        "name": "争议解决",
        "focus": (
            "管辖地、仲裁条款、诉讼成本分担、举证责任分配。\n"
            "重点关注：管辖地是否对乙方不利（如约定甲方所在地法院）、\n"
            "仲裁条款是否剥夺了乙方的诉讼权利、举证责任是否过度偏向甲方。"
        ),
    },
    "general": {
        "name": "通用风险",
        "focus": (
            "不属于上述专业维度的其他风险。\n"
            "重点关注：不可抗力条款是否合理、合同转让/分包限制、\n"
            "通知送达方式、合同变更条件、其他显失公平的条款。"
        ),
    },
}


def build_worker_system_prompt(dimension: str) -> str:
    """构建指定维度的 Worker System Prompt"""
    dim = WORKER_DIMENSIONS[dimension]

    return (
        f"## 角色\n"
        f"你是合同审查的{dim['name']}专家。你代表合同的乙方（上传方），从他的利益出发评估风险。\n\n"
        f"## 关注点\n"
        f"{dim['focus']}\n\n"
        f"## 输入格式\n"
        f"你会收到一个 JSON 数组，每个元素包含 id、type、title、text 字段。\n\n"
        f"## Think 步骤\n"
        f"在给出风险评级前，对每个条款先推理（在 <think> 标签内）：\n"
        f"1. 该条款对乙方（上传方）的具体影响是什么？\n"
        f"2. 与行业惯例/法律默认条款相比，这个条款是否偏离？偏离方向是什么？\n"
        f"3. 不利方是谁？不利程度如何？\n\n"
        f"## 评级标准\n"
        f"- red: 条款明确不利于乙方且无对等保护，或违反法律强制性规定\n"
        f"- yellow: 存在不确定性、行业惯例有争议、或轻微不利于乙方\n"
        f"- green: 条款标准且对乙方无明显不利\n\n"
        f"## 输出格式\n"
        f"只返回 JSON 数组，不要包含任何其他文字、解释或 markdown 格式。\n"
        f"对每个条款输出：\n"
        f'{{\n'
        f'  "clause_id": "条款id",\n'
        f'  "risk_level": "red/yellow/green",\n'
        f'  "risk_type": "具体风险类型",\n'
        f'  "issue": "问题描述（一句话）",\n'
        f'  "unfavorable_to": "不利方（甲方/乙方/双方）",\n'
        f'  "severity": 1-10,\n'
        f'  "suggestion": "具体修改方向或替代表述",\n'
        f'  "legal_basis": "相关法律依据（如有）"\n'
        f'}}\n'
        f'如某条款在本维度无风险，输出 risk_level: "green"，issue: "本维度无明显风险"。\n'
    )


async def analyze_dimension(
    dimension: str,
    clauses: list[ClauseItem],
    llm: LLMGateway,
    contract_type: str,
    kb_rules: list[str] | None = None,
) -> list[ClauseRisk]:
    """
    单个维度的 Worker：分析一批条款的风险。

    只分析 relevance 包含该维度的条款。如果没有匹配条款，返回空列表。
    """
    # 筛选属于本维度的条款
    relevant = [c for c in clauses if dimension in c.relevance]

    if not relevant:
        logger.info("Worker[%s]: 无相关条款，跳过", dimension)
        return []

    dim_info = WORKER_DIMENSIONS[dimension]
    system_prompt = build_worker_system_prompt(dimension)

    # 构建条款输入
    import json
    clauses_input = json.dumps(
        [{"id": c.id, "type": c.type, "title": c.title, "text": c.text} for c in relevant],
        ensure_ascii=False,
    )

    user_content = f"合同类型：{contract_type}\n\n条款列表：\n{clauses_input}"

    if kb_rules:
        user_content += f"\n\n相关知识库规则（供参考）：\n" + "\n".join(f"- {r}" for r in kb_rules)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    resp = await llm.chat(messages, task="analysis")

    if not resp.content:
        logger.warning("Worker[%s]: LLM 返回空内容", dimension)
        return [
            ClauseRisk(clause_id=c.id, risk_level="green", issue="分析失败，请人工复核")
            for c in relevant
        ]

    parsed = llm.parse_json(resp.content)

    if not isinstance(parsed, list):
        logger.warning("Worker[%s]: JSON 解析失败", dimension)
        return [
            ClauseRisk(clause_id=c.id, risk_level="green", issue="分析失败，请人工复核")
            for c in relevant
        ]

    results: list[ClauseRisk] = []
    for item in parsed:
        if isinstance(item, dict):
            results.append(ClauseRisk(
                clause_id=item.get("clause_id", ""),
                risk_level=item.get("risk_level", "green"),
                risk_type=item.get("risk_type", ""),
                issue=item.get("issue", ""),
                unfavorable_to=item.get("unfavorable_to", ""),
                severity=item.get("severity", 1),
                suggestion=item.get("suggestion", ""),
                legal_basis=item.get("legal_basis", ""),
            ))

    logger.info(
        "Worker[%s] 完成: %d 条条款, red=%d yellow=%d green=%d",
        dimension,
        len(results),
        sum(1 for r in results if r.risk_level == "red"),
        sum(1 for r in results if r.risk_level == "yellow"),
        sum(1 for r in results if r.risk_level == "green"),
    )
    return results
```

然后创建 5 个薄包装文件（`equity.py`, `financial.py`, `ip.py`, `dispute.py`, `general.py`），每个只导出一个快捷函数：

```python
# server/core/workers/equity.py
"""权责对等 Worker"""
from server.core.workers.equity_impl import analyze_equity

__all__ = ["analyze_equity"]
```

或者更简单：直接在 `__init__.py` 里统一导出，不单独建文件。选择哪种方式取决于你——我建议统一放在一个 `workers.py` 文件里，用 `analyze_dimension("equity", ...)` 调用，减少文件数量。

### 1.4 `server/core/workers/evaluator.py`

Stage 3 聚合评分。

```python
"""Stage 3: Evaluator — 一致性检查 + 聚合评分"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from server.core.llm import LLMGateway
from server.core.workers.equity_impl import ClauseRisk

logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    """Stage 3 聚合结果"""
    overall_score: int = 0
    risk_distribution: dict[str, int] = field(default_factory=lambda: {"red": 0, "yellow": 0, "green": 0})
    recommendation: str = "negotiate_first"
    one_line_summary: str = ""
    needs_review: list[str] = field(default_factory=list)
    top_risks: list[str] = field(default_factory=list)


async def evaluate(
    clause_risks: list[ClauseRisk],
    llm: LLMGateway,
) -> EvaluationResult:
    """
    Stage 3: 一致性检查 + 聚合评分。

    1. 检测同一条款在不同 Worker 间的评级冲突
    2. 聚合评分
    3. 生成总结
    """
    import json

    result = EvaluationResult()

    # 1. 一致性检查：按 clause_id 分组，检测冲突
    from collections import defaultdict
    by_clause: dict[str, list[ClauseRisk]] = defaultdict(list)
    for r in clause_risks:
        by_clause[r.clause_id].append(r)

    needs_review: list[str] = []
    for clause_id, risks in by_clause.items():
        levels = set(r.risk_level for r in risks)
        if "red" in levels and "green" in levels:
            # 同一条款有 red 也有 green，需要人工复核
            needs_review.append(clause_id)
            logger.warning("条款 %s 评级冲突: %s", clause_id, levels)

    # 2. 聚合评分
    risk_list_text = "\n".join(
        f"条款 {r.clause_id}: {r.risk_level} ({r.risk_type}) - {r.issue}"
        for r in clause_risks
    )

    system_prompt = (
        "你是合同风险评估的聚合专家。基于各维度 Worker 的分析结果，给出综合评分。\n\n"
        "## 评分标准\n"
        "- 0-30: 高风险，建议不签或大幅修改后再签\n"
        "- 31-60: 中等风险，建议重点协商后再签\n"
        "- 61-80: 低风险，可签但建议微调\n"
        "- 81-100: 风险很低，可直接签署\n\n"
        "## 输出格式\n"
        "只返回 JSON 对象，不要包含任何其他文字或 markdown 格式：\n"
        "{\n"
        '  "overall_score": 0-100,\n'
        '  "risk_distribution": {"red": N, "yellow": N, "green": N},\n'
        '  "top_risks": ["最危险的3个风险（一句话）"],\n'
        '  "one_line_summary": "一句话总结",\n'
        '  "recommendation": "sign / negotiate_first / reject"\n'
        "}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"分析结果：\n{risk_list_text}"},
    ]

    resp = await llm.chat(messages, task="scoring")

    if resp.content:
        parsed = llm.parse_json(resp.content)
        if isinstance(parsed, dict):
            result.overall_score = parsed.get("overall_score", 50)
            result.risk_distribution = parsed.get("risk_distribution", {"red": 0, "yellow": 0, "green": 0})
            result.recommendation = parsed.get("recommendation", "negotiate_first")
            result.one_line_summary = parsed.get("one_line_summary", "")
            result.top_risks = parsed.get("top_risks", [])

    # 如果 LLM 没给出分布，从条款统计
    if not any(result.risk_distribution.values()):
        for r in clause_risks:
            level = r.risk_level
            if level in result.risk_distribution:
                result.risk_distribution[level] += 1

    # 如果没有评分，根据红黄绿比例计算
    if result.overall_score == 0:
        total = sum(result.risk_distribution.values())
        if total > 0:
            result.overall_score = int(
                (result.risk_distribution["green"] * 90
                 + result.risk_distribution["yellow"] * 60
                 + result.risk_distribution["red"] * 20) / total
            )

    result.needs_review = needs_review

    logger.info(
        "Stage 3 完成: score=%d red=%d yellow=%d green=%d review=%d",
        result.overall_score,
        result.risk_distribution.get("red", 0),
        result.risk_distribution.get("yellow", 0),
        result.risk_distribution.get("green", 0),
        len(needs_review),
    )
    return result
```

---

## 第二步：重写 `server/core/agent.py`

保留 `ContractAgent` 类名和 `analyze()` 方法签名（保持 API 层兼容），内部改为三段式 Pipeline。

```python
"""Agent Pipeline — 三段式 Prompt Chaining + Parallelization"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from typing import Callable

from server.config import TYPE_EN_MAP
from server.core.knowledge import KnowledgeEngine
from server.core.llm import LLMGateway, get_llm_gateway
from server.core.ocr import OCREngine, get_ocr_engine
from server.core.workers.evaluator import EvaluationResult, evaluate
from server.core.workers.equity_impl import ClauseRisk, analyze_dimension
from server.core.workers.parser import ParseResult, parse_contract

from server.models.database import async_session_factory

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """分析结果（保持与原有接口兼容）"""
    contract_id: str = ""
    contract_type: str = ""
    contract_type_en: str = "other"
    overall_score: int = 0
    recommendation: str = "negotiate_first"
    summary: str = ""
    model_used: str = ""
    clauses: list[dict] = field(default_factory=list)
    red_count: int = 0
    yellow_count: int = 0
    green_count: int = 0
    needs_review: list[str] = field(default_factory=list)
    top_risks: list[str] = field(default_factory=list)


# Worker 维度列表
DIMENSIONS = ["equity", "financial", "ip", "dispute", "general"]


class ContractAgent:
    """合同分析 Agent — 三段式 Pipeline"""

    def __init__(
        self,
        llm: LLMGateway | None = None,
        ocr: OCREngine | None = None,
    ) -> None:
        self.llm = llm or get_llm_gateway()
        self.ocr = ocr or get_ocr_engine()

    async def analyze(
        self,
        file_path: str,
        contract_type_hint: str | None = None,
        on_step: Callable | None = None,
    ) -> AnalysisResult:
        """完整的三段式分析流程"""

        async def _notify(step: int, total: int, message: str) -> None:
            if on_step:
                try:
                    await on_step(step, total, message)
                except Exception:
                    pass

        result = AnalysisResult()
        contract_id = uuid.uuid4().hex

        # ── OCR 识别 ──
        await _notify(1, 5, "正在识别文字...")
        logger.info("OCR 识别开始")
        try:
            ocr_result = await self._retry(
                lambda: self.ocr.recognize(file_path), "OCR 识别"
            )
            if not ocr_result or not ocr_result.full_text.strip():
                logger.error("OCR 识别结果为空")
                return result
            full_text = ocr_result.full_text

            # 检查 OCR 质量
            if ocr_result.confidence_avg < 0.7:
                logger.warning("OCR 置信度较低: %.2f", ocr_result.confidence_avg)
                # 仍然继续，但标记
        except Exception as e:
            logger.error("OCR 识别失败: %s", e)
            return result

        # ── Stage 1: 结构解析 ──
        await _notify(2, 5, "正在解析合同结构...")
        logger.info("Stage 1: 结构解析")
        try:
            parse_result = await parse_contract(full_text, self.llm, contract_type_hint)
        except Exception as e:
            logger.error("Stage 1 失败: %s", e)
            # 兜底：全文作为一个条款
            from server.core.workers.parser import ClauseItem
            parse_result = ParseResult(
                contract_type=contract_type_hint or "其他",
                clauses=[ClauseItem(id="1", type="other", title="全文", text=full_text[:2000], relevance=["general"])],
            )

        result.contract_type = parse_result.contract_type
        result.contract_type_en = parse_result.contract_type_en
        result.model_used = parse_result.recommended_model

        # ── 知识库检索 ──
        kb_rules: list[str] = []
        try:
            async with async_session_factory() as db:
                knowledge = KnowledgeEngine(db)
                kb_rules = await knowledge.search(full_text[:500], parse_result.contract_type)
        except Exception as e:
            logger.warning("知识库检索失败: %s", e)

        # ── Stage 2: 并行风险评估 ──
        total_workers = len(DIMENSIONS)
        await _notify(3, 5, f"正在并行分析 {total_workers} 个维度...")
        logger.info("Stage 2: 并行风险评估 (%d 个 Worker)", total_workers)

        worker_tasks = [
            analyze_dimension(dim, parse_result.clauses, self.llm, parse_result.contract_type, kb_rules)
            for dim in DIMENSIONS
        ]
        worker_results = await asyncio.gather(*worker_tasks, return_exceptions=True)

        # 合并所有 Worker 结果
        all_risks: list[ClauseRisk] = []
        for dim, res in zip(DIMENSIONS, worker_results):
            if isinstance(res, Exception):
                logger.warning("Worker[%s] 失败: %s", dim, res)
            elif isinstance(res, list):
                all_risks.extend(res)

        # ── Stage 3: 聚合评分 ──
        await _notify(4, 5, "正在聚合评分...")
        logger.info("Stage 3: 聚合评分")
        try:
            eval_result = await evaluate(all_risks, self.llm)
        except Exception as e:
            logger.warning("Stage 3 失败: %s", e)
            # 兜底：直接统计
            eval_result = EvaluationResult()
            for r in all_risks:
                if r.risk_level in eval_result.risk_distribution:
                    eval_result.risk_distribution[r.risk_level] += 1

        # ── 组装最终结果 ──
        await _notify(5, 5, "正在生成报告...")
        result.overall_score = eval_result.overall_score
        result.recommendation = eval_result.recommendation
        result.summary = eval_result.one_line_summary
        result.needs_review = eval_result.needs_review
        result.top_risks = eval_result.top_risks
        result.red_count = eval_result.risk_distribution.get("red", 0)
        result.yellow_count = eval_result.risk_distribution.get("yellow", 0)
        result.green_count = eval_result.risk_distribution.get("green", 0)

        # 组装条款列表（合并解析结果和风险评估结果）
        risk_map: dict[str, ClauseRisk] = {}
        for r in all_risks:
            # 同一 clause_id + 同一维度只保留 severity 最高的
            key = f"{r.clause_id}"
            if key not in risk_map or r.severity > risk_map[key].severity:
                risk_map[key] = r

        for clause in parse_result.clauses:
            risk = risk_map.get(clause.id)
            clause_dict = {
                "clause_number": clause.id,
                "title": clause.title,
                "content": clause.text,
                "type": clause.type,
                "risk_level": risk.risk_level if risk else "green",
                "risk_type": risk.risk_type if risk else "未分析",
                "risk_summary": risk.issue if risk else "本维度无明显风险",
                "plain_explanation": risk.issue if risk else "",
                "severity_score": risk.severity if risk else 1,
                "suggested_clause": risk.suggestion if risk else "",
                "legal_basis": risk.legal_basis if risk else "",
                "unfavorable_to": risk.unfavorable_to if risk else "",
                "needs_review": clause.id in eval_result.needs_review,
            }
            result.clauses.append(clause_dict)

        result.contract_id = contract_id
        logger.info(
            "分析完成: score=%d red=%d yellow=%d green=%d review=%d",
            result.overall_score,
            result.red_count,
            result.yellow_count,
            result.green_count,
            len(result.needs_review),
        )
        return result

    async def _retry(self, fn, step_name: str, max_retries: int = 2):
        """带重试的异步调用"""
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                return await fn()
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    logger.warning("%s 重试 %d/%d: %s", step_name, attempt + 1, max_retries, e)
                    await asyncio.sleep(1.0 * (attempt + 1))
        raise last_error  # type: ignore
```

---

## 第三步：更新 prompts 目录

将 prompt 模板迁移/保留：

- `server/core/prompts/classify.py` — **保留**，作为 Stage 1 的兜底 prompt
- `server/core/prompts/split.py` — **保留**，作为 Stage 1 的兜底 prompt
- `server/core/prompts/analyze.py` — **保留**，作为 Worker 的兜底 prompt
- `server/core/prompts/suggest.py` — **保留**，不改动
- `server/core/prompts/score.py` — **保留**，作为 Stage 3 的兜底 prompt

新的 System Prompt 已经内嵌在 Worker 代码中（`build_worker_system_prompt()`），不再单独存文件。这样做是因为 prompt 和维度配置强耦合，放在一起更容易维护。

---

## 第四步：验证

1. **单元测试**：为 `parse_contract` 和 `analyze_dimension` 写测试，mock LLM 响应
2. **集成测试**：用一份示例合同跑完整 Pipeline，检查：
   - Stage 1 输出的条款数组是否包含正确的 type 和 relevance
   - Stage 2 各 Worker 是否只分析了相关条款
   - Stage 3 聚合结果是否合理
3. **回归测试**：确认 `server/api/contracts.py` 的调用方式不变，API 返回格式兼容
4. **性能测试**：对比新旧方案的延迟（并行 vs 串行）

---

## 注意事项

- **不要改动 `server/core/llm.py`** 的现有接口，新功能通过新方法添加
- **不要改动前端代码**，API 返回格式保持兼容
- **不要改动数据库模型**
- 所有新文件使用 type hints，异常不能裸 except
- 所有日志用 `logging` 模块，不用 `print()`
- Commit message 用中文
