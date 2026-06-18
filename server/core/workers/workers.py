"""Stage 2: 通用风险评估 Worker — 5 个维度并行分析"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from server.core.llm import LLMGateway
from server.core.workers.parser import ClauseItem

logger = logging.getLogger(__name__)


# ── 数据结构 ──

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


# ── 维度配置 ──

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


# ── System Prompt 构建 ──

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


# ── Stage 2: 维度分析 ──

async def analyze_dimension(
    dimension: str,
    clauses: list[ClauseItem],
    llm: LLMGateway,
    contract_type: str,
    kb_rules: list[str] | None = None,
    kb_laws: list[dict] | None = None,
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

    system_prompt = build_worker_system_prompt(dimension)

    # 构建条款输入
    clauses_input = json.dumps(
        [{"id": c.id, "type": c.type, "title": c.title, "text": c.text} for c in relevant],
        ensure_ascii=False,
    )

    user_content = f"合同类型：{contract_type}\n\n条款列表：\n{clauses_input}"

    if kb_rules:
        user_content += "\n\n相关知识库规则（供参考）：\n" + "\n".join(f"- {r}" for r in kb_rules)

    if kb_laws:
        user_content += "\n\n相关法律条文（供参考）：\n"
        for law in kb_laws:
            user_content += f"- {law.get('law_name', '')} {law.get('article_number', '')}: {law.get('content', '')}\n"

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
