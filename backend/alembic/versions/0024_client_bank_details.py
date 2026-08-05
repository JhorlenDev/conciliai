"""Store client bank account details."""

from alembic import op
import sqlalchemy as sa


revision = "0024_client_bank_details"
down_revision = "0023_receipt_doc_backfill"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contas_bancarias", sa.Column("agencia", sa.String(30), nullable=False, server_default=""))
    op.add_column("contas_bancarias", sa.Column("conta", sa.String(50), nullable=False, server_default=""))
    op.add_column("contas_bancarias", sa.Column("titular", sa.String(255), nullable=False, server_default=""))
    op.alter_column("contas_bancarias", "agencia", server_default=None)
    op.alter_column("contas_bancarias", "conta", server_default=None)
    op.alter_column("contas_bancarias", "titular", server_default=None)


def downgrade() -> None:
    op.drop_column("contas_bancarias", "titular")
    op.drop_column("contas_bancarias", "conta")
    op.drop_column("contas_bancarias", "agencia")
