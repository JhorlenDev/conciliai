"""add receipt financial values"""
from alembic import op
import sqlalchemy as sa

revision = "0002_financial_values"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    for column in (
        "valor_original", "valor_desconto", "valor_abatimento", "valor_desconto_abatimento",
        "valor_juros", "valor_multa", "valor_encargos", "valor_pago",
    ):
        op.add_column("comprovantes", sa.Column(column, sa.Numeric(18, 2), nullable=True))
    op.add_column("comprovantes", sa.Column("detalhes_financeiros", sa.JSON(), nullable=True))
    op.execute("UPDATE comprovantes SET valor_original = valor, valor_pago = valor, detalhes_financeiros = '{}' WHERE valor IS NOT NULL")


def downgrade():
    op.drop_column("comprovantes", "detalhes_financeiros")
    for column in (
        "valor_pago", "valor_encargos", "valor_multa", "valor_juros", "valor_desconto_abatimento",
        "valor_abatimento", "valor_desconto", "valor_original",
    ):
        op.drop_column("comprovantes", column)
