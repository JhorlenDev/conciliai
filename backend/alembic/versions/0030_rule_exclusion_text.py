"""Add optional accounting rule exclusion text.

Revision ID: 0030_rule_exclusion_text
Revises: 0029_rule_query_indexes
Create Date: 2026-08-14 13:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0030_rule_exclusion_text"
down_revision = "0029_rule_query_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "regras_contabeis",
        sa.Column("texto_exclusao_normalizado", sa.Text(), nullable=False, server_default=""),
    )
    op.alter_column("regras_contabeis", "texto_exclusao_normalizado", server_default=None)


def downgrade() -> None:
    op.drop_column("regras_contabeis", "texto_exclusao_normalizado")
