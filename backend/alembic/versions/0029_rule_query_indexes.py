"""Index recurring reconciliation rule queries."""

from alembic import op


revision = "0029_rule_query_indexes"
down_revision = "0028_rule_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_movimentos_conciliacao_ativo_data", "movimentos_extrato", ["conciliacao_id", "ativo", "data"])
    op.create_index("ix_regras_cliente_banco_escopo", "regras_contabeis", ["cliente_id", "banco", "ativo", "escopo"])


def downgrade() -> None:
    op.drop_index("ix_regras_cliente_banco_escopo", table_name="regras_contabeis")
    op.drop_index("ix_movimentos_conciliacao_ativo_data", table_name="movimentos_extrato")
