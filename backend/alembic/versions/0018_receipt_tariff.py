"""Store bank fees shown on payment receipts."""

from alembic import op
import sqlalchemy as sa


revision = "0018_receipt_tariff"
down_revision = "0017_rule_component"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("comprovantes", sa.Column("valor_tarifa", sa.Numeric(18, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("comprovantes", "valor_tarifa")
