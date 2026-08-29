"""CLI runner for the privacy-preserving Route B comparison."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path

from experiments.contract_pipeline.baselines import run_mode
from server.core.document_ingress import ingest
from server.core.llm import LLMGateway

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
        if len(groups) < 6 or any(counts[item] < 2 for item in CONTRACT_TYPES):
            raise ValueError("comparison set requires at least 6 independent groups, with 2 rental, 2 labor, and 2 service groups")
    return records


def _load_config(path: str | Path) -> dict:
    with Path(path).open(encoding="utf-8") as handle:
        config = json.load(handle)
    modes = config.get("modes")
    if not isinstance(modes, list) or not modes or any(mode not in MODE_MAX_CALLS for mode in modes):
        raise ValueError("config.modes must contain valid experiment modes")
    if type(config.get("runs_per_sample")) is not int or config["runs_per_sample"] < 1:
        raise ValueError("config.runs_per_sample must be a positive integer")
    return config


def _pricing_complete(pricing: object, provider: str, model: str) -> bool:
    if not isinstance(pricing, dict):
        return False
    required = ("currency", "input_per_million", "output_per_million", "source_url", "verified_at", "provider", "model")
    return all(pricing.get(key) not in (None, "") for key in required) and pricing["provider"] == provider and pricing["model"] == model


def preflight(records: list[dict], config: dict, gateway: LLMGateway | None = None, *, allow_remote: bool = False) -> tuple[str, str, str]:
    if gateway is None:
        gateway = LLMGateway(
            provider_lock=config.get("provider_lock") or None,
            model_lock=config.get("model_lock") or None,
            structured_mode=config.get("structured_mode", "auto"),
        )
    plan = gateway.get_processing_plan(task="analysis")
    provider = config.get("provider_lock") or plan.provider
    model = config.get("model_lock") or plan.model
    if not provider or not model or plan.processing_mode == "unavailable":
        raise ValueError("锁定的 provider/model 不可用")
    if plan.processing_mode == "remote":
        if not allow_remote:
            raise PermissionError("检测到远程模型；必须显式传入 --allow-remote-processing")
        if not _pricing_complete(config.get("pricing"), provider, model):
            raise ValueError("远程正式实验缺少与锁定 provider/model 匹配的完整官方价格快照")
    groups = len({record["independent_group"] for record in records})
    type_count = len({record["contract_type"] for record in records})
    max_calls = sum(MODE_MAX_CALLS[mode] for mode in config["modes"]) * len(records) * config["runs_per_sample"]
    print(f"independent_groups={groups} contract_types={type_count} runs_per_sample={config['runs_per_sample']}")
    print(f"provider={provider} model={model} processing_mode={plan.processing_mode} max_calls={max_calls}")
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
            if include_failed or item.get("success"):
                keys.add(key)
    return keys


async def _run(args, records, config, provider, model):
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    experiment_id = "route-b-" + hashlib.sha256(
        json.dumps(config, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    existing = _existing_keys(output, args.include_failed)
    with output.open("a", encoding="utf-8") as handle:
        for record in records:
            for mode in config["modes"]:
                for repeat_index in range(1, config["runs_per_sample"] + 1):
                    # experiment_id is generated by the result; resume matching uses the stable tuple below.
                    stable_key = (experiment_id, record["sample_id"], mode, repeat_index)
                    if stable_key in existing:
                        continue
                    trace_records = []
                    gateway = LLMGateway(
                        trace_sink=trace_records.append,
                        provider_lock=provider,
                        model_lock=model,
                        structured_mode=config.get("structured_mode", "auto"),
                    )
                    if mode == "single_pass":
                        try:
                            input_text = (await ingest(record["input_path"])).full_text
                        except Exception:
                            input_text = Path(record["input_path"]).read_text(encoding="utf-8")
                        result = await run_mode(
                            mode, input_text, gateway,
                            sample_id=record["sample_id"],
                            independent_group=record["independent_group"],
                            repeat_index=repeat_index,
                            temperature=config.get("temperature", 0.1),
                            pricing=config.get("pricing"),
                        )
                    else:
                        result = await run_mode(
                            mode, record["input_path"], gateway,
                            sample_id=record["sample_id"],
                            independent_group=record["independent_group"],
                            repeat_index=repeat_index,
                            temperature=config.get("temperature", 0.1),
                            pricing=config.get("pricing"),
                        )
                    result.experiment_id = experiment_id
                    handle.write(json.dumps(result.to_dict(config.get("store_contract_text", False)), ensure_ascii=False) + "\n")
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
