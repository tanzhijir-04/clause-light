"""为知识库规则批量生成 embedding 向量

使用方法：
    cd clause-light
    python scripts/init_rules_embeddings.py

依赖：sentence-transformers（未安装时脚本会提示并退出）
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main():
    # 检查 embedding 模块是否可用
    from server.core.embedding import is_available, encode_single

    if not is_available():
        print("❌ sentence-transformers 未安装，无法生成 embedding")
        print("   请运行: pip install sentence-transformers")
        return

    from server.models.database import KnowledgeRule, async_session_factory, init_db

    await init_db()

    async with async_session_factory() as db:
        from sqlalchemy import select

        stmt = select(KnowledgeRule).where(KnowledgeRule.is_active == True)  # noqa: E712
        result = await db.execute(stmt)
        rules = result.scalars().all()

        if not rules:
            print("知识库为空，无需生成 embedding")
            return

        total = len(rules)
        updated = 0
        skipped = 0

        for i, rule in enumerate(rules, 1):
            # 跳过已有 embedding 的规则
            if rule.embedding:
                skipped += 1
                continue

            # 用规则文本 + 触发关键词一起编码
            text = rule.rule_text
            if rule.trigger_keywords:
                try:
                    keywords = json.loads(rule.trigger_keywords)
                    if keywords:
                        text += " " + " ".join(keywords)
                except (json.JSONDecodeError, TypeError):
                    pass

            vec = encode_single(text)
            if vec is not None:
                rule.embedding = json.dumps(vec, ensure_ascii=False)
                updated += 1
                print(f"[{i}/{total}] ✅ {rule.rule_text[:30]}...")
            else:
                print(f"[{i}/{total}] ❌ 编码失败: {rule.rule_text[:30]}...")

        await db.commit()

    print(f"\n完成: 共 {total} 条规则，新增 {updated} 条 embedding，跳过 {skipped} 条")


if __name__ == "__main__":
    asyncio.run(main())
