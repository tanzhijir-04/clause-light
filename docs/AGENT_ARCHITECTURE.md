# ClauseLight Agent 架构设计 & CC 开发提示词

## 一、架构总览：Prompt Chaining + Parallelization Workflow

**选型依据**：合同审查是确定性任务，步骤可预分解，不需要 Full Agent。采用 Anthropic 推荐的 Prompt Chaining + Parallelization 模式，用 Workflow 编排而非 Agent 自主循环。

```
用户上传合同 PDF/图片
        │
        ▼
  ┌─────────────────┐
  │   OCR 识别层     │  PaddleOCR → 原始文本 + 置信度
  └────────┬────────┘
           │
           ▼
  ┌─────────────────┐
  │  Stage 1:       │  结构解析 Worker（1 次 LLM 调用）
  │  条款拆解 + 分类 │  输出：条款数组 + 合同类型 + 模型路由决策
  └────────┬────────┘
           │
     ┌─────┼─────┬──────────┐
     ▼     ▼     ▼          ▼
  ┌─────┐┌─────┐┌─────┐┌─────────┐
  │权责 ││财务 ││ IP  ││ 争议解决 │  Stage 2: 4+1 并行 Worker
  │Worker││Worker││Worker││ Worker  │  （各 1 次 LLM 调用，并发执行）
  └──┬──┘└──┬──┘└──┬──┘└────┬────┘
     │     │     │        │
     └─────┴─────┴────────┘
           │
           ▼
  ┌─────────────────┐
  │  Stage 3:       │  一致性检查 + 聚合评分
  │  Evaluator      │  （1 次 LLM 调用）
  └────────┬────────┘
           │
           ▼
  ┌─────────────────┐
  │  输出渲染层      │  红黄绿标注 + 修改建议 + 用户友好报告
  └─────────────────┘
```

**总 LLM 调用次数**：1（解析）+ 4~5（并行分析）+ 1（聚合）= 6~7 次，其中并行调用的延迟等于单次最慢调用。

---

## 二、各阶段详细设计

### OCR 层

- 使用现有 `server/core/ocr.py`（PaddleOCR 封装），不改动
- **新增**：OCR 完成后检查 `confidence_avg`，低于 0.7 时在结果中标记 `ocr_quality: "low"`，前端提示用户"识别质量较低，建议手动补充"
- OCR 结果作为只读输入传给 Stage 1，不参与后续 LLM 调用

### Stage 1：结构解析 Worker

**职责**：一次 LLM 调用，同时完成合同分类 + 条款拆解 + 模型路由决策。

**输入**：OCR 全文（最多 8000 字符）

**输出**：

```json
{
  "contract_type": "劳动合同",
  "complexity": "standard",
  "recommended_model": "fast",
  "clauses": [
    {
      "id": "3.2",
      "type": "payment",
      "title": "付款条件",
      "text": "甲方应于验收后90日内付款...",
      "relevance": ["equity", "financial"]
    },
    {
      "id": "8.1",
      "type": "liability_cap",
      "title": "赔偿上限",
      "text": "乙方赔偿责任不超过合同总价的5%...",
      "relevance": ["equity", "financial", "dispute"]
    },
    {
      "id": "12.1",
      "type": "force_majeure",
      "title": "不可抗力",
      "text": "因不可抗力导致合同无法履行...",
      "relevance": ["general"]
    }
  ]
}
```

**条款类型枚举**（Stage 1 必须从中选择）：

| type | 说明 | 对应 Worker |
|------|------|------------|
| payment | 付款/结算条件 | financial |
| liability_cap | 赔偿上限/责任限制 | equity, financial |
| penalty | 违约金/赔偿金 | equity, financial |
| confidentiality | 保密义务 | ip |
| ip_ownership | 知识产权归属 | ip |
| non_compete | 竞业限制 | ip, equity |
| termination | 合同解除/终止 | equity, dispute |
| dispute_resolution | 争议解决（仲裁/诉讼） | dispute |
| unilateral | 单方面权利/变更权 | equity |
| warranty | 质保/担保 | equity, financial |
| force_majeure | 不可抗力 | general |
| assignment | 合同转让/分包 | equity |
| other | 其他/未分类 | general |

**`relevance` 字段**决定该条款送哪些 Worker 分析。`general` 类型送通用风险 Worker。

**模型路由逻辑**：
- `complexity: "standard"` + `recommended_model: "fast"` → Stage 2 用轻量模型
- `complexity: "complex"` + `recommended_model: "strong"` → Stage 2 用强模型
- 判断依据：是否出现 `other` 类型条款、条款总数、合同类型是否在常见列表中

### Stage 2：并行风险评估 Worker（4+1）

**5 个 Worker 并发执行**，每个 Worker 只接收与其维度相关的条款。

| Worker | 维度 | 关注点 |
|--------|------|--------|
| equity_worker | 权责对等 | 双方义务是否对等、单方面宽松/严苛、不利方判定 |
| financial_worker | 财务风险 | 付款周期、违约金比例、赔偿上限、滞纳金 |
| ip_worker | 知识产权 | IP 归属、保密义务范围、竞业限制合理性 |
| dispute_worker | 争议解决 | 管辖地、仲裁条款、诉讼成本、举证责任 |
| general_worker | 通用风险 | 不属于上述维度的条款，兜底检查 |

**每个 Worker 的 System Prompt 结构**：

```
## 角色
你是合同审查的{维度}专家。你代表合同的乙方（上传方），从他的利益出发评估风险。

## 输入
你会收到一个条款数组，每个条款有 id、type、text。

## Think 步骤
在给出风险评级前，对每个条款先推理：
1. 该条款对乙方（上传方）的具体影响是什么？
2. 与行业惯例/法律默认条款相比，这个条款是否偏离？偏离方向是什么？
3. 不利方是谁？不利程度如何？

## 评级标准
- red: 条款明确不利于乙方且无对等保护，或违反法律强制性规定
- yellow: 存在不确定性、行业惯例有争议、或轻微不利于乙方
- green: 条款标准且对乙方无明显不利

## 输出格式
对每个条款输出 JSON 对象：
{
  "clause_id": "条款id",
  "risk_level": "red/yellow/green",
  "risk_type": "具体风险类型（如：违约金过高、霸王条款、权责不对等）",
  "issue": "问题描述（一句话）",
  "unfavorable_to": "不利方（甲方/乙方/双方）",
  "severity": 1-10,
  "suggestion": "具体修改方向或替代表述",
  "legal_basis": "相关法律依据（如有）"
}

如某条款在本维度无风险，输出 risk_level: "green"，issue: "本维度无明显风险"。
```

**Worker 输入**：只包含 `relevance` 字段包含该 Worker 维度的条款。减少无关信息，让每个 LLM call 专注。

**Worker 输出**：统一 JSON 数组格式。

### Stage 3：Evaluator 一致性检查 + 聚合评分

**职责**（单次 LLM 调用）：

1. **冲突检测**：同一条款在不同 Worker 间 risk_level 不一致时（如 equity_worker 评 red，financial_worker 评 green），标记为 `needs_review`
2. **聚合评分**：
   - 统计 red/yellow/green 分布
   - 计算综合风险分（0-100）
   - 生成一句话总结
   - 给出推荐操作：sign / negotiate_first / reject
3. **补充建议**：对所有 red 条款生成谈判话术

**不做的事**：不做循环迭代，一次检查够了。跨条款的逻辑关系（如条款 A 的违约金和条款 B 的责任上限矛盾）在 summary 中自然体现即可，不需要 Evaluator 专门处理。

**输出**：

```json
{
  "overall_score": 42,
  "risk_distribution": { "red": 3, "yellow": 5, "green": 8 },
  "recommendation": "negotiate_first",
  "one_line_summary": "该合同存在3处高风险条款，建议重点协商赔偿上限和违约金条款后再签署",
  "needs_review": ["8.1"],
  "top_risks": [
    "第8.1条赔偿上限仅5%，远低于行业惯例",
    "第5.3条甲方单方面解除权无对等限制",
    "第9.2条违约金按日0.5%计算，年化超180%"
  ]
}
```

### 输出渲染层

前端根据 Stage 2 + Stage 3 的结果渲染：
- 条款列表：按风险等级排序（red → yellow → green），每条显示风险标注、问题描述、修改建议
- 总览卡片：红黄绿数量、综合分数、推荐操作
- `needs_review` 的条款加特殊标记"需人工复核"
- 展示 LLM 的 think 推理过程（可折叠），增加用户信任感

---

## 三、知识库集成方式

知识库检索**不放在 Worker 里**，而是在 Stage 1 完成后、Stage 2 开始前，做一次统一检索。

```
Stage 1 输出条款数组
        │
        ▼
[知识库检索] ──→ 按合同类型 + 条款类型，检索 top-5 相关规则和法规
        │
        ▼
Stage 2 每个 Worker 的 prompt 里注入检索到的规则作为参考
```

这样 Worker 不需要自己检索，职责单一：只做分析。

---

## 四、错误降级策略

| 阶段 | 失败情况 | 降级方案 |
|------|----------|----------|
| OCR | 识别失败或置信度 < 0.5 | 返回错误，提示用户重新上传 |
| Stage 1 | LLM 调用失败 | 重试 1 次，仍失败则用规则引擎兜底（按标号正则拆条款） |
| Stage 1 | JSON 解析失败 | 用正则提取条款编号，全文作为一个条款继续 |
| Stage 2 | 单个 Worker 失败 | 该维度所有条款标为 green（未分析），其余 Worker 继续 |
| Stage 2 | 部分条款无 Worker 覆盖 | general_worker 兜底 |
| Stage 3 | 聚合失败 | 从 Stage 2 结果直接统计红黄绿数量，跳过评分 |
| 全局 | 所有 LLM 调用失败 | 返回"服务暂时不可用"，提示用户稍后重试 |

---

## 五、文件结构变更

在现有 `server/core/` 下新增：

```
server/core/
├── agent.py              # 重写：Pipeline 编排器（替代现有 7 步流程）
├── workers/
│   ├── __init__.py
│   ├── parser.py         # Stage 1: 结构解析 Worker
│   ├── equity.py         # Stage 2: 权责对等 Worker
│   ├── financial.py      # Stage 2: 财务风险 Worker
│   ├── ip.py             # Stage 2: 知识产权 Worker
│   ├── dispute.py        # Stage 2: 争议解决 Worker
│   ├── general.py        # Stage 2: 通用风险 Worker（兜底）
│   └── evaluator.py      # Stage 3: 一致性检查 + 聚合评分
├── prompts/
│   ├── parser_system.py      # Stage 1 system prompt
│   ├── worker_system.py      # Stage 2 通用 system prompt 模板（参数化维度）
│   ├── evaluator_system.py   # Stage 3 system prompt
│   └── ...（保留现有 prompt 文件作为 fallback）
```

**现有文件改动**：
- `server/core/agent.py`：重写为 Pipeline 编排器，保留 `ContractAgent` 类名和 `analyze()` 方法签名
- `server/core/llm.py`：新增 `chat_with_tools()` 方法（支持 function calling 的场景预留），现有 `chat()` 保持不变
- `server/api/contracts.py`：调用方式不变（仍调用 `ContractAgent.analyze()`）
- `server/api/ws.py`：`on_step` 回调语义不变（步骤编号调整为新的阶段）

**不改动的文件**：
- `server/core/ocr.py`：不动
- `server/core/knowledge.py`：不动，由 agent.py 调用其 `search()` 方法
- `server/models/database.py`：不动
- 前端文件：不动（API 返回格式兼容）
- `mobile/`：不动

---

## 六、LLM 调用预算

| 阶段 | 调用次数 | 并发 | 预估延迟（含重试） |
|------|----------|------|-------------------|
| Stage 1 解析 | 1 | - | 2-4s |
| 知识库检索 | 0（非 LLM） | - | <0.1s |
| Stage 2 分析 | 4-5 | 并行 | 3-6s（取决于最慢的 Worker） |
| Stage 3 聚合 | 1 | - | 2-4s |
| **总计** | **6-7** | - | **8-15s** |

对比现有方案（Step 5 串行分析 N 条条款）：如果合同有 10 条条款，现有方案需要 10 次串行 LLM 调用，延迟 20-40s。新方案固定 4-5 次并行调用，延迟大幅降低。

---

## 七、后续可扩展点（本次不实现，仅预留）

1. **Evaluator 循环迭代**：如果一致性检查发现严重冲突，可以让相关 Worker 重新分析（需要改 agent.py 为 loop 结构）
2. **用户反馈学习**：用户对评级结果的修正可以反馈到知识库（`auto_learned` 来源）
3. **多合同对比**：同一份合同不同版本的风险对比
4. **Agent 模式升级**：当需要处理开放式问题（如"这份合同适不适合我的业务场景"）时，再升级为 Full Agent Loop
