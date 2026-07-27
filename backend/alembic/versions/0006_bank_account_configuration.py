"""add client bank account configuration"""

from alembic import op
import sqlalchemy as sa

revision = "0006_bank_account_configuration"
down_revision = "0005_accounting_rule_scope"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "contas_bancarias",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("cliente_id", sa.String(36), sa.ForeignKey("clientes.id"), nullable=False),
        sa.Column("banco", sa.String(100), nullable=False),
        sa.Column("conta_contabil", sa.String(100), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("cliente_id", "banco", name="uq_contas_bancarias_cliente_banco"),
    )
    op.create_index("ix_contas_bancarias_cliente_id", "contas_bancarias", ["cliente_id"])


def downgrade():
    op.drop_index("ix_contas_bancarias_cliente_id", table_name="contas_bancarias")
    op.drop_table("contas_bancarias")
