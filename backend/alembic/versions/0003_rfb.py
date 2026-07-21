"""add Receita Federal receipts"""
from alembic import op
import sqlalchemy as sa

revision = "0003_rfb"
down_revision = "0002_financial_values"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("comprovantes_rfb", sa.Column("id", sa.String(36), primary_key=True), sa.Column("conciliacao_id", sa.String(36), sa.ForeignKey("conciliacoes.id"), nullable=False), sa.Column("arquivo_id", sa.String(36), sa.ForeignKey("arquivos.id"), nullable=False), sa.Column("pagina_numero", sa.Integer, nullable=False), sa.Column("tipo", sa.String(10), nullable=False), sa.Column("cnpj", sa.String(32)), sa.Column("razao_social", sa.Text), sa.Column("competencia", sa.String(30)), sa.Column("periodo_apuracao", sa.String(30)), sa.Column("data_vencimento", sa.Date), sa.Column("data_arrecadacao", sa.Date), sa.Column("numero_documento", sa.String(80)), sa.Column("codigo_banco", sa.String(10)), sa.Column("nome_banco", sa.String(150)), sa.Column("agencia", sa.String(20)), sa.Column("valor_principal", sa.Numeric(18, 2)), sa.Column("valor_multa", sa.Numeric(18, 2)), sa.Column("valor_juros", sa.Numeric(18, 2)), sa.Column("valor_total", sa.Numeric(18, 2)), sa.Column("texto_original", sa.Text), sa.Column("status", sa.String(40)), sa.Column("editado_manualmente", sa.Boolean), sa.Column("created_at", sa.DateTime), sa.Column("updated_at", sa.DateTime))
    op.create_table("comprovantes_rfb_itens", sa.Column("id", sa.String(36), primary_key=True), sa.Column("comprovante_rfb_id", sa.String(36), sa.ForeignKey("comprovantes_rfb.id", ondelete="CASCADE"), nullable=False), sa.Column("codigo", sa.String(20)), sa.Column("descricao", sa.Text), sa.Column("valor_principal", sa.Numeric(18, 2)), sa.Column("valor_multa", sa.Numeric(18, 2)), sa.Column("valor_juros", sa.Numeric(18, 2)), sa.Column("valor_total", sa.Numeric(18, 2)))


def downgrade():
    op.drop_table("comprovantes_rfb_itens")
    op.drop_table("comprovantes_rfb")
