"""Distill Prompt — 从分析结果提炼候选记忆资产（严格 JSON）"""

from __future__ import annotations

import json
from typing import Any


_SYSTEM = """你是合同审查记忆提炼助手。根据分析结果与可选反馈，提炼可复用的记忆资产。
必须只输出一个 JSON 对象，不要 Markdown，不要解释。JSON schema：
{
  "atoms": [{"content": str, "kind": "fact|preference|constraint|event", "confidence": 0-1}],
  "rules": [{"rule_text": str, "category": str, "confidence": 0-1, "trigger_keywords": [str]}],
  "skills": [{"name": str, "triggers": {"contract_types":[str],"keywords":[str]}, "steps":[str], "validation":[str], "confidence": 0-1}],
  "wiki_patches": [{"slug": str, "title": str, "body": str, "confidence": 0-1}]
}
规则：
- atoms/rules 可为空数组；不确定时降低 confidence。
- skills 仅在出现可复用审查套路且 steps≥2 时输出，否则 []。
- wiki_patches 仅在有明确法条/概念解释时输出，否则 []。
"""


def build_distill_messages(
    *,
    contract_type: str,
    clause_summaries: list[dict[str, Any]],
    feedback_events: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    """构造 Distill LLM 消息，要求严格 JSON 输出"""
    payload = {
        "contract_type": contract_type,
        "clause_summaries": clause_summaries,
        "feedback_events": feedback_events or [],
    }
    user = (
        "请根据以下合同分析摘要提炼候选记忆资产，输出严格 JSON：\n"
        + json.dumps(payload, ensure_ascii=False)
    )
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": user},
    ]
