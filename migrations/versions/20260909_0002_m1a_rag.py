"""m1a rag knowledge documents and chunks

Revision ID: 20260909_0002
Revises: 20260909_0001
Create Date: 2026-09-09
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260909_0002"
down_revision: Union[str, None] = "20260909_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_key", sa.String(length=500), nullable=False),
        sa.Column("source_title", sa.String(length=300), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_documents")),
        sa.UniqueConstraint(
            "source_key",
            "content_sha256",
            name="uq_knowledge_documents_source_hash",
        ),
    )
    op.create_index(
        op.f("ix_knowledge_documents_content_sha256"),
        "knowledge_documents",
        ["content_sha256"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_documents_organization_id"),
        "knowledge_documents",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_documents_status"),
        "knowledge_documents",
        ["status"],
        unique=False,
    )

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("heading", sa.String(length=500), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_start", sa.Integer(), nullable=False),
        sa.Column("source_end", sa.Integer(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("embedding_json", sa.JSON(), nullable=True),
        sa.Column("embedding_model", sa.String(length=160), nullable=True),
        sa.Column("visibility", sa.String(length=24), nullable=False),
        sa.Column("acl_json", sa.JSON(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["knowledge_documents.id"],
            name=op.f("fk_knowledge_chunks_document_id_knowledge_documents"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_chunks")),
        sa.UniqueConstraint(
            "document_id",
            "ordinal",
            name="uq_knowledge_chunks_document_ordinal",
        ),
    )
    for column in (
        "document_id",
        "organization_id",
        "content_sha256",
        "visibility",
    ):
        op.create_index(
            op.f(f"ix_knowledge_chunks_{column}"),
            "knowledge_chunks",
            [column],
            unique=False,
        )


def downgrade() -> None:
    for column in (
        "visibility",
        "content_sha256",
        "organization_id",
        "document_id",
    ):
        op.drop_index(op.f(f"ix_knowledge_chunks_{column}"), table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")

    for column in ("status", "organization_id", "content_sha256"):
        op.drop_index(
            op.f(f"ix_knowledge_documents_{column}"),
            table_name="knowledge_documents",
        )
    op.drop_table("knowledge_documents")
