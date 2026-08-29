"""Stage 1: 结构解析 Worker — 合同分类 + 条款拆解 + 模型路由"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from server.core.llm import LLMGateway
from server.core.schemas.llm_outputs import ParseResultSchema, RiskDimension

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


def normalize_contract_text(text: str) -> str:
    """Normalize Stage 1 text using the frontend's coordinate semantics."""
    normalized = text
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    normalized = re.sub(r"([^\n])\n([^\n])", r"\1 \2", normalized)
    normalized = re.sub(r" {2,}", " ", normalized)
    return normalized.strip()


def _utf16_length(text: str) -> int:
    """Return the JavaScript-compatible UTF-16 code-unit length."""
    return len(text.encode("utf-16-le")) // 2


def _utf16_prefix(text: str, max_units: int) -> str:
    """Return a text prefix no longer than ``max_units`` UTF-16 units."""
    units = 0
    end = 0
    for index, character in enumerate(text):
        character_units = 2 if ord(character) > 0xFFFF else 1
        if units + character_units > max_units:
            break
        units += character_units
        end = index + 1
    return text[:end]


# ── 数据结构 ──

@dataclass
class ClauseItem:
    """单个条款"""
    id: str = ""
    type: str = "other"
    title: str = ""
    text: str = ""
    relevance: list[RiskDimension] = field(default_factory=lambda: ["general"])
    source_start: int = -1
    source_end: int = -1
    review_required: bool = False
    review_reason: str = ""


@dataclass
class ParseResult:
    """Stage 1 解析结果"""
    contract_type: str = "其他"
    contract_type_en: str = "other"
    complexity: str = "standard"       # standard / complex
    recommended_model: str = "fast"    # fast / strong
    clauses: list[ClauseItem] = field(default_factory=list)
    parse_failed: bool = False
    failure_reason: str = ""
    parse_status: str = "completed"  # completed / partial / fallback
    review_required: bool = False
    fallback_reason: str = ""


# ── 文本分段 ──

CHUNK_SIZE = 6000  # 每段最大字符数


def _chunk_text(text: str) -> list[str]:
    """
    按段落边界切分长文本，每段不超过 CHUNK_SIZE 字符。

    切分策略：
    1. 优先按 "第X条" 等条款标题切分
    2. 其次按空行（段落间隔）切分
    3. 最后按固定长度硬切
    """
    if len(text) <= CHUNK_SIZE:
        return [text]

    # 策略1：按条款标题切分（"第X条"、"第X节"、"X." 等）
    # 匹配中文条款编号：第X条、第X节、X.X、X、（X）等
    splits = re.split(r'(?=(?:第[一二三四五六七八九十百千零\d]+[条章节]|[（(]\s*[一二三四五六七八九十百零\d]+\s*[）)]|\d+\.\d+\s|\d+\.\s))', text)

    chunks = []
    current = ''
    for part in splits:
        if not part.strip():
            continue
        if len(current) + len(part) > CHUNK_SIZE and current:
            chunks.append(current.strip())
            current = part
        else:
            current += part
    if current.strip():
        chunks.append(current.strip())

    # 如果策略1 切分后仍有超长段，按空行二次切分
    final_chunks = []
    for chunk in chunks:
        if len(chunk) <= CHUNK_SIZE:
            final_chunks.append(chunk)
            continue
        # 按空行切分
        paragraphs = chunk.split('\n\n')
        sub_current = ''
        for para in paragraphs:
            if len(sub_current) + len(para) + 2 > CHUNK_SIZE and sub_current:
                final_chunks.append(sub_current.strip())
                sub_current = para
            else:
                sub_current += ('\n\n' + para if sub_current else para)
        if sub_current.strip():
            final_chunks.append(sub_current.strip())

    # 策略3：最终兜底，硬切超长段
    result = []
    for chunk in final_chunks:
        while len(chunk) > CHUNK_SIZE:
            # 在 CHUNK_SIZE 附近找最近的换行符切分
            cut_pos = chunk.rfind('\n', 0, CHUNK_SIZE)
            if cut_pos < CHUNK_SIZE // 2:
                cut_pos = CHUNK_SIZE
            result.append(chunk[:cut_pos].strip())
            chunk = chunk[cut_pos:].strip()
        if chunk:
            result.append(chunk)

    return result if result else [text[:CHUNK_SIZE]]


def _fallback_parse_result(
    normalized_text: str,
    contract_type: str,
    reason: str,
) -> ParseResult:
    """Return a reviewable full-text clause when Stage 1 cannot parse."""
    clause = ClauseItem(
        id="1",
        type="other",
        title="全文",
        text=normalized_text,
        relevance=["general"],
        source_start=0,
        source_end=_utf16_length(normalized_text),
        review_required=True,
        review_reason=reason,
    )
    return ParseResult(
        contract_type=contract_type,
        contract_type_en=TYPE_EN_MAP.get(contract_type, "other"),
        clauses=[clause],
        parse_failed=True,
        failure_reason=reason,
        parse_status="fallback",
        review_required=True,
        fallback_reason=reason,
    )


def _apply_source_locations(clauses: list[ClauseItem], source_text: str) -> bool:
    """Attach monotonic normalized-text spans and report whether review is needed."""
    cursor = 0
    review_required = False
    for clause in clauses:
        clause.text = normalize_contract_text(clause.text)
        match_length = len(clause.text)
        start = source_text.find(clause.text, cursor) if clause.text else -1
        if start < 0 and clause.text:
            prefix = _utf16_prefix(clause.text, 30)
            start = source_text.find(prefix, cursor)
            match_length = len(prefix)

        if start < 0:
            clause.source_start = -1
            clause.source_end = -1
            clause.review_required = True
            clause.review_reason = "条款原文定位失败"
            review_required = True
            continue

        match_end = start + match_length
        clause.source_start = _utf16_length(source_text[:start])
        clause.source_end = _utf16_length(source_text[:match_end])
        cursor = match_end
        review_required = review_required or clause.review_required

    return review_required


VALID_RELEVANCE = {"equity", "financial", "ip", "dispute", "general"}


# ── Stage 1: 结构解析 ──

async def parse_contract(
    full_text: str,
    llm: LLMGateway,
    contract_type_hint: str | None = None,
) -> ParseResult:
    """
    Stage 1: 结构解析（分类 + 拆解 + 路由决策）。

    短合同（≤8000字）：一次 LLM 调用完成。
    长合同（>8000字）：分段解析后合并。

    返回 ParseResult，包含合同类型、条款数组、模型路由建议。
    """
    normalized_text = normalize_contract_text(full_text)
    # 分段处理长合同
    chunks = _chunk_text(normalized_text)
    if len(chunks) > 1:
        logger.info("合同较长（%d 字），分为 %d 段解析", len(full_text), len(chunks))

    all_clauses: list[ClauseItem] = []
    contract_type = contract_type_hint or "其他"
    contract_type_en = TYPE_EN_MAP.get(contract_type, "other")
    complexity = "standard"
    recommended_model = "fast"
    parse_failed = False
    failure_reason = ""

    for i, chunk in enumerate(chunks):
        chunk_result = await _parse_single_chunk(
            chunk, llm, contract_type_hint if i == 0 else contract_type,
        )

        # 第一段的合同类型最可靠（包含合同头部信息）
        if i == 0:
            contract_type = chunk_result.contract_type
            contract_type_en = chunk_result.contract_type_en
        if chunk_result.parse_failed:
            parse_failed = True
            if not failure_reason:
                failure_reason = chunk_result.failure_reason or chunk_result.fallback_reason

        all_clauses.extend(chunk_result.clauses)

        # 复杂度取最高值
        if chunk_result.complexity == "complex":
            complexity = "complex"
            recommended_model = chunk_result.recommended_model

    # 合并去重（按 id + 标题前 10 字匹配）
    seen = set()
    unique_clauses = []
    for clause in all_clauses:
        key = (clause.id, clause.title[:10] if clause.title else "")
        if key not in seen:
            seen.add(key)
            unique_clauses.append(clause)

    if not unique_clauses:
        reason = failure_reason or "未解析出条款"
        result = _fallback_parse_result(normalized_text, contract_type, reason)
    else:
        review_required = _apply_source_locations(unique_clauses, normalized_text)
        result = ParseResult(
            contract_type=contract_type,
            contract_type_en=contract_type_en,
            complexity=complexity,
            recommended_model=recommended_model,
            parse_failed=parse_failed,
            failure_reason=failure_reason,
            parse_status="partial" if parse_failed else "completed",
            review_required=review_required or parse_failed,
            clauses=unique_clauses,
        )

    logger.info(
        "Stage 1 完成: type=%s complexity=%s clauses=%d (from %d chunks)",
        result.contract_type, result.complexity, len(result.clauses), len(chunks),
    )
    return result


async def _parse_single_chunk(
    text: str,
    llm: LLMGateway,
    contract_type_hint: str | None = None,
) -> ParseResult:
    """单段文本的结构解析（一次 LLM 调用）"""

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

    user_content = f"请解析以下合同：\n\n{text}"

    if contract_type_hint:
        user_content = f"合同类型提示：{contract_type_hint}\n\n{user_content}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    try:
        resp = await llm.chat_structured(messages, schema=ParseResultSchema, task="analysis")
    except Exception as e:
        reason = f"LLM 调用失败: {e}"
        logger.warning("Stage 1 LLM 调用失败: %s", e)
        return ParseResult(
            parse_failed=True,
            failure_reason=reason,
            parse_status="fallback",
            review_required=True,
            fallback_reason=reason,
        )

    result = ParseResult()

    if not (resp.content or "").strip() and resp.parsed is None:
        logger.error("Stage 1 LLM 返回空内容")
        reason = "LLM 返回空内容"
        result.parse_failed = True
        result.failure_reason = reason
        result.parse_status = "fallback"
        result.review_required = True
        result.fallback_reason = reason
        return result

    parsed_model = resp.parsed
    if parsed_model is None:
        try:
            raw = llm.parse_json(resp.content)
        except Exception as e:
            reason = f"JSON 解析失败: {e}"
            logger.warning("Stage 1 JSON 解析失败: %s", e)
            result.parse_failed = True
            result.failure_reason = reason
            result.parse_status = "fallback"
            result.review_required = True
            result.fallback_reason = reason
            return result
        if not isinstance(raw, dict):
            logger.warning("Stage 1 JSON 解析失败")
            reason = "JSON 根对象不是解析结果"
            result.parse_failed = True
            result.failure_reason = reason
            result.parse_status = "fallback"
            result.review_required = True
            result.fallback_reason = reason
            return result
        invalid_relevance_positions: set[int] = set()
        raw_for_validation = dict(raw)
        raw_clauses = raw.get("clauses", [])
        if isinstance(raw_clauses, list):
            sanitized_clauses = []
            for index, clause in enumerate(raw_clauses):
                if not isinstance(clause, dict):
                    sanitized_clauses.append(clause)
                    continue
                sanitized_clause = dict(clause)
                clause_type = sanitized_clause.get("type", "other")
                if clause_type not in CLAUSE_TYPES:
                    clause_type = "other"
                relevance = sanitized_clause.get("relevance")
                if (
                    "relevance" in sanitized_clause
                    and (
                        not isinstance(relevance, list)
                        or not relevance
                        or any(
                            not isinstance(item, str) or item not in VALID_RELEVANCE
                            for item in relevance
                        )
                    )
                ):
                    sanitized_clause["relevance"] = TYPE_TO_WORKERS.get(
                        clause_type, ["general"]
                    )
                    invalid_relevance_positions.add(index)
                sanitized_clauses.append(sanitized_clause)
            raw_for_validation["clauses"] = sanitized_clauses
        try:
            parsed_model = ParseResultSchema.model_validate(raw_for_validation)
        except Exception as e:
            logger.warning("Stage 1 Schema 校验失败: %s", e)
            reason = f"Schema 校验失败: {e}"
            result.parse_failed = True
            result.failure_reason = reason
            result.parse_status = "fallback"
            result.review_required = True
            result.fallback_reason = reason
            return result
    else:
        invalid_relevance_positions = set()

    assert isinstance(parsed_model, ParseResultSchema)
    parsed = parsed_model.model_dump()

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
    for index, c in enumerate(raw_clauses):
        clause_type = c.get("type", "other")
        if clause_type not in CLAUSE_TYPES:
            clause_type = "other"

        relevance = c.get("relevance", TYPE_TO_WORKERS.get(clause_type, ["general"]))
        invalid_relevance = (
            index in invalid_relevance_positions
            or not isinstance(relevance, list)
            or not relevance
            or any(
                not isinstance(item, str) or item not in VALID_RELEVANCE
                for item in relevance
            )
        )
        if invalid_relevance:
            relevance = TYPE_TO_WORKERS.get(clause_type, ["general"])

        result.clauses.append(ClauseItem(
            id=c.get("id", ""),
            type=clause_type,
            title=c.get("title", ""),
            text=c.get("text", ""),
            relevance=relevance,
            review_required=invalid_relevance,
            review_reason="relevance 无效，已按条款类型映射" if invalid_relevance else "",
        ))

    result.review_required = any(clause.review_required for clause in result.clauses)

    return result
