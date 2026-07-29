"""Store CNPJs for receipt beneficiaries."""

from alembic import op
import sqlalchemy as sa


revision = "0014_receipt_cnpjs"
down_revision = "0013_receipt_participants"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("comprovantes", sa.Column("cnpj_beneficiario", sa.String(32), nullable=False, server_default=""))
    op.add_column("comprovantes", sa.Column("cnpj_beneficiario_final", sa.String(32), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("comprovantes", "cnpj_beneficiario_final")
    op.drop_column("comprovantes", "cnpj_beneficiario")
