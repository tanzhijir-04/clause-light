"""修改建议 Prompt"""

from __future__ import annotations


def suggest_prompt(clause: str, risk_type: str) -> list[dict]:
    """修改建议 prompt — 针对风险条款生成修改建议"""
    return [
        {
            "role": "system",
            "content": (
                "针对以下风险条款，生成修改建议。\n\n"
                "返回 JSON：\n"
                '{\n'
                '  "suggested_clause": "修改后的完整条款",\n'
                '  "modification_reason": "理由（30字内）",\n'
                '  "can_negotiate": true/false,\n'
                '  "negotiation_tip": "谈判话术（如有）"\n'
                '}\n\n'
                "只返回 JSON 对象，不要包含任何其他文字、解释或 markdown 格式。"
            ),
        },
        {
            "role": "user",
            "content": f"条款：{clause}\n风险类型：{risk_type}",
        },
    ]
