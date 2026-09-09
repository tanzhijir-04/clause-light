"""合同主记录、版本、参与方、条款和文件模型。"""

from __future__ import annotations

import uuid

from sqlalchemy import BigInteger, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from server.models.base import Base, TimestampMixin


class Contract(TimestampMixin, Base):
    __tablename__ = "contract_records"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    title: Mapped[str] = mapped_column(String(300))
    contract_type: Mapped[str] = mapped_column(String(80), default="other")
    lifecycle_status: Mapped[str] = mapped_column(String(32), default="draft")


class ContractVersion(TimestampMixin, Base):
    __tablename__ = "contract_versions"
    __table_args__ = (
        UniqueConstraint(
            "contract_id",
            "version_number",
            name="uq_contract_versions_contract_number",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contract_records.id"), index=True
    )
    version_number: Mapped[int]
    text_content: Mapped[str | None] = mapped_column(Text)
    content_sha256: Mapped[str] = mapped_column(String(64), index=True)
    source: Mapped[str] = mapped_column(String(32), default="upload")


class ContractParty(TimestampMixin, Base):
    __tablename__ = "contract_parties"
    __table_args__ = (
        UniqueConstraint(
            "contract_version_id",
            "role",
            "normalized_name",
            name="uq_contract_parties_version_role_name",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    contract_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contract_versions.id"), index=True
    )
    role: Mapped[str] = mapped_column(String(40))
    display_name: Mapped[str] = mapped_column(String(300))
    normalized_name: Mapped[str] = mapped_column(String(300), index=True)


class Clause(TimestampMixin, Base):
    __tablename__ = "contract_clauses"
    __table_args__ = (
        UniqueConstraint(
            "contract_version_id",
            "ordinal",
            name="uq_contract_clauses_version_ordinal",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    contract_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contract_versions.id"), index=True
    )
    ordinal: Mapped[int]
    heading: Mapped[str | None] = mapped_column(String(500))
    body: Mapped[str] = mapped_column(Text)
    source_start: Mapped[int]
    source_end: Mapped[int]
    content_sha256: Mapped[str] = mapped_column(String(64), index=True)


class DocumentAsset(TimestampMixin, Base):
    __tablename__ = "document_assets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    contract_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contract_versions.id"), index=True
    )
    filename: Mapped[str] = mapped_column(String(300))
    media_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    content_sha256: Mapped[str] = mapped_column(String(64), index=True)
    storage_key: Mapped[str] = mapped_column(String(500), unique=True)
    parse_status: Mapped[str] = mapped_column(String(32), default="pending")
