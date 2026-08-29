# ClauseLight 论文路线 B 证据台账

> 本台账的基线区块在任务 1 完成时冻结。后续只能追加证据，不得改写、删除或倒填基线事实。

## 不可变基线（2026-08-29）

- 执行日期：`2026-08-29`
- 仓库：`<repository-root>`（提交文档不记录绝对工作站路径）
- `git rev-parse HEAD`：`769e9b43e53d352bb7df0d4903028d10bc19d462`
- `git status --short`：

  ```text
   M docs/论文初稿-ClauseLight.md
   M docs/论文提纲-ClauseLight.md
   M docs/论文材料盘点-ClauseLight.md
  ?? docs/assets/
  ?? docs/superpowers/plans/2026-08-25-clauselight-md-paper-strengthening.md
  ?? docs/superpowers/plans/2026-08-26-clauselight-chinese-research-paper.md
  ?? docs/superpowers/plans/2026-08-29-clauselight-route-b-paper-validation.md
  ?? docs/论文投稿版-计算机应用文摘-ClauseLight.md
  ```

  以上论文 Markdown、图片资产及相关未提交计划文件均为既有用户改动；本任务只记录，不 reset、覆盖、整理、暂存或提交这些改动。
- Python：`Python 3.12.5`
- 基线测试命令：`pytest`
- 基线测试输出摘要：`255 items collected; 253 passed, 2 skipped, 23 warnings; exit code 0; 61.41s`
- 基线测试警告：包含 Requests 依赖版本警告、Starlette 弃用警告及既有测试中的 RuntimeWarning；警告不改变上述通过/跳过统计。

## 证据等级与编号

证据等级按强度和可复核性分为四级：

- **CODE**：仓库中的可读配置、协议、脚本或实现；证明“写了什么”，不证明法律正确。
- **TEST**：自动化测试及其可复现输出；证明测试覆盖的行为，不等同于真实合同法律准确率。
- **RUN**：按冻结配置和合格 manifest 执行的实验及脱敏聚合结果；证明观察到的运行现象，不自动证明普遍性。
- **HUMAN**：具备资质的法律专家依据预先定义的标注规范形成的独立金标准、复核或一致性证据；目前不存在 HUMAN 法律专家 gold labels。

因此，截至本台账建立日，法律准确率（以及 recall、F1、律师一致率）均未评估。不得在论文或摘要中声称准确率、召回率、F1、律师一致、或优于人类，除非对应结论有 HUMAN 证据支持。论文的每一条结论、比较结论和定量结论都必须在句末或表格注释中指向一个或多个本台账证据 ID；没有证据 ID 的内容只能写成待验证假设。

## 实验数据规则

私有 manifest 的路径固定为 `experiments/data/manifest.local.jsonl`，且必须被 Git 忽略。每行必须是 JSON 对象，并且严格只含以下字段：

`sample_id`, `input_path`, `contract_type`, `source_kind`, `authorization_note`, `independent_group`, `contains_personal_data`

`contract_type` 只能为 `rental`、`labor`、`service`；`source_kind` 只能为 `authorized`（合成/演示占位）或 `txt`、`pdf`、`image`。最小比较样本为 6 个独立文本：租赁、劳动、服务各 2 个。同一独立文本的 PDF/TXT/图片变体必须使用相同 `independent_group`，并且只计数一次。未达到该规则时，实验只能标记为 development-only，不得作跨类型比较结论。

仅允许使用已获授权处理的私有数据；`authorization_note` 必须非空并能说明授权依据，`input_path` 必须指向仓库外的私有路径。字面量 `<private-input-path>` 前缀只允许在已提交的 example 校验模式中出现；真实私有输入文件必须实际存在于私有路径，并在运行前有授权记录。真实合同、个人信息、API key、含合同正文或个人信息的 raw output 均禁止提交到仓库。私有数据应放在仓库外或由忽略规则保护的位置；聚合 Markdown 不得回填合同正文。

### Manifest 标准库校验

校验器先确认 `sample_id` 是非空字符串，再进行重复追踪；私有/非示例路径必须解析为仓库外已存在的普通文件（`is_file()`）。`--example` 模式只接受精确的 `<private-input-path>/demo-rental-01.txt` 哨兵。

从仓库根目录执行以下命令。它逐行解析 JSONL，严格检查 7 个字段、允许的合同类型/来源类型、`contains_personal_data` 的严格布尔类型、授权说明和仓库外路径，并在 `--require-comparison-set` 下强制 6 个独立组及每类 2 组；任一错误均以非零状态退出。PDF/TXT/图片变体共用 `independent_group`，只计一个独立文本。

```powershell
@'
import json
import os
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
example_sentinel = "<private-input-path>/demo-rental-01.txt"
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
        if not isinstance(record["sample_id"], str) or not record["sample_id"].strip():
            raise SystemExit(f"line {line_number}: sample_id must be non-empty")
        if record["sample_id"] in sample_ids:
            raise SystemExit(f"line {line_number}: duplicate sample_id")
        sample_ids.add(record["sample_id"])
        if not isinstance(record["contract_type"], str) or record["contract_type"] not in contract_types:
            raise SystemExit(f"line {line_number}: contract_type must be rental, labor, or service")
        if not isinstance(record["source_kind"], str) or record["source_kind"] not in source_kinds:
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
        if example_mode and input_path != example_sentinel:
            raise SystemExit(f"line {line_number}: only the exact example sentinel is allowed in example mode")
        if not example_mode and input_path.startswith("<"):
            raise SystemExit(f"line {line_number}: placeholder input_path is allowed only in example mode")
        if input_path != example_sentinel:
            candidate = Path(input_path).expanduser()
            lexical = Path(os.path.normpath(str(candidate if candidate.is_absolute() else repo_root / candidate)))
            if lexical == repo_root or repo_root in lexical.parents:
                raise SystemExit(f"line {line_number}: input_path must be outside the repository")
            resolved = candidate.resolve() if candidate.is_absolute() else (repo_root / candidate).resolve()
            if resolved == repo_root or repo_root in resolved.parents:
                raise SystemExit(f"line {line_number}: input_path must be outside the repository")
            if not resolved.is_file():
                raise SystemExit(f"line {line_number}: input_path must resolve to an existing regular file")
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

对私有 manifest 设置 `$manifest_path = "experiments/data/manifest.local.jsonl"`、`$validator_flags = @('--require-comparison-set')`，再执行上方完整校验器。对提交的示例 manifest 设置 `$manifest_path = "experiments/contract_pipeline/manifest.example.jsonl"`、`$validator_flags = @('--example')`，再执行同一完整校验器；只有精确的 `<private-input-path>/...` 示例哨兵可通过。私有 manifest 不得使用任何占位符前缀，且重复 `sample_id` 必须失败；真实输入文件必须存在于私有路径并已获授权。示例只有一个独立组，所以只能标记 development-only。

两份同步校验器的记录结果：空、null、数字 `sample_id` 均以 `line 1: sample_id must be non-empty` 非零退出；六组但含 phantom 私有输入的 manifest 均以 `line 1: input_path must resolve to an existing regular file` 非零退出。

## 当前证据登记

| Evidence ID | 等级 | 内容 | 状态/限制 |
|---|---|---|---|
| `CODE-BASELINE-001` | CODE | 本区块记录 2026-08-29 的 HEAD、状态和 Python 基线 | 已冻结；既有用户改动只记录不改动 |
| `TEST-BASELINE-001` | TEST | `pytest`：255 collected，253 passed，2 skipped，23 warnings，exit 0 | 仅证明仓库测试通过，不证明法律准确率 |
| `CODE-CONFIG-001` | CODE | `experiments/contract_pipeline/config.json` 的冻结运行参数 | provider/model lock 为空；不得混用有效配置 |
| `CODE-MANIFEST-001` | CODE | 私有 manifest 的严格字段和 6 文本最低样本规则 | 不满足时仅 development-only |
| `TEST-FORMAT-001` | TEST | 已执行配置 JSON 校验、示例 manifest 全行/schema 校验（`--example`）及正式比较门禁校验（`--require-comparison-set`）和 `git diff --check` | 2026-08-29：两份同步校验器均拒绝空/null/数字 `sample_id`，并拒绝不存在的私有输入文件；example schema 校验通过；comparison gate 按预期以非零退出并标记 development-only；`git diff --check` 通过 |
| `RUN-<date>-<id>` | RUN | 脱敏实验聚合结果、配置摘要和样本计数 | 每次运行追加真实 ID；不得包含合同正文/个人信息 |
| `HUMAN-<id>` | HUMAN | 未来法律专家 gold label 或独立复核 | 当前不存在；法律准确率未评估 |

## 已执行与后续验证命令

从仓库根目录执行并把实际结果关联到证据 ID：

```powershell
python --version                         # CODE-BASELINE-001
git rev-parse HEAD                      # CODE-BASELINE-001
git status --short                      # CODE-BASELINE-001
pytest                                  # TEST-BASELINE-001
python -m json.tool experiments/contract_pipeline/config.json  # TEST-FORMAT-001
完整内嵌校验器（上方代码块）设置 `$manifest_path = "experiments/contract_pipeline/manifest.example.jsonl"`、`$validator_flags = @('--example')`后执行  # TEST-FORMAT-001：全行/schema 校验通过
同一完整内嵌校验器设置 `$manifest_path = "experiments/contract_pipeline/manifest.example.jsonl"`、`$validator_flags = @('--example', '--require-comparison-set')`后执行  # TEST-FORMAT-001：六组门禁按预期非零退出，development-only
git diff --check                         # TEST-FORMAT-001
```

## 隐私与声明禁令

本项目禁止提交真实合同、API keys、含合同文本或个人信息的 raw outputs；禁止通过 Git 历史、示例文件、聚合结果或日志间接泄露这些内容。除非存在可复核的 HUMAN 证据，禁止声称法律 accuracy、recall、F1、lawyer agreement 或 superiority over humans。Task 1 只记录硬远程定价门禁，不包含可执行 runner，也不声称本 commit 已经执行该门禁；Task 10 的可执行 runner 必须在任何模型调用前拒绝执行，除非独立运行元数据中的 pricing 是完整对象，包含 `currency`、`input_per_million`、`output_per_million`、官方 `source_url`、`verified_at`，并有与锁定 provider/model 匹配的证据。`config.json` 仍是冻结基线；远程价格只能写入单独的已验证运行元数据/快照，不得静默改变基线。`pricing: null` 对本地推理仍表示不估算成本，不支持零成本或成本优势结论。
