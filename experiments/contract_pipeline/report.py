"""Deterministic aggregation for redacted Route B JSONL results."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from statistics import mean, median

from experiments.contract_pipeline.metrics import pairwise_stability, risk_distribution, structured_success_rate, summarize_calls


def _records(path: Path) -> list[dict]:
    result = []
    with path.open(encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, 1):
            if not raw.strip():
                continue
            try:
                item = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"line {line_number}: invalid JSON") from exc
            if not isinstance(item, dict):
                raise ValueError(f"line {line_number}: result must be an object")
            result.append(item)
    return result


def _pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def _p95(values) -> str:
    values = sorted(value for value in values if value is not None)
    if not values:
        return "0.00"
    index = max(0, min(len(values) - 1, int(len(values) * 0.95)))
    return f"{values[index]:.2f}"


def render_report(records: list[dict], *, raw_sha256: str = "", commit: str = "unknown") -> str:
    modes = sorted({item.get("mode", "unknown") for item in records})
    providers = sorted({item.get("provider", "") for item in records if item.get("provider")})
    models = sorted({item.get("model", "") for item in records if item.get("model")})
    temperatures = sorted({item.get("temperature") for item in records if item.get("temperature") is not None})
    calls = [call for item in records for call in (item.get("call_records") or [])]
    call_summary = summarize_calls(calls)
    unknown = sum(risk_distribution(item.get("clauses", [])).get("unknown", 0) for item in records)
    review_runs = sum(bool(item.get("review_reasons")) for item in records)
    failure_types = Counter(
        item.get("error_type") or call.get("error_type")
        for item in records
        for call in ([{}] if item.get("error_type") else (item.get("call_records") or [{}]))
        if item.get("error_type") or call.get("error_type")
    )

    lines = [
        "# ClauseLight 路线 B 实验结果",
        "",
        "> 本报告只汇总脱敏 JSONL 元数据，不包含合同正文或原始 Prompt。未建立专家标注，因此不评价法律判断正确性。",
        "",
        "## 数据与可复现信息",
        "",
        f"- 原始 JSONL SHA-256：{raw_sha256 or '未提供'}",
        f"- 代码提交：{commit}",
        f"- Run 数：{len(records)}；样本数：{len({r.get('sample_id') for r in records})}；独立组数：{len({r.get('independent_group') for r in records})}",
        f"- 模式：{', '.join(modes) or '无'}；provider：{', '.join(providers) or '无'}；model：{', '.join(models) or '无'}",
        f"- 温度：{', '.join(map(str, temperatures)) or '无'}；结构化调用路径：{', '.join(sorted({str(c.get('structured_via', 'unknown')) for c in calls})) or '无'}",
        "- 去重/重复键：(sample_id, mode, repeat_index)；成功记录复跑时跳过，失败记录默认重跑。",
        "",
        "## 各模式运行与调用指标",
        "",
        "| 模式 | Run 数 | 成功率 | 结构化成功率 | 总耗时 ms | 中位耗时 ms | P95 耗时 ms | 输入 Token | 输出 Token | 总 Token | Token 覆盖率 | 估算费用 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for mode in modes:
        group = [item for item in records if item.get("mode") == mode]
        mode_calls = [call for item in group for call in (item.get("call_records") or [])]
        summary = summarize_calls(mode_calls)
        costs = [item.get("estimated_cost") for item in group]
        cost = f"{sum(costs):.6f} {group[0].get('cost_currency', '')}" if costs and all(v is not None for v in costs) else "不可计算"
        success_rate = sum(bool(i.get("success")) for i in group) / len(group) if group else 0
        elapsed = [i.get("elapsed_ms", 0) or 0 for i in group]
        lines.append(
            f"| {mode} | {len(group)} | {_pct(success_rate)} | {_pct(structured_success_rate(group))} | {sum(elapsed)} | {median(elapsed) if elapsed else 0:.2f} | {_p95(elapsed)} | {summary['input_tokens']} | {summary['output_tokens']} | {summary['tokens_used']} | {_pct(summary['token_coverage'])} | {cost} |"
        )
    lines.extend([
        "",
        "## 重复稳定性",
        "",
        "| 模式 | 两两比较数 | 风险等级一致率 | 条款数标准差 | 总体分数标准差 |",
        "|---|---:|---:|---:|---:|",
    ])
    for mode in modes:
        stability = pairwise_stability([item for item in records if item.get("mode") == mode])
        lines.append(f"| {mode} | {stability['comparisons']} | {stability['risk_level_agreement']:.4f} | {stability['clause_count_stddev']:.4f} | {stability['overall_score_stddev']:.4f} |")
    lines.extend([
        "",
        "## 风险、复核与失败状态",
        "",
        f"- unknown 条款数：{unknown}；含人工复核原因的 Run 数：{review_runs}。",
        f"- 失败类型：{', '.join(f'{key}={value}' for key, value in sorted(failure_types.items())) or '无'}。",
        f"- 全部调用：{call_summary['call_count']} 次，成功 {call_summary['success_count']} 次；总延迟 {call_summary['total_latency_ms']} ms，Token 覆盖率 {_pct(call_summary['token_coverage'])}。",
        "- 费用只有在每条调用的输入/输出 Token 和完整官方价格快照均存在时才计算；否则整列标记为“不可计算”，不把缺失 Token 当作零成本。",
        "",
        "## 结论边界",
        "",
        "未建立专家标注，不评价法律判断正确性；不得将失败状态捕获率、结构化成功率或重复稳定性改写为法律准确率、召回率、F1、律师一致率或优于人类的证据。",
        "",
    ])
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Aggregate Route B JSONL results")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--commit", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        source = Path(args.input)
        raw = source.read_bytes()
        records = _records(source)
        commit = args.commit
        if commit is None:
            try:
                commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
            except Exception:
                commit = "unknown"
        Path(args.output).write_text(
            render_report(records, raw_sha256=hashlib.sha256(raw).hexdigest(), commit=commit),
            encoding="utf-8",
        )
        return 0
    except Exception as exc:
        print(f"report failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
