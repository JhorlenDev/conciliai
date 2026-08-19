"""Allow statement movements to be ignored in a period.

Revision ID: 0031_movement_period_ignore
Revises: 0030_rule_exclusion_text
Create Date: 2026-08-19 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0031_movement_period_ignore"
down_revision = "0030_rule_exclusion_text"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "movimentos_extrato",
        sa.Column("ignorado_no_periodo", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("movimentos_extrato", "ignorado_no_periodo", server_default=None)
    op.create_index("ix_movimentos_conciliacao_ignorado", "movimentos_extrato", ["conciliacao_id", "ignorado_no_periodo"])


def downgrade() -> None:
    op.drop_index("ix_movimentos_conciliacao_ignorado", table_name="movimentos_extrato")
    op.drop_column("movimentos_extrato", "ignorado_no_periodo")
