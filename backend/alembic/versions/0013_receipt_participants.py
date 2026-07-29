"""Preserve all receipt participants for matching and review."""

from alembic import op
import sqlalchemy as sa


revision = "0013_receipt_participants"
down_revision = "0012_bb_direction"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for column in ("beneficiario", "nome_fantasia", "beneficiario_final", "pagador"):
        op.add_column("comprovantes", sa.Column(column, sa.Text(), nullable=False, server_default=""))
    op.add_column("correspondencias", sa.Column("criterio_correspondencia", sa.String(80), nullable=False, server_default=""))
    op.execute("UPDATE comprovantes SET beneficiario = favorecido WHERE beneficiario = ''")


def downgrade() -> None:
    op.drop_column("correspondencias", "criterio_correspondencia")
    for column in ("pagador", "beneficiario_final", "nome_fantasia", "beneficiario"):
        op.drop_column("comprovantes", column)
