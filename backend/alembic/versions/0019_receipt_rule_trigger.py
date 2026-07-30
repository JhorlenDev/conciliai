"""Add optional receipt trigger to accounting rules."""

from alembic import op
import sqlalchemy as sa


revision = "0019_receipt_trigger"
down_revision = "0018_receipt_tariff"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("regras_contabeis", sa.Column("gatilho_comprovante_normalizado", sa.Text(), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("regras_contabeis", "gatilho_comprovante_normalizado")
