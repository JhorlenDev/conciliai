"""add accounting rule source structures"""
from alembic import op
import sqlalchemy as sa

revision = "0004_rule_source"
down_revision = "0003_rfb"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("regras_contabeis", sa.Column("id", sa.String(36), primary_key=True), sa.Column("tipo_fonte", sa.String(30), nullable=False), sa.Column("tipo_operacao", sa.String(80)), sa.Column("favorecido_normalizado", sa.Text), sa.Column("codigo_receita", sa.String(20)), sa.Column("conta_debito", sa.String(100)), sa.Column("conta_credito", sa.String(100)), sa.Column("historico", sa.Text), sa.Column("ativo", sa.Boolean), sa.Column("created_at", sa.DateTime))
    op.add_column("correspondencias", sa.Column("comprovante_rfb_id", sa.String(36), sa.ForeignKey("comprovantes_rfb.id"), nullable=True))
    op.add_column("correspondencias", sa.Column("fonte_regra", sa.String(30), nullable=True))
    op.add_column("correspondencias", sa.Column("regra_contabil_id", sa.String(36), sa.ForeignKey("regras_contabeis.id"), nullable=True))
    op.create_table("lancamentos_contabeis", sa.Column("id", sa.String(36), primary_key=True), sa.Column("correspondencia_id", sa.String(36), sa.ForeignKey("correspondencias.id"), nullable=False), sa.Column("regra_contabil_id", sa.String(36), sa.ForeignKey("regras_contabeis.id"), nullable=True), sa.Column("componente", sa.String(30)), sa.Column("valor", sa.Numeric(18, 2), nullable=False), sa.Column("conta_debito", sa.String(100)), sa.Column("conta_credito", sa.String(100)), sa.Column("historico", sa.Text), sa.Column("status", sa.String(40)))


def downgrade():
    op.drop_table("lancamentos_contabeis")
    op.drop_column("correspondencias", "regra_contabil_id")
    op.drop_column("correspondencias", "fonte_regra")
    op.drop_column("correspondencias", "comprovante_rfb_id")
    op.drop_table("regras_contabeis")
