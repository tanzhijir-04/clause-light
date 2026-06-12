# 贡献指南

## 开发环境搭建

1. 克隆仓库
2. 创建虚拟环境：`python -m venv .venv`
3. 激活虚拟环境
4. 安装依赖：`pip install -r requirements.txt`
5. 复制配置：`cp .env.example .env`
6. 初始化：`python scripts/init_db.py && python scripts/import_rules.py`

## 代码规范

- Python: type hints + ruff 格式化
- 前端: 纯 HTML/CSS/JS，无框架
- 注释: 中文
- Commit: 中文，使用 feat/fix/docs/refactor/test/chore 前缀

## 知识库规则贡献

规则 JSON 格式：

```json
{
  "id": "G001",
  "category": "通用",
  "rule_text": "规则描述",
  "trigger_keywords": ["关键词1", "关键词2"],
  "risk_level": "red",
  "risk_type": "风险类型",
  "explanation": "通俗解释",
  "legal_basis": "相关法律依据",
  "confidence": 0.9
}
```

提交规则到 `shared/rules/` 目录下对应类型的 JSON 文件中。
