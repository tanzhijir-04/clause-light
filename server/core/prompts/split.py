"""条款拆解 Prompt"""

from __future__ import annotations


def split_prompt(contract_text: str, contract_type: str) -> list[dict]:
    """条款拆解 prompt — 将合同拆解为独立条款"""
    return [
        {
            "role": "system",
            "content": (
                "你是一个合同条款拆解专家。将以下合同拆解为独立条款，返回 JSON 数组。\n"
                "每个元素包含：clause_number（条款编号）、title（条款标题）、content（条款内容）\n"
                "仅返回 JSON 数组，不要其他内容。"
            ),
        },
        {
            "role": "user",
            "content": f"合同类型：{contract_type}\n\n合同全文：\n{contract_text}",
        },
    ]
