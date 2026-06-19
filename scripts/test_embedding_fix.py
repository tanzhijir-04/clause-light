"""测试 embedding 异步加载修复"""

import asyncio
import time
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_embedding_async():
    """测试异步加载 embedding 模型"""
    from server.core import embedding

    print("=" * 60)
    print("测试 embedding 异步加载")
    print("=" * 60)

    # 测试 1: 同步检查（不应该触发下载）
    print("\n[测试 1] 同步检查 is_available()...")
    start = time.time()
    available = embedding.is_available()
    elapsed = time.time() - start
    print(f"  结果: {available}, 耗时: {elapsed:.3f}s")
    print(f"  预期: False (模型未加载), 实际: {available}")

    # 测试 2: 异步检查（应该触发下载）
    print("\n[测试 2] 异步检查 is_available_async() (首次会下载模型)...")
    start = time.time()
    available = await embedding.is_available_async()
    elapsed = time.time() - start
    print(f"  结果: {available}, 耗时: {elapsed:.3f}s")
    print(f"  预期: True (模型已加载), 实际: {available}")

    # 测试 3: 再次同步检查（应该立即返回）
    print("\n[测试 3] 再次同步检查 is_available()...")
    start = time.time()
    available = embedding.is_available()
    elapsed = time.time() - start
    print(f"  结果: {available}, 耗时: {elapsed:.3f}s")
    print(f"  预期: True (模型已缓存), 实际: {available}")

    # 测试 4: 测试 asyncio.wait_for 超时机制
    print("\n[测试 4] 测试 asyncio.wait_for 超时机制...")
    from server.core.knowledge import KnowledgeEngine
    from server.models.database import async_session_factory

    try:
        async with async_session_factory() as db:
            engine = KnowledgeEngine(db)
            start = time.time()
            # 设置 5 秒超时（模型已加载，应该很快完成）
            result = await asyncio.wait_for(
                engine.search("租赁合同", "租赁合同"),
                timeout=5.0,
            )
            elapsed = time.time() - start
            print(f"  结果: 成功, 耗时: {elapsed:.3f}s, 返回 {len(result)} 条规则")
    except asyncio.TimeoutError:
        print(f"  结果: 超时! 这表明异步修复没有生效")
    except Exception as e:
        print(f"  结果: 异常 - {e}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_embedding_async())
