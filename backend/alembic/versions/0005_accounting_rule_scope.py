"""scope accounting rules by client and bank"""
from alembic import op
import sqlalchemy as sa

revision = "0005_accounting_rule_scope"
down_revision = "0004_rule_source"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("regras_contabeis", sa.Column("cliente_id", sa.String(36), sa.ForeignKey("clientes.id"), nullable=True))
    op.add_column("regras_contabeis", sa.Column("banco", sa.String(100), nullable=False, server_default=""))
    op.add_column("regras_contabeis", sa.Column("complemento", sa.Text, nullable=False, server_default=""))
    op.create_index("ix_regras_contabeis_cliente_id", "regras_contabeis", ["cliente_id"])


def downgrade():
    op.drop_index("ix_regras_contabeis_cliente_id", table_name="regras_contabeis")
    op.drop_column("regras_contabeis", "complemento")
    op.drop_column("regras_contabeis", "banco")
    op.drop_column("regras_contabeis", "cliente_id")
