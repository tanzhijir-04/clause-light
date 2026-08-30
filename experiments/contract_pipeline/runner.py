"""CLI runner for the privacy-preserving Route B comparison."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

from experiments.contract_pipeline.baselines import failed_result, run_mode
from experiments.contract_pipeline.policy import (
    EXPERIMENT_MAX_RETRIES,
    EXPERIMENT_TEMPERATURE,
    MODE_ORDER,
    STRUCTURED_MODE,
    ExperimentGateway,
    rotate_modes,
)
from server.core.document_ingress import ingest
from server.core.llm import LLMCallRecord, LLMGateway
from server.core.workers.parser import normalize_contract_text

FIELDS = {
    "sample_id", "input_path", "contract_type", "source_kind",
    "authorization_note", "independent_group", "contains_personal_data",
}
CONTRACT_TYPES = {"rental", "labor", "service"}
SOURCE_KINDS = {"authorized", "txt", "pdf", "image"}
EXAMPLE_SENTINEL = "<private-input-path>/demo-rental-01.txt"
TYPE_HINTS = {"rental": "租赁合同", "labor": "劳动合同", "service": "服务合同"}
MODE_MAX_CALLS = {
    "single_pass": 1,
    "serial_multi_stage": 9,
    "parallel_multi_stage": 9,
}


def load_manifest(path: str | Path, *, require_comparison_set: bool = True) -> list[dict]:
    path = Path(path)
    repo_root = Path.cwd().resolve()
    records: list[dict] = []
    sample_ids: set[str] = set()
    groups: dict[str, str] = {}
    example_mode = path.name == "manifest.example.jsonl"
    with path.open(encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, 1):
            if not raw.strip():
                raise ValueError(f"line {line_number}: blank lines are not allowed")
            try:
                record = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"line {line_number}: invalid JSON: {exc}") from exc
            if not isinstance(record, dict) or set(record) != FIELDS:
                raise ValueError(f"line {line_number}: fields must be exactly {sorted(FIELDS)}")
            for field in ("sample_id", "input_path", "authorization_note", "independent_group"):
                if not isinstance(record[field], str) or not record[field].strip():
                    raise ValueError(f"line {line_number}: {field} must be non-empty")
            if record["sample_id"] in sample_ids:
                raise ValueError(f"line {line_number}: duplicate sample_id")
            sample_ids.add(record["sample_id"])
            if record["contract_type"] not in CONTRACT_TYPES:
                raise ValueError(f"line {line_number}: contract_type must be rental, labor, or service")
            if record["source_kind"] not in SOURCE_KINDS:
                raise ValueError(f"line {line_number}: unsupported source_kind")
            if type(record["contains_personal_data"]) is not bool:
                raise ValueError(f"line {line_number}: contains_personal_data must be boolean")
            input_path = record["input_path"]
            if not (input_path == EXAMPLE_SENTINEL and example_mode):
                candidate = Path(input_path).expanduser()
                lexical = Path(os.path.normpath(str(candidate if candidate.is_absolute() else repo_root / candidate)))
                if lexical == repo_root or repo_root in lexical.parents:
                    raise ValueError(f"line {line_number}: input_path must be outside the repository")
                resolved = candidate.resolve() if candidate.is_absolute() else (repo_root / candidate).resolve()
                if resolved == repo_root or repo_root in resolved.parents or not resolved.is_file():
                    raise ValueError(f"line {line_number}: input_path must resolve to an existing private file")
            group = record["independent_group"]
            previous = groups.setdefault(group, record["contract_type"])
            if previous != record["contract_type"]:
                raise ValueError(f"line {line_number}: independent_group cannot mix contract types")
            records.append(record)
    if require_comparison_set:
        counts = Counter(groups.values())
        group_counts = Counter(record["independent_group"] for record in records)
        if (
            len(records) != 6
            or len(groups) != 6
            or any(count != 1 for count in group_counts.values())
            or any(counts[item] != 2 for item in CONTRACT_TYPES)
        ):
            raise ValueError(
                "comparison set requires exactly 6 records and 6 independent groups, "
                "with exactly 2 rental, 2 labor, and 2 service groups; "
                "each independent_group must have exactly one sample/input"
            )
    return records


def _load_config(path: str | Path) -> dict:
    with Path(path).open(encoding="utf-8") as handle:
        config = json.load(handle)
    modes = config.get("modes")
    if not isinstance(modes, list) or not modes or any(mode not in MODE_MAX_CALLS for mode in modes):
        raise ValueError("config.modes must contain valid experiment modes")
    if tuple(modes) != MODE_ORDER:
        raise ValueError("config.modes must use the frozen three-mode order")
    if type(config.get("runs_per_sample")) is not int or config["runs_per_sample"] < 1:
        raise ValueError("config.runs_per_sample must be a positive integer")
    if config["runs_per_sample"] != 5:
        raise ValueError("config.runs_per_sample must be 5 for the frozen comparison")
    if config.get("temperature") != EXPERIMENT_TEMPERATURE:
        raise ValueError("config.temperature must be 0.1 for the frozen experiment")
    if config.get("max_retries") != EXPERIMENT_MAX_RETRIES:
        raise ValueError("config.max_retries must be 0 for the frozen experiment")
    if config.get("structured_mode") != STRUCTURED_MODE:
        raise ValueError("config.structured_mode must be json_fallback for the frozen experiment")
    if config.get("store_contract_text") is not False:
        raise ValueError("config.store_contract_text must be false")
    if not isinstance(config.get("timeout_seconds"), (int, float)) or config["timeout_seconds"] <= 0:
        raise ValueError("config.timeout_seconds must be positive")
    return config


def _pricing_complete(pricing: object, provider: str, model: str) -> bool:
    if not isinstance(pricing, dict):
        return False
    required = ("currency", "input_per_million", "output_per_million", "source_url", "verified_at", "provider", "model")
    return all(pricing.get(key) not in (None, "") for key in required) and pricing["provider"] == provider and pricing["model"] == model


def preflight(records: list[dict], config: dict, gateway: LLMGateway | None = None, *, allow_remote: bool = False) -> tuple[str, str, str]:
    if gateway is None:
        gateway = ExperimentGateway(
            provider_lock=config.get("provider_lock") or None,
            model_lock=config.get("model_lock") or None,
        )
    plan = gateway.get_processing_plan(task="analysis")
    provider_lock = config.get("provider_lock") or ""
    model_lock = config.get("model_lock") or ""
    if provider_lock and provider_lock != plan.provider:
        raise ValueError("provider_lock 与实际 processing plan provider 不一致")
    if model_lock and model_lock != plan.model:
        raise ValueError("model_lock 与实际 processing plan model 不一致")
    provider = provider_lock or plan.provider
    model = model_lock or plan.model
    if not provider or not model or plan.processing_mode == "unavailable":
        raise ValueError("锁定的 provider/model 不可用")
    if plan.processing_mode == "remote":
        if not allow_remote:
            raise PermissionError("检测到远程模型；必须显式传入 --allow-remote-processing")
        if not _pricing_complete(config.get("pricing"), provider, model):
            raise ValueError("远程正式实验缺少与锁定 provider/model 匹配的完整官方价格快照")
    groups = len({record["independent_group"] for record in records})
    type_count = len({record["contract_type"] for record in records})
    planned_runs = len(records) * len(config["modes"]) * config["runs_per_sample"]
    known_call_estimate = (
        sum(MODE_MAX_CALLS[mode] for mode in config["modes"])
        * len(records)
        * config["runs_per_sample"]
    )
    print(f"independent_groups={groups} contract_types={type_count} runs_per_sample={config['runs_per_sample']}")
    print(
        f"provider={provider} model={model} processing_mode={plan.processing_mode} "
        f"planned_runs={planned_runs} known_call_estimate={known_call_estimate}"
    )
    print("known_call_estimate_is_not_a_spend_cap=true retries=0_does_not_guarantee_no_server_side_charge=true")
    return provider, model, plan.processing_mode


def _existing_keys(path: Path, include_failed: bool) -> set[tuple]:
    if not path.exists():
        return set()
    keys = set()
    with path.open(encoding="utf-8") as handle:
        for raw in handle:
            try:
                item = json.loads(raw)
            except json.JSONDecodeError:
                continue
            key = (item.get("experiment_id"), item.get("sample_id"), item.get("mode"), item.get("repeat_index"))
            keys.add(key)
    return keys


def _trace_dicts(records: list[LLMCallRecord]) -> list[dict]:
    return [record.__dict__.copy() for record in records]


def _protocol_failure(result, provider: str, model: str):
    """将实际 trace 与预检锁定值比较；不泄露请求内容。"""
    records = getattr(result, "call_records", [])
    if not records:
        result.success = False
        result.analysis_status = "failed"
        result.overall_score = None
        result.clauses = []
        result.review_reasons = {"pipeline": ["ProtocolViolation"]}
        result.error_type = "ProtocolViolation"
        result.error_message = ""
        return result
    for record in records:
        if (
            record.get("provider") != provider
            or record.get("model") != model
            or record.get("temperature") != EXPERIMENT_TEMPERATURE
        ):
            result.success = False
            result.analysis_status = "failed"
            result.overall_score = None
            result.clauses = []
            result.review_reasons = {"pipeline": ["ProtocolViolation"]}
            result.error_type = "ProtocolViolation"
            result.error_message = ""
            return result
    return result


async def _run(args, records, config, provider, model):
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    experiment_id = "route-b-" + hashlib.sha256(
        json.dumps(config, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    existing = _existing_keys(output, args.include_failed)
    with output.open("a", encoding="utf-8") as handle:
        for record in records:
            parse_started = asyncio.get_running_loop().time()
            document_result = None
            input_text = ""
            parse_error = None
            try:
                document_result = await ingest(record["input_path"])
                input_text = normalize_contract_text(document_result.full_text)
                if not input_text.strip():
                    raise ValueError("document text is empty")
                document_result.full_text = input_text
            except Exception as exc:
                parse_error = exc
            parse_elapsed_ms = int((asyncio.get_running_loop().time() - parse_started) * 1000)

            for repeat_index in range(1, config["runs_per_sample"] + 1):
                for mode in rotate_modes(config["modes"], repeat_index):
                    # experiment_id is generated by the result; resume matching uses the stable tuple below.
                    stable_key = (experiment_id, record["sample_id"], mode, repeat_index)
                    if stable_key in existing:
                        continue
                    trace_records = []
                    gateway = ExperimentGateway(
                        trace_sink=trace_records.append,
                        provider_lock=provider,
                        model_lock=model,
                    )
                    if parse_error is not None:
                        result = failed_result(
                            sample_id=record["sample_id"],
                            independent_group=record["independent_group"],
                            mode=mode,
                            repeat_index=repeat_index,
                            provider=provider,
                            model=model,
                            temperature=EXPERIMENT_TEMPERATURE,
                            input_text=input_text,
                            parse_elapsed_ms=parse_elapsed_ms,
                            error_type=type(parse_error).__name__,
                            call_records=_trace_dicts(trace_records),
                            pricing=config.get("pricing"),
                        )
                        protocol_check = False
                    else:
                        protocol_check = True
                        analysis_started = time.monotonic()
                        try:
                            run_input = input_text if mode == "single_pass" else record["input_path"]
                            run_kwargs = {
                                "sample_id": record["sample_id"],
                                "independent_group": record["independent_group"],
                                "repeat_index": repeat_index,
                                "temperature": EXPERIMENT_TEMPERATURE,
                                "pricing": config.get("pricing"),
                                "parse_elapsed_ms": parse_elapsed_ms,
                            }
                            if mode != "single_pass":
                                run_kwargs["document_result"] = document_result
                            result = await asyncio.wait_for(
                                run_mode(mode, run_input, gateway, **run_kwargs),
                                timeout=config["timeout_seconds"],
                            )
                        except Exception as exc:
                            result = failed_result(
                                sample_id=record["sample_id"],
                                independent_group=record["independent_group"],
                                mode=mode,
                                repeat_index=repeat_index,
                                provider=provider,
                                model=model,
                                temperature=EXPERIMENT_TEMPERATURE,
                                input_text=input_text,
                                elapsed_ms=max(1, int((time.monotonic() - analysis_started) * 1000)),
                                parse_elapsed_ms=parse_elapsed_ms,
                                error_type=type(exc).__name__,
                                call_records=_trace_dicts(trace_records),
                                pricing=config.get("pricing"),
                            )
                            protocol_check = False
                    if protocol_check:
                        result = _protocol_failure(result, provider, model)
                    result.experiment_id = experiment_id
                    handle.write(json.dumps(result.to_dict(False), ensure_ascii=False) + "\n")
                    handle.flush()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Route B contract comparison")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", default="experiments/results/raw/route-b.jsonl")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--allow-remote-processing", action="store_true")
    parser.add_argument("--include-failed", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        records = load_manifest(args.manifest)
        config = _load_config(args.config)
        provider, model, mode = preflight(records, config, allow_remote=args.allow_remote_processing)
        if args.check_only:
            return 0
        asyncio.run(_run(args, records, config, provider, model))
        return 0
    except Exception as exc:
        print(f"preflight/run failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
