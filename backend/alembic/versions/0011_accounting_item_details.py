"""Add detailed accounting-item metadata without removing existing data."""

from alembic import op
import sqlalchemy as sa


revision = "0011_accounting_items"
down_revision = "0010_repair_direction"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("lancamentos_contabeis", sa.Column("categoria", sa.String(30), nullable=False, server_default=""))
    op.add_column("lancamentos_contabeis", sa.Column("tributo", sa.Text(), nullable=False, server_default=""))
    op.add_column("lancamentos_contabeis", sa.Column("codigo_receita", sa.String(20), nullable=False, server_default=""))
    op.add_column("lancamentos_contabeis", sa.Column("descricao", sa.Text(), nullable=False, server_default=""))
    op.add_column("lancamentos_contabeis", sa.Column("efeito_no_total", sa.String(10), nullable=False, server_default="SOMA"))
    op.add_column("lancamentos_contabeis", sa.Column("origem", sa.String(20), nullable=False, server_default=""))
    op.add_column("lancamentos_contabeis", sa.Column("ordem", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    for column in ("ordem", "origem", "efeito_no_total", "descricao", "codigo_receita", "tributo", "categoria"):
        op.drop_column("lancamentos_contabeis", column)
