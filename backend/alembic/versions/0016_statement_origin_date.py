"""Store auxiliary transfer scheduling date separately from counterparty."""

from alembic import op
import sqlalchemy as sa


revision = "0016_origin_date"
down_revision = "0015_receipt_backfill"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("movimentos_extrato", sa.Column("data_origem", sa.String(10), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("movimentos_extrato", "data_origem")
