# ClauseLight 论文路线 B 证据台账

> 本台账的基线区块在任务 1 完成时冻结。后续只能追加证据，不得改写、删除或倒填基线事实。

## 不可变基线（2026-08-29）

- 执行日期：`2026-08-29`
- 仓库：`C:\Users\20300\Desktop\clause-light`
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

`contract_type` 只能为 `rental`、`labor`、`service`；`source_kind` 只能为 `txt`、`pdf`、`image`。最小比较样本为 6 个独立文本：租赁、劳动、服务各 2 个。同一独立文本的 PDF/TXT/图片变体必须使用相同 `independent_group`，并且只计数一次。未达到该规则时，实验只能标记为 development-only，不得作跨类型比较结论。

仅允许使用已获授权处理的私有数据；`authorization_note` 必须能说明授权依据。真实合同、个人信息、API key、含合同正文或个人信息的 raw output 均禁止提交到仓库。私有数据应放在仓库外或由忽略规则保护的位置；聚合 Markdown 不得回填合同正文。

## 当前证据登记

| Evidence ID | 等级 | 内容 | 状态/限制 |
|---|---|---|---|
| `CODE-BASELINE-001` | CODE | 本区块记录 2026-08-29 的 HEAD、状态和 Python 基线 | 已冻结；既有用户改动只记录不改动 |
| `TEST-BASELINE-001` | TEST | `pytest`：255 collected，253 passed，2 skipped，23 warnings，exit 0 | 仅证明仓库测试通过，不证明法律准确率 |
| `CODE-CONFIG-001` | CODE | `experiments/contract_pipeline/config.json` 的冻结运行参数 | provider/model lock 为空；不得混用有效配置 |
| `CODE-MANIFEST-001` | CODE | 私有 manifest 的严格字段和 6 文本最低样本规则 | 不满足时仅 development-only |
| `TEST-FORMAT-001` | TEST | 计划执行 JSON 校验与 `git diff --check` | 待本任务完成后登记实际输出 |
| `RUN-<date>-<id>` | RUN | 脱敏实验聚合结果、配置摘要和样本计数 | 每次运行追加真实 ID；不得包含合同正文/个人信息 |
| `HUMAN-<id>` | HUMAN | 未来法律专家 gold label 或独立复核 | 当前不存在；法律准确率未评估 |

## 计划验证命令

从仓库根目录执行并把实际结果关联到证据 ID：

```powershell
python --version                         # CODE-BASELINE-001
git rev-parse HEAD                      # CODE-BASELINE-001
git status --short                      # CODE-BASELINE-001
pytest                                  # TEST-BASELINE-001
python -m json.tool experiments/contract_pipeline/config.json  # TEST-FORMAT-001
python -c "import json; json.loads(open('experiments/contract_pipeline/manifest.example.jsonl', encoding='utf-8').readline())"  # TEST-FORMAT-001
git diff --check                         # TEST-FORMAT-001
```

## 隐私与声明禁令

本项目禁止提交真实合同、API keys、含合同文本或个人信息的 raw outputs；禁止通过 Git 历史、示例文件、聚合结果或日志间接泄露这些内容。除非存在可复核的 HUMAN 证据，禁止声称法律 accuracy、recall、F1、lawyer agreement 或 superiority over humans。`pricing: null` 也不支持零成本或成本优势结论；远程 provider 的价格结论必须引用官方价格快照及其证据 ID。
