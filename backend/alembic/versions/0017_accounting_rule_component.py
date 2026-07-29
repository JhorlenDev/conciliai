"""Scope accounting rules to a reconciliation component."""

from alembic import op
import sqlalchemy as sa


revision = "0017_rule_component"
down_revision = "0016_origin_date"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("regras_contabeis", sa.Column("tipo_componente", sa.String(30), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("regras_contabeis", "tipo_componente")
