"""合同分类 Prompt"""

from __future__ import annotations


def classify_prompt(contract_text: str) -> list[dict]:
    """合同分类 prompt — 判断合同类型"""
    return [
        {
            "role": "system",
            "content": (
                "你是一个合同分类专家。分析以下合同文本，判断其合同类型。\n"
                "可选类型：租赁合同、劳动合同、装修合同、外包合同、借款合同、"
                "服务合同、采购合同、合作协议、其他\n"
                "仅返回类型名称，不要其他内容。"
            ),
        },
        {
            "role": "user",
            "content": f"分析以下合同的类型：\n\n{contract_text[:3000]}",
        },
    ]
