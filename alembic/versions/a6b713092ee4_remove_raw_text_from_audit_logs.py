"""remove raw text from audit logs

Revision ID: a6b713092ee4
Revises: 742c0cb3f354
Create Date: 2026-09-13

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a6b713092ee4"
down_revision: Union[str, Sequence[str], None] = "742c0cb3f354"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove raw PII text from the audit_logs table."""

    op.drop_column(
        "audit_logs",
        "original_text",
        schema="compliance",
    )


def downgrade() -> None:
    """Restore the original_text column."""

    op.add_column(
        "audit_logs",
        op.Column(
            "original_text",
            op.Text(),
            nullable=True,
        ),
        schema="compliance",
    )