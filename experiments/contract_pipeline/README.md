# Route B contract pipeline experiment

This directory contains the reproducible protocol and non-sensitive example metadata for Route B. The private manifest is `experiments/data/manifest.local.jsonl`; it is intentionally ignored by Git and must be created locally by an authorized operator. The example manifest contains placeholders only and is safe to review or commit.

## Frozen configuration

[`config.json`](./config.json) is frozen for the baseline comparison:

- `modes`: `single_pass`, `serial_multi_stage`, `parallel_multi_stage`.
- `runs_per_sample`: 5; `temperature`: 0.1; `max_retries`: 0.
- `structured_mode`: `json_fallback`; `timeout_seconds`: 600.
- `store_contract_text`: `false`; contract text must not be persisted in experiment results.
- `pricing`: `null`.

`provider_lock` and `model_lock` are empty in the frozen config. An experiment runner must record the effective provider and model in non-sensitive metadata; it must not silently switch providers or models within a comparison. For a remote provider, any cost statement requires an archived snapshot of that provider's official pricing page, with retrieval date and URL, referenced by an evidence ID. For local inference, `pricing: null` means cost is unknown/not assessed; it is not permission to estimate, compare, or claim zero cost.

## Private manifest and sample rule

Create `experiments/data/manifest.local.jsonl` locally, one JSON object per line, with exactly these fields and no additional fields:

```json
{"sample_id":"...","input_path":"...","contract_type":"rental|labor|service","source_kind":"txt|pdf|image","authorization_note":"...","independent_group":"...","contains_personal_data":false}
```

The minimum comparison set is six independent texts: two rental, two labor, and two service texts. PDF, TXT, and image variants of one underlying text must share the same `independent_group` and count as one independent text, even if every variant is run. If this minimum is not met, label the run development-only and make no cross-type comparison claim.

Only use contracts for which the operator has documented authorization to process them. Keep real contracts and any personal data outside the repository; use redacted or synthetic inputs where possible. `input_path` must point to a private local path, not a committed repository path. Never commit the local manifest, real contract files, API keys, or raw outputs containing contract text or personal information.

## Evidence and claims

The evidence ledger is [`docs/论文路线B证据台账-ClauseLight.md`](../../docs/论文路线B证据台账-ClauseLight.md). Every conclusion in the paper must cite one or more ledger evidence IDs. No HUMAN legal-expert gold labels exist for this project, so legal accuracy is unassessed. Do not claim accuracy, recall, F1, lawyer agreement, or superiority over humans without HUMAN-level evidence.

The runner should preserve only redacted, aggregate metadata in `experiments/results/`. Raw results belong under `experiments/results/raw/` and are ignored; nevertheless, do not place contract text or personal information there. The example config, example manifest, code, and aggregated Markdown remain trackable and must not be ignored.

## Planned verification commands

Run these from the repository root and record the outputs in the ledger with the listed evidence IDs:

```powershell
python --version
git rev-parse HEAD
git status --short
pytest
python -m json.tool experiments/contract_pipeline/config.json
python -c "import json; json.loads(open('experiments/contract_pipeline/manifest.example.jsonl', encoding='utf-8').readline())"
git diff --check
```

Suggested IDs are `CODE-CONFIG-001` (frozen config), `CODE-MANIFEST-001` (manifest schema), `TEST-BASELINE-001` (repository tests), `TEST-FORMAT-001` (JSON and whitespace checks), and `RUN-<date>-<id>` for each redacted experiment run. Reserve `HUMAN-<id>` only for a future documented legal-expert annotation process; no such evidence currently exists.
