"""Rename the existing Caixa bank before adding Conta Caixa."""

from alembic import op


revision = "0020_rename_caixa"
down_revision = "0019_receipt_trigger"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table, column in (("conciliacoes", "banco"), ("contas_bancarias", "banco"), ("regras_contabeis", "banco"), ("arquivos", "banco_selecionado")):
        op.execute(f"UPDATE {table} SET {column} = 'Caixa' WHERE {column} = 'Conta Caixa'")


def downgrade() -> None:
    for table, column in (("conciliacoes", "banco"), ("contas_bancarias", "banco"), ("regras_contabeis", "banco"), ("arquivos", "banco_selecionado")):
        op.execute(f"UPDATE {table} SET {column} = 'Conta Caixa' WHERE {column} = 'Caixa'")
