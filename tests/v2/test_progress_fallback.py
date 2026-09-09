from __future__ import annotations

import pytest

from server.platform.progress import ProgressPublisher


@pytest.mark.asyncio
async def test_progress_falls_back_without_losing_final_state() -> None:
    publisher = ProgressPublisher(redis_client=None)
    await publisher.publish("job-1", {"status": "running", "percent": 40})
    assert publisher.local_snapshot("job-1") == {"status": "running", "percent": 40}
