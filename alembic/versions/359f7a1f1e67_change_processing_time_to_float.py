"""change processing time to float

Revision ID: 359f7a1f1e67
Revises: a6b713092ee4
Create Date: 2026-09-13 11:48:55.210234

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "359f7a1f1e67"
down_revision: Union[str, Sequence[str], None] = "a6b713092ee4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Change processing_time from INTEGER to FLOAT."""
    op.alter_column(
        "audit_logs",
        "processing_time",
        existing_type=sa.Integer(),
        type_=sa.Float(),
        existing_nullable=False,
        schema="compliance",
    )


def downgrade() -> None:
    """Change processing_time back from FLOAT to INTEGER."""
    op.alter_column(
        "audit_logs",
        "processing_time",
        existing_type=sa.Float(),
        type_=sa.Integer(),
        existing_nullable=False,
        schema="compliance",
    )