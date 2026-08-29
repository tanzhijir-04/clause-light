"""Three comparable Route B experiment modes.

The module deliberately keeps only redacted run metadata in its result object.  The
caller may opt into contract text for local debugging, but the frozen runner does
not do so.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from experiments.contract_pipeline.metrics import estimate_cost
from server.core.agent import AnalysisResult, ContractAgent
from server.core.document_ingress import ingest
from server.core.llm import LLMCallRecord, LLMGateway
from server.core.workers.parser import normalize_contract_text


class SinglePassClauseSchema(BaseModel):
    clause_number: str = Field(min_length=1)
    title: str = ""
    content: str = Field(min_length=1)
    type: str = "other"
    risk_level: Literal["red", "yellow", "green"]
    risk_type: str = ""
    risk_summary: str = ""
    severity_score: int = Field(default=1, ge=1, le=10)
    suggested_clause: str = ""
    legal_basis: str = ""
    citation_ids: list[str] = Field(default_factory=list)


class SinglePassReviewSchema(BaseModel):
    contract_type: str = "其他"
    overall_score: int | None = Field(default=None, ge=0, le=100)
    summary: str = ""
    recommendation: Literal["sign", "negotiate_first", "reject", "manual_review"] = "manual_review"
    clauses: list[SinglePassClauseSchema] = Field(default_factory=list)
    review_reasons: dict[str, list[str]] = Field(default_factory=dict)


@dataclass
class ExperimentRunResult:
    experiment_id: str
    sample_id: str
    independent_group: str
    mode: str
    repeat_index: int
    provider: str
    model: str
    temperature: float
    started_at: str
    elapsed_ms: int
    success: bool
    analysis_status: str
    overall_score: int | None
    clauses: list[dict]
    review_reasons: dict[str, list[str]]
    call_records: list[dict]
    estimated_cost: float | None
    cost_currency: str
    input_sha256: str
    error_type: str = ""
    error_message: str = ""

    def to_dict(self, store_contract_text: bool = False) -> dict:
        data = asdict(self)
        if not store_contract_text:
            for clause in data["clauses"]:
                clause.pop("content", None)
                clause.pop("text", None)
        return data


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _records_from_gateway(llm: Any) -> list[dict]:
    records = getattr(llm, "trace_records", None)
    if records is None:
        records = getattr(llm, "_experiment_trace", [])
    return [asdict(item) if isinstance(item, LLMCallRecord) else dict(item) for item in records]


def attach_trace_sink(llm: Any, records: list[LLMCallRecord]) -> None:
    """Attach to a gateway without replacing a caller-owned sink when possible."""
    if isinstance(llm, LLMGateway):
        previous = getattr(llm, "_trace_sink", None)

        def sink(record: LLMCallRecord) -> None:
            records.append(record)
            if previous:
                previous(record)

        llm._trace_sink = sink


def _provider_model(llm: Any, records: list[dict]) -> tuple[str, str]:
    plan_getter = getattr(llm, "get_processing_plan", None)
    if callable(plan_getter):
        plan = plan_getter(task="analysis")
        if plan is not None and (plan.provider or plan.model):
            return plan.provider, plan.model
    if records:
        return records[0].get("provider", ""), records[0].get("model", "")
    return "", ""


def _safe_clause_dict(clause: dict) -> dict:
    return {
        "clause_number": clause.get("clause_number", clause.get("id", "")),
        "title": clause.get("title", ""),
        "content": clause.get("content", clause.get("text", "")),
        "type": clause.get("type", "other"),
        "risk_level": clause.get("risk_level", "unknown")
        if clause.get("risk_level") in {"red", "yellow", "green", "unknown"}
        else "unknown",
        "risk_type": clause.get("risk_type", ""),
        "risk_summary": clause.get("risk_summary", clause.get("issue", "")),
        "severity_score": clause.get("severity_score", clause.get("severity")),
        "suggested_clause": clause.get("suggested_clause", clause.get("suggestion", "")),
        "legal_basis": clause.get("legal_basis", ""),
        "citation_ids": list(clause.get("citation_ids") or []),
        "analysis_status": clause.get("analysis_status", "completed"),
        "needs_review": bool(clause.get("needs_review", False)),
        "source_start": clause.get("source_start", -1),
        "source_end": clause.get("source_end", -1),
    }


def _base_result(
    *, sample_id: str, independent_group: str, mode: str, repeat_index: int,
    provider: str, model: str, temperature: float, started_at: str,
    elapsed_ms: int, success: bool, analysis_status: str, overall_score: int | None,
    clauses: list[dict], review_reasons: dict[str, list[str]], call_records: list[dict],
    input_text: str, pricing: dict | None = None, error_type: str = "", error_message: str = "",
) -> ExperimentRunResult:
    cost = estimate_cost(call_records, pricing)
    return ExperimentRunResult(
        experiment_id=uuid.uuid4().hex,
        sample_id=sample_id,
        independent_group=independent_group,
        mode=mode,
        repeat_index=repeat_index,
        provider=provider,
        model=model,
        temperature=temperature,
        started_at=started_at,
        elapsed_ms=elapsed_ms,
        success=success,
        analysis_status=analysis_status,
        overall_score=overall_score,
        clauses=clauses,
        review_reasons=review_reasons,
        call_records=call_records,
        estimated_cost=cost["cost"],
        cost_currency=cost["currency"],
        input_sha256=hashlib.sha256(input_text.encode("utf-8")).hexdigest(),
        error_type=error_type,
        error_message=error_message,
    )


async def run_single_pass(
    full_text: str,
    llm: LLMGateway,
    *,
    sample_id: str,
    independent_group: str,
    repeat_index: int = 1,
    temperature: float = 0.1,
    pricing: dict | None = None,
) -> ExperimentRunResult:
    """One whole-document structured call; no KB, memory, workers or evaluator."""
    started_at = _now()
    start = time.monotonic()
    records: list[LLMCallRecord] = []
    attach_trace_sink(llm, records)
    provider = model = ""
    previous_structured_mode = getattr(llm, "structured_mode", None)
    try:
        provider, model = _provider_model(llm, [])
        if isinstance(llm, LLMGateway):
            # The baseline has exactly one structured request; Outlines followed by
            # chat fallback would make it an unfair multi-call baseline.
            llm.structured_mode = "json_fallback"
        prompt_path = Path(__file__).resolve().parents[2] / "server" / "core" / "prompts" / "single_pass_review.txt"
        prompt = prompt_path.read_text(encoding="utf-8") + "\n" + full_text
        response = await llm.chat_structured(
            [{"role": "system", "content": prompt}],
            schema=SinglePassReviewSchema,
            task="analysis",
            temperature=temperature,
            max_retries=0,
        )
        provider = provider or getattr(response, "provider", "")
        model = model or getattr(response, "model", "")
        parsed = response.parsed
        if not isinstance(parsed, SinglePassReviewSchema):
            raise ValueError("单次整文结构化结果校验失败")
        normalized = normalize_contract_text(full_text)
        clauses = [_safe_clause_dict(item.model_dump()) for item in parsed.clauses]
        # Reuse the production locator semantics while keeping the baseline's schema independent.
        cursor = 0
        for clause in clauses:
            if clause["citation_ids"]:
                clause["citation_ids"] = []
                parsed.review_reasons.setdefault(clause["clause_number"], []).append(
                    "单次整文基线未连接法规数据库，引用需人工复核"
                )
            text = normalize_contract_text(clause["content"])
            start_at = normalized.find(text, cursor) if text else -1
            if start_at >= 0:
                clause["source_start"] = len(normalized[:start_at].encode("utf-16-le")) // 2
                end_at = start_at + len(text)
                clause["source_end"] = len(normalized[:end_at].encode("utf-16-le")) // 2
                cursor = end_at
            else:
                clause["risk_level"] = "unknown"
                clause["analysis_status"] = "failed"
                clause["needs_review"] = True
                parsed.review_reasons.setdefault(clause["clause_number"], []).append("条款原文定位失败")
        elapsed = int((time.monotonic() - start) * 1000)
        return _base_result(
            sample_id=sample_id, independent_group=independent_group, mode="single_pass",
            repeat_index=repeat_index, provider=provider, model=model, temperature=temperature,
            started_at=started_at, elapsed_ms=elapsed, success=True,
            analysis_status="completed", overall_score=parsed.overall_score,
            clauses=clauses, review_reasons=parsed.review_reasons,
            call_records=[asdict(record) for record in records], input_text=full_text, pricing=pricing,
        )
    except Exception as exc:
        return _base_result(
            sample_id=sample_id, independent_group=independent_group, mode="single_pass",
            repeat_index=repeat_index, provider=provider, model=model, temperature=temperature,
            started_at=started_at, elapsed_ms=int((time.monotonic() - start) * 1000), success=False,
            analysis_status="failed", overall_score=None, clauses=[], review_reasons={"pipeline": [str(exc)]},
            call_records=[asdict(record) for record in records], input_text=full_text, pricing=pricing,
            error_type=type(exc).__name__, error_message=" ".join(str(exc).split())[:200],
        )
    finally:
        if isinstance(llm, LLMGateway) and previous_structured_mode is not None:
            llm.structured_mode = previous_structured_mode


async def _run_multi_stage(
    input_path: str,
    llm: LLMGateway,
    *,
    mode: str,
    sample_id: str,
    independent_group: str,
    repeat_index: int = 1,
    temperature: float = 0.1,
    pricing: dict | None = None,
) -> ExperimentRunResult:
    started_at = _now()
    started = time.monotonic()
    records: list[LLMCallRecord] = []
    attach_trace_sink(llm, records)
    input_text = ""
    try:
        input_text = (await ingest(input_path)).full_text
    except Exception:
        try:
            input_text = Path(input_path).read_text(encoding="utf-8")
        except Exception:
            input_text = ""
    provider, model = _provider_model(llm, [])
    try:
        result: AnalysisResult = await ContractAgent(llm=llm).analyze(
            input_path, worker_mode="serial" if mode == "serial_multi_stage" else "parallel"
        )
        provider = provider or getattr(result, "provider", "")
        clauses = [_safe_clause_dict(item) for item in result.clauses]
        return _base_result(
            sample_id=sample_id, independent_group=independent_group, mode=mode,
            repeat_index=repeat_index, provider=provider, model=model, temperature=temperature,
            started_at=started_at, elapsed_ms=int((time.monotonic() - started) * 1000),
            success=result.analysis_status in {"completed", "partial"},
            analysis_status=result.analysis_status, overall_score=result.overall_score,
            clauses=clauses, review_reasons=result.review_reasons,
            call_records=[asdict(record) for record in records], input_text=input_text, pricing=pricing,
            error_type="" if result.analysis_status != "failed" else "AnalysisFailed",
            error_message=result.error,
        )
    except Exception as exc:
        return _base_result(
            sample_id=sample_id, independent_group=independent_group, mode=mode,
            repeat_index=repeat_index, provider=provider, model=model, temperature=temperature,
            started_at=started_at, elapsed_ms=int((time.monotonic() - started) * 1000), success=False,
            analysis_status="failed", overall_score=None, clauses=[], review_reasons={"pipeline": [str(exc)]},
            call_records=[asdict(record) for record in records], input_text=input_text, pricing=pricing,
            error_type=type(exc).__name__, error_message=" ".join(str(exc).split())[:200],
        )


async def run_serial_multi_stage(*args, **kwargs) -> ExperimentRunResult:
    return await _run_multi_stage(*args, mode="serial_multi_stage", **kwargs)


async def run_parallel_multi_stage(*args, **kwargs) -> ExperimentRunResult:
    return await _run_multi_stage(*args, mode="parallel_multi_stage", **kwargs)


async def run_mode(mode: str, *args, **kwargs) -> ExperimentRunResult:
    if mode == "single_pass":
        return await run_single_pass(*args, **kwargs)
    if mode == "serial_multi_stage":
        return await run_serial_multi_stage(*args, **kwargs)
    if mode == "parallel_multi_stage":
        return await run_parallel_multi_stage(*args, **kwargs)
    raise ValueError(f"未知实验模式: {mode}")
