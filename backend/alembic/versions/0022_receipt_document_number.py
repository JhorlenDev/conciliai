"""Store document identifiers extracted from bank receipts."""

from alembic import op
import sqlalchemy as sa


revision = "0022_receipt_document_number"
down_revision = "0021_scope_rules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("comprovantes", sa.Column("numero_documento", sa.String(80), nullable=False, server_default=""))
    op.alter_column("comprovantes", "numero_documento", server_default=None)


def downgrade() -> None:
    op.drop_column("comprovantes", "numero_documento")
