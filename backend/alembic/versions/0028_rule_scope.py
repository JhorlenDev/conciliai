"""Scope new accounting rules to one period by default."""

from alembic import op
import sqlalchemy as sa


revision = "0028_rule_scope"
down_revision = "0027_rule_period_exceptions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("regras_contabeis", sa.Column("escopo", sa.String(length=20), nullable=False, server_default="global"))
    op.alter_column("regras_contabeis", "escopo", server_default=None)


def downgrade() -> None:
    op.drop_column("regras_contabeis", "escopo")
