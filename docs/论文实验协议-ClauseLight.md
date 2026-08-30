# ClauseLight Route B 对照实验协议

> 版本：Task 4；冻结日期：2026-08-30。本文是运行前协议，不记录观察结果，也不因结果调整指标。

## 1. 研究问题与比较对象

本实验只回答三个方案在合同审查任务中的：

1. 可运行性与结构化完成情况；
2. 处理开销（分析墙钟时间、调用次数、Token 与可估算费用）；
3. 可复核性与重复输出稳定性。

比较对象为同一份规范化合同全文上的三种执行模式：

- `single_pass`：一次整文结构化审查；
- `serial_multi_stage`：现有五维 Worker 串行调度的多阶段流水线；
- `parallel_multi_stage`：现有五维 Worker 并行调度的多阶段流水线。

这只能支持“完整方案/调度方式的工程比较”，不能据此宣称法律准确率、律师一致率或算法优越性。

## 2. 样本、计划键与运行顺序

正式主样本固定为 6 个独立组：租赁 2 组、劳动 2 组、服务 2 组。每个独立组只选一份主输入；同一合同的 PDF、TXT、图片等格式变体只能作为附加案例，不能增加独立样本数。

计划运行数为 `6 × 3 × 5 = 90` 个计划键。失败键也计入分母。主键为：

`experiment_id / sample_id / mode / repeat_index`

同一合同每轮包含三种模式；重复轮次轮换模式的先后顺序：

`single_pass → serial_multi_stage → parallel_multi_stage`

下一轮左移一位，循环执行。恢复运行只补没有记录的主键；一个键的首次终态（成功或失败）即主结果，不把后续重试并入主分析。

## 3. 输入、模型和执行参数

- 三种模式使用同一次文档解析产生的 `DocumentResult`；全文先规范化，再以同一规范化全文计算 `input_sha256`。
- 每个 sample 只解析一次；解析耗时单列为 `parse_elapsed_ms`。
- 三种模式的 `elapsed_ms` 都从规范化全文就绪后开始，只计分析到结构化结果结束；并行调用的延迟不求和为墙钟时间。
- 所有模型请求必须通过 `ExperimentGateway`，实际 trace 中的 provider、model、temperature 必须与预检锁定值一致。
- `temperature=0.1`，模型请求 `max_retries=0`，结构化路径固定为 `json_fallback`。
- 正式配置中的模式顺序、重复数、温度、重试数、结构化路径和 `store_contract_text=false` 均为冻结门禁；配置不由 runner 静默改写。
- provider/model 在一轮内固定；预检只读取本地配置和处理计划，不发起模型调用。

## 4. 学习状态和可比性边界

正式基线传入 `enable_memory=False`，关闭 MemoryKernel 会话/loadout、冲突工具扩展和分析结束后的 Distill。知识库与法规检索仍按同一固定代码路径执行；正式实验应使用同一规则/法规库快照。该实验不评估自演化记忆收益。

三种模式均使用现有五个风险维度；串行与并行只改变 Worker 调度方式。服务端限流或模型侧异常必须保留为失败/复核状态，不得转换成伪造正文或绿色结果。

## 5. 失败、计时与统计口径

每个 `run_mode` 受 `timeout_seconds` 的 `asyncio.wait_for` 约束。超时、解析失败和结构化失败均写入完整 `ExperimentRunResult`：

`success=false`、`analysis_status=failed`、`overall_score=null`、`clauses=[]`、`error_type` 为异常类型名、`error_message` 为空，并保留已产生的脱敏 trace。解析失败不回退为读取路径文本，也不跳过计划键。

Task 3 的稳定性口径继续适用：只比较同一 `sample_id + mode` 的有效重复；空失败不能算风险等级一致，报告需展示有效对数量和排除量。先展示每合同配对值及描述统计；五次重复不是五个独立合同，不据此进行独立样本显著性检验。失败数、结构化完成率、复核捕获情况和费用缺失均如实保留。

## 6. 费用与预算说明

预检输出计划运行数和已知调用估计。已知调用估计只基于当前代码中可数的请求路径，`max_calls` 不是消费硬上限，不能用它承诺最大账单；冲突、服务端重试或供应商内部行为可能增加实际收费。`max_retries=0` 只表示客户端不主动重试，不代表服务端没有额外收费。

只有在真实 trace 的 input/output Token 均完整，且存在与锁定 provider/model 匹配的完整官方价格快照（币种、输入/输出单价、来源 URL、核验时间）时才估算费用；缺失时为 `null`，禁止填 0。正式远程运行还必须有明确的远程处理授权和费用控制。

## 7. raw 结果白名单与隐私边界

主 JSONL 只保存主键、provider/model/temperature、时间、状态、分数、`input_sha256`、解析耗时、费用、脱敏调用元数据，以及每条 clause 的：

`clause_number / risk_level / analysis_status / needs_review / source_start / source_end`

`call_records` 不保存 `error_message`；`review_reasons` 只保存固定原因码及计数。禁止保存条款 title、risk summary、suggested clause、legal basis、自由文本、异常原句、合同正文或个人信息。`store_contract_text` 仅保留向后兼容的参数名，不改变该白名单。

输入文件、授权依据、API key、私有 manifest 和 raw 输出均不提交。公开报告只能从脱敏聚合结果生成；没有人工法律专家金标准时，不报告 accuracy、recall、F1 或律师一致率。
