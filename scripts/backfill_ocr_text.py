"""为旧合同补录 ocr_text"""

import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.core.ocr import get_ocr_engine
from server.models.database import async_session_factory, Contract
from sqlalchemy import select

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def backfill():
    """为所有 ocr_text 为空的合同补录原文"""
    ocr = get_ocr_engine()

    async with async_session_factory() as db:
        # 查找所有 ocr_text 为空的合同
        stmt = select(Contract).where(Contract.ocr_text.is_(None))
        result = await db.execute(stmt)
        contracts = result.scalars().all()

        logger.info(f"找到 {len(contracts)} 个需要补录 ocr_text 的合同")

        for contract in contracts:
            if not contract.source_file:
                logger.warning(f"合同 {contract.id} 没有 source_file，跳过")
                continue

            if not os.path.exists(contract.source_file):
                logger.warning(f"合同 {contract.id} 的文件不存在: {contract.source_file}")
                continue

            try:
                logger.info(f"正在处理合同: {contract.title} ({contract.id})")
                ocr_result = await ocr.recognize(contract.source_file)

                if ocr_result and ocr_result.full_text.strip():
                    contract.ocr_text = ocr_result.full_text
                    logger.info(f"  ✓ 保存 ocr_text: {len(ocr_result.full_text)} 字符")
                else:
                    logger.warning(f"  ✗ OCR 结果为空")
            except Exception as e:
                logger.error(f"  ✗ OCR 失败: {e}")

        await db.commit()
        logger.info("补录完成")


if __name__ == "__main__":
    asyncio.run(backfill())
