"""分层记忆 dataclass 与配置测试"""

from server.core.memory.models import RetrieveBudget, MemoryHit
from server.config import settings


def test_default_budget_values():
    b = RetrieveBudget.default()
    assert b.max_chars == 3000
    assert b.max_l1 == 8
    assert b.max_l2 == 2
    assert b.max_l3 == 3


def test_memory_hit_fields():
    hit = MemoryHit(layer="l1", id="a1", text="用户是乙方", score=0.9)
    assert hit.layer == "l1"
    assert hit.chars() == len("用户是乙方")


def test_settings_memory_budget():
    assert settings.MEMORY_RETRIEVE_CHAR_BUDGET == 3000
    assert settings.MEMORY_AUTO_ACTIVATE_THRESHOLD == 0.75
