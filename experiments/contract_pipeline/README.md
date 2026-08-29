# Route B contract pipeline experiment

This directory contains the reproducible protocol and non-sensitive example metadata for Route B. The private manifest is `experiments/data/manifest.local.jsonl`; it is intentionally ignored by Git and must be created locally by an authorized operator. The example manifest contains one semantically valid, synthetic placeholder record and is safe to review or commit; it is development-only because it does not meet the six-group comparison minimum.

## Frozen configuration

[`config.json`](./config.json) is frozen for the baseline comparison:

- `modes`: `single_pass`, `serial_multi_stage`, `parallel_multi_stage`.
- `runs_per_sample`: 5; `temperature`: 0.1; `max_retries`: 0.
- `structured_mode`: `json_fallback`; `timeout_seconds`: 600.
- `store_contract_text`: `false`; contract text must not be persisted in experiment results.
- `pricing`: `null`.

`provider_lock` and `model_lock` are empty in the frozen config. An experiment runner must record the effective provider and model in separate, non-sensitive run metadata; it must not silently switch providers or models within a comparison. The config remains the frozen baseline. A formal remote run must reject before any model call unless its separate verified pricing snapshot is a complete object with `currency`, `input_per_million`, `output_per_million`, `official source_url`, and `verified_at`, plus evidence that the snapshot matches the locked provider/model. Remote pricing is populated in that separate verified run metadata/snapshot, never by silently changing this baseline config. For local inference, `pricing: null` means cost is unknown/not assessed; it is not permission to estimate, compare, or claim zero cost.

## Private manifest and sample rule

Create `experiments/data/manifest.local.jsonl` locally, one JSON object per line, with exactly these fields and no additional fields. `source_kind` may be `authorized` for a synthetic/demo placeholder, or `txt`, `pdf`, or `image` for an authorized input variant:

```json
{"sample_id":"demo-rental-01","input_path":"<private-input-path>/demo-rental-01.txt","contract_type":"rental","source_kind":"authorized","authorization_note":"placeholder-authorized-demo-only","independent_group":"demo-rental-01","contains_personal_data":false}
```

The minimum comparison set is six independent texts: two rental, two labor, and two service texts. PDF, TXT, and image variants of one underlying text must share the same `independent_group` and count as one independent text, even if every variant is run. If this minimum is not met, label the run development-only and make no cross-type comparison claim.

Only use contracts for which the operator has documented authorization to process them. Keep real contracts and any personal data outside the repository; use redacted or synthetic inputs where possible. `input_path` must point to a private local path outside the repository, and `authorization_note` must be non-empty and identify the authorization basis. The literal `<private-input-path>` prefix is accepted only for this committed example validation; every real private input file must exist at its private path and have documented authorization before a run. Never commit the local manifest, real contract files, API keys, or raw outputs containing contract text or personal information.

### Manifest validation (fails nonzero on invalid input)

Run the following PowerShell command from the repository root for the private manifest. It uses only the Python standard library, validates every JSONL line, rejects extra/missing fields, checks the allowed values and exact boolean type, rejects repository-local input paths or missing authorization notes, and enforces the formal six-independent-group rule. The example line passes schema validation but must be treated as development-only until a private manifest passes the comparison-set check.

```powershell
@'
import json
import sys
from collections import Counter
from pathlib import Path

path = Path(sys.argv[1])
example_mode = "--example" in sys.argv[2:]
require_comparison_set = "--require-comparison-set" in sys.argv[2:]
fields = {"sample_id", "input_path", "contract_type", "source_kind", "authorization_note", "independent_group", "contains_personal_data"}
contract_types = {"rental", "labor", "service"}
source_kinds = {"authorized", "txt", "pdf", "image"}
repo_root = Path.cwd().resolve()
groups = {}
sample_ids = set()

with path.open(encoding="utf-8") as handle:
    for line_number, raw in enumerate(handle, 1):
        if not raw.strip():
            raise SystemExit(f"line {line_number}: blank lines are not allowed")
        try:
            record = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"line {line_number}: invalid JSON: {exc}")
        if not isinstance(record, dict) or set(record) != fields:
            raise SystemExit(f"line {line_number}: fields must be exactly {sorted(fields)}")
        if record["sample_id"] in sample_ids:
            raise SystemExit(f"line {line_number}: duplicate sample_id")
        sample_ids.add(record["sample_id"])
        if not isinstance(record["sample_id"], str) or not record["sample_id"].strip():
            raise SystemExit(f"line {line_number}: sample_id must be non-empty")
        if record["contract_type"] not in contract_types:
            raise SystemExit(f"line {line_number}: contract_type must be rental, labor, or service")
        if record["source_kind"] not in source_kinds:
            raise SystemExit(f"line {line_number}: source_kind must be authorized, txt, pdf, or image")
        if not isinstance(record["input_path"], str) or not record["input_path"].strip():
            raise SystemExit(f"line {line_number}: input_path must be non-empty")
        if not isinstance(record["authorization_note"], str) or not record["authorization_note"].strip():
            raise SystemExit(f"line {line_number}: authorization_note is required")
        if not isinstance(record["independent_group"], str) or not record["independent_group"].strip():
            raise SystemExit(f"line {line_number}: independent_group must be non-empty")
        if type(record["contains_personal_data"]) is not bool:
            raise SystemExit(f"line {line_number}: contains_personal_data must be boolean")
        input_path = record["input_path"]
        if input_path.startswith("<private-input-path>") and not example_mode:
            raise SystemExit(f"line {line_number}: placeholder input_path is allowed only in example mode")
        if input_path.startswith("<") and not (example_mode and input_path.startswith("<private-input-path>/")):
            raise SystemExit(f"line {line_number}: unsupported placeholder input_path")
        if not input_path.startswith("<private-input-path>/"):
            candidate = Path(input_path).expanduser()
            resolved = candidate.resolve() if candidate.is_absolute() else (repo_root / candidate).resolve()
            if resolved == repo_root or repo_root in resolved.parents:
                raise SystemExit(f"line {line_number}: input_path must be outside the repository")
        group = record["independent_group"]
        previous_type = groups.setdefault(group, record["contract_type"])
        if previous_type != record["contract_type"]:
            raise SystemExit(f"line {line_number}: one independent_group cannot mix contract types")

if require_comparison_set:
    counts = Counter(groups.values())
    if len(groups) < 6 or any(counts[item] < 2 for item in contract_types):
        raise SystemExit("comparison set requires at least 6 independent groups, with 2 rental, 2 labor, and 2 service groups")
print(f"valid: {path} ({len(groups)} independent groups)")
'@ | python - $manifest_path $validator_flags
```

For a private manifest, define `$manifest_path = "experiments/data/manifest.local.jsonl"` and `$validator_flags = @('--require-comparison-set')`, then execute the full block above. For the committed example, define `$manifest_path = "experiments/contract_pipeline/manifest.example.jsonl"` and `$validator_flags = @('--example')`, then execute the same full block. The example accepts only the exact `<private-input-path>/...` sentinel, passes schema validation, and is development-only. A private manifest rejects every placeholder-prefixed path and duplicate `sample_id`; every real `input_path` must exist, remain private, and be authorized before a run. PDF/TXT/image variants of one underlying text must share `independent_group` and count once. If a private manifest has fewer than six independent texts, or fewer than two rental, two labor, and two service groups, do not make a cross-type comparison claim.

## Evidence and claims

The evidence ledger is [`docs/论文路线B证据台账-ClauseLight.md`](../../docs/论文路线B证据台账-ClauseLight.md). Every conclusion in the paper must cite one or more ledger evidence IDs. No HUMAN legal-expert gold labels exist for this project, so legal accuracy is unassessed. Do not claim accuracy, recall, F1, lawyer agreement, or superiority over humans without HUMAN-level evidence.

The runner should preserve only redacted, aggregate metadata in `experiments/results/`. Raw results belong under `experiments/results/raw/` and are ignored; nevertheless, do not place contract text or personal information there. The example config, example manifest, code, and aggregated Markdown remain trackable and must not be ignored. The ignored raw formats are limited to the planned JSONL/CSV result paths.

Task 1 documents the hard remote pricing gate; it does not contain an executable runner or claim that the gate is already enforced here. Task 10's executable runner must enforce the gate before model invocation: formal remote runs must reject unless pricing is complete and verified for the locked provider/model.

## Planned verification commands

Run these from the repository root and record the outputs in the ledger with the listed evidence IDs:

```powershell
python --version
git rev-parse HEAD
git status --short
pytest
python -m json.tool experiments/contract_pipeline/config.json
git diff --check
```

For `TEST-FORMAT-001`, the full embedded validator above was executed twice: once with `$manifest_path = "experiments/contract_pipeline/manifest.example.jsonl"` and `$validator_flags = @('--example')` (schema PASS), and once with the same manifest and `$validator_flags = @('--example', '--require-comparison-set')` (intentional nonzero exit at the six-group gate; development-only). A private formal run uses `$validator_flags = @('--require-comparison-set')` without `--example`, so every placeholder-prefixed path is rejected. Suggested IDs are `CODE-CONFIG-001` (frozen config), `CODE-MANIFEST-001` (manifest schema and validation policy), `TEST-BASELINE-001` (repository tests), `TEST-FORMAT-001` (full config/example JSON validation and `git diff --check`), and `RUN-<date>-<id>` for each redacted experiment run. Reserve `HUMAN-<id>` only for a future documented legal-expert annotation process; no such evidence currently exists.
