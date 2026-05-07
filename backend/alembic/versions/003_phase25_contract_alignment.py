"""Phase 2.5 contract alignment.

Revision ID: 003
Revises: 002
Create Date: 2026-05-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: str = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "leads",
        sa.Column(
            "last_contacted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        "idx_leads_last_contacted_at",
        "leads",
        [sa.text("last_contacted_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_leads_last_contacted_at", table_name="leads")
    op.drop_column("leads", "last_contacted_at")
