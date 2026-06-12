"""风险分析 Prompt（核心）"""

from __future__ import annotations


def analyze_prompt(
    clause_content: str,
    contract_type: str,
    contract_context: str,
    kb_rules: list[str],
) -> list[dict]:
    """风险分析 prompt — 逐条分析条款风险"""
    rules_text = "\n".join(f"- {r}" for r in kb_rules) if kb_rules else "无相关规则"
    return [
        {
            "role": "system",
            "content": (
                "你是一个专业的合同风险审查助手。分析以下条款的风险。\n"
                "默认从接受方（乙方）的角度审查。\n\n"
                "返回 JSON：\n"
                '{\n'
                '  "risk_level": "red" | "yellow" | "green",\n'
                '  "risk_type": "风险类型（如：违约金过高、霸王条款、权责不对等等）",\n'
                '  "risk_summary": "一句话摘要（20字内）",\n'
                '  "plain_explanation": "大白话解释（50字内）",\n'
                '  "legal_basis": "相关法律依据",\n'
                '  "severity_score": 1-10\n'
                '}\n\n'
                "只返回 JSON 对象，不要包含任何其他文字、解释或 markdown 格式。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"合同类型：{contract_type}\n\n"
                f"条款内容：{clause_content}\n\n"
                f"相关知识库规则：{rules_text}"
            ),
        },
    ]
