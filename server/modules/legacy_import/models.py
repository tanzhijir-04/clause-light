"""v1 导入批次和旧新 ID 映射模型。"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from server.models.base import Base, TimestampMixin


class ImportBatch(TimestampMixin, Base):
    __tablename__ = "import_batches"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_sha256: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(24), default="running")
    counts: Mapped[dict] = mapped_column(JSON, default=dict)


class LegacyIdMap(Base):
    __tablename__ = "legacy_id_maps"
    __table_args__ = (
        UniqueConstraint(
            "batch_id",
            "entity_type",
            "legacy_id",
            name="uq_legacy_id_maps_source",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("import_batches.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(80))
    legacy_id: Mapped[str] = mapped_column(String(120))
    new_id: Mapped[uuid.UUID]
