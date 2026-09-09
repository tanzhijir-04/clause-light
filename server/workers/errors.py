"""Worker 可分类的错误。"""

from __future__ import annotations


class RetryableJobError(RuntimeError):
    """处理器可安全重试的错误。"""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code
