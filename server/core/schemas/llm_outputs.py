"""LLM 结构化输出 Schema（Outlines / Pydantic）"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt


RiskDimension = Literal["equity", "financial", "ip", "dispute", "general"]
RiskLevel = Literal["red", "yellow", "green", "unknown"]


class ParseClauseSchema(BaseModel):
    """Stage 1 单条条款"""

    id: str = Field(min_length=1, description="条款编号")
    type: str = "other"
    title: str = ""
    text: str = Field(min_length=1)
    relevance: list[RiskDimension] = Field(default_factory=lambda: ["general"])


class ParseResultSchema(BaseModel):
    """Stage 1 结构解析输出"""

    contract_type: str = "其他"
    complexity: Literal["standard", "complex"] = "standard"
    recommended_model: Literal["fast", "strong"] = "fast"
    clauses: list[ParseClauseSchema] = Field(default_factory=list)


class ClauseRiskSchema(BaseModel):
    """Stage 2 单条风险"""

    clause_id: str = Field(min_length=1)
    risk_level: Literal["red", "yellow", "green"]
    risk_type: str = ""
    issue: str = ""
    unfavorable_to: str = ""
    severity: int = Field(default=1, ge=1, le=10)
    suggestion: str = ""
    legal_basis: str = ""
    citation_ids: list[str] = Field(default_factory=list)


class ClauseRiskListSchema(BaseModel):
    """Stage 2 Worker 输出（数组包一层便于 schema 约束）"""

    risks: list[ClauseRiskSchema] = Field(default_factory=list)


class RiskDistributionSchema(BaseModel):
    """Stage 3 风险分布，只允许固定的非负整数计数。"""

    model_config = ConfigDict(extra="forbid")

    red: StrictInt = Field(default=0, ge=0)
    yellow: StrictInt = Field(default=0, ge=0)
    green: StrictInt = Field(default=0, ge=0)
    unknown: StrictInt = Field(default=0, ge=0)


class EvaluationSchema(BaseModel):
    """Stage 3 聚合评分"""

    overall_score: StrictInt = Field(default=50, ge=0, le=100)
    recommendation: Literal["sign", "negotiate_first", "reject"] = "negotiate_first"
    one_line_summary: str = ""
    needs_review: list[str] = Field(default_factory=list)
    top_risks: list[str] = Field(default_factory=list)
    risk_distribution: RiskDistributionSchema = Field(
        default_factory=RiskDistributionSchema
    )


class DistillAtomSchema(BaseModel):
    content: str
    kind: str = "fact"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class DistillRuleSchema(BaseModel):
    rule_text: str
    category: str = "通用"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    trigger_keywords: list[str] = Field(default_factory=list)


class DistillSkillSchema(BaseModel):
    name: str
    steps: list[str] = Field(default_factory=list)
    triggers: dict = Field(default_factory=dict)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class DistillWikiPatchSchema(BaseModel):
    title: str
    slug: str = ""
    body: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class DistillResultSchema(BaseModel):
    """Distill Pipeline JSON 根对象"""

    atoms: list[DistillAtomSchema] = Field(default_factory=list)
    rules: list[DistillRuleSchema] = Field(default_factory=list)
    skills: list[DistillSkillSchema] = Field(default_factory=list)
    wiki_patches: list[DistillWikiPatchSchema] = Field(default_factory=list)
