"""Personalization contract fixes.

Revision ID: 005
Revises: 004
Create Date: 2026-05-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: str = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("uq_inbound_events_fingerprint", table_name="inbound_events")
    op.create_index(
        "uq_inbound_events_fingerprint",
        "inbound_events",
        ["event_fingerprint"],
        unique=True,
        postgresql_where=sa.text("event_fingerprint IS NOT NULL"),
    )

    op.alter_column(
        "winning_snippets",
        "win_rate",
        new_column_name="reply_rate",
        existing_type=sa.Float(),
    )
    op.add_column(
        "winning_snippets",
        sa.Column("subject_line", sa.String(), nullable=True),
    )
    op.add_column(
        "winning_snippets",
        sa.Column("hook_type", sa.String(), nullable=True),
    )
    op.add_column(
        "winning_snippets",
        sa.Column("role_seniority", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("winning_snippets", "role_seniority")
    op.drop_column("winning_snippets", "hook_type")
    op.drop_column("winning_snippets", "subject_line")
    op.alter_column(
        "winning_snippets",
        "reply_rate",
        new_column_name="win_rate",
        existing_type=sa.Float(),
    )

    op.drop_index("uq_inbound_events_fingerprint", table_name="inbound_events")
    op.create_index(
        "uq_inbound_events_fingerprint",
        "inbound_events",
        ["event_fingerprint"],
        unique=True,
    )
