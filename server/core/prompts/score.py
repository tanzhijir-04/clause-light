"""综合评分 Prompt"""

from __future__ import annotations


def score_prompt(all_analyses: list[dict]) -> list[dict]:
    """综合评分 prompt — 基于所有条款分析给出总评"""
    analyses_text = "\n\n".join(
        [
            f"条款：{a.get('clause_number', '')} {a.get('clause_title', '')}\n"
            f"风险：{a.get('risk_level', '')} - {a.get('risk_summary', '')}\n"
            f"评分：{a.get('severity_score', 0)}"
            for a in all_analyses
        ]
    )
    return [
        {
            "role": "system",
            "content": (
                "基于以下分析结果，给出综合评分。\n\n"
                "返回 JSON：\n"
                '{\n'
                '  "overall_score": 0-100,\n'
                '  "risk_distribution": {"red": N, "yellow": N, "green": N},\n'
                '  "top_risks": ["最危险的3个风险"],\n'
                '  "one_line_summary": "一句话总结",\n'
                '  "recommendation": "sign" | "negotiate_first" | "reject"\n'
                '}'
            ),
        },
        {
            "role": "user",
            "content": f"分析结果：\n{analyses_text}",
        },
    ]
