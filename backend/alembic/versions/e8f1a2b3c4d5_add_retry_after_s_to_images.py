"""Add retry_after_s to images for quota-exhausted UX

Revision ID: e8f1a2b3c4d5
Revises: b6313dcecc7d
Create Date: 2026-08-09 22:58:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e8f1a2b3c4d5"
down_revision: Union[str, None] = "b6313dcecc7d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("images", sa.Column("retry_after_s", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("images", "retry_after_s")
