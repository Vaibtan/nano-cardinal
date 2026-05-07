"""Core contracts for inbound, signals, sequences, and outreach.

Revision ID: 004
Revises: 003
Create Date: 2026-05-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

from app.embeddings import VECTOR_DIMENSION

revision: str = "004"
down_revision: str = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "inbound_events",
        sa.Column("source_event_id", sa.String(), nullable=True),
    )
    op.add_column(
        "inbound_events",
        sa.Column("event_fingerprint", sa.String(), nullable=True),
    )
    op.create_index(
        "uq_inbound_events_fingerprint",
        "inbound_events",
        ["event_fingerprint"],
        unique=True,
    )
    op.create_index(
        "uq_inbound_source_event_id",
        "inbound_events",
        ["source", "source_event_id"],
        unique=True,
        postgresql_where=sa.text("source_event_id IS NOT NULL"),
    )

    op.add_column(
        "signals",
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW() + INTERVAL '90 days'"),
        ),
    )
    op.create_index(
        "idx_signals_expires_at",
        "signals",
        ["expires_at"],
    )

    op.add_column(
        "lead_sequence_enrollments",
        sa.Column("paused_reason", sa.String(), nullable=True),
    )
    op.add_column(
        "lead_sequence_enrollments",
        sa.Column(
            "paused_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        "idx_enrollments_paused_reason",
        "lead_sequence_enrollments",
        ["sequence_id", "paused_reason"],
        postgresql_where=sa.text("status = 'PAUSED'"),
    )

    op.add_column(
        "outreach_logs",
        sa.Column(
            "delivery_status",
            sa.String(),
            nullable=False,
            server_default="PENDING",
        ),
    )
    op.add_column(
        "outreach_logs",
        sa.Column("error_code", sa.String(), nullable=True),
    )
    op.add_column(
        "outreach_logs",
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.add_column(
        "outreach_logs",
        sa.Column(
            "bounced_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.alter_column(
        "outreach_logs",
        "sent_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=None,
        nullable=True,
    )

    op.create_table(
        "winning_snippets",
        sa.Column(
            "id",
            sa.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("industry", sa.String(), nullable=True),
        sa.Column("persona", sa.String(), nullable=True),
        sa.Column("channel", sa.String(), nullable=True),
        sa.Column("win_rate", sa.Float(), nullable=True),
        sa.Column(
            "embedding",
            Vector(VECTOR_DIMENSION),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "idx_winning_snippets_industry",
        "winning_snippets",
        ["industry"],
    )
    op.create_index(
        "idx_winning_snippets_persona",
        "winning_snippets",
        ["persona"],
    )
    op.create_index(
        "idx_winning_snippets_embedding_hnsw",
        "winning_snippets",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index(
        "idx_winning_snippets_embedding_hnsw",
        table_name="winning_snippets",
    )
    op.drop_index(
        "idx_winning_snippets_persona",
        table_name="winning_snippets",
    )
    op.drop_index(
        "idx_winning_snippets_industry",
        table_name="winning_snippets",
    )
    op.drop_table("winning_snippets")

    op.alter_column(
        "outreach_logs",
        "sent_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )
    op.drop_column("outreach_logs", "bounced_at")
    op.drop_column("outreach_logs", "error_message")
    op.drop_column("outreach_logs", "error_code")
    op.drop_column("outreach_logs", "delivery_status")

    op.drop_index(
        "idx_enrollments_paused_reason",
        table_name="lead_sequence_enrollments",
    )
    op.drop_column("lead_sequence_enrollments", "paused_at")
    op.drop_column("lead_sequence_enrollments", "paused_reason")

    op.drop_index("idx_signals_expires_at", table_name="signals")
    op.drop_column("signals", "expires_at")

    op.drop_index(
        "uq_inbound_source_event_id",
        table_name="inbound_events",
    )
    op.drop_index(
        "uq_inbound_events_fingerprint",
        table_name="inbound_events",
    )
    op.drop_column("inbound_events", "event_fingerprint")
    op.drop_column("inbound_events", "source_event_id")
