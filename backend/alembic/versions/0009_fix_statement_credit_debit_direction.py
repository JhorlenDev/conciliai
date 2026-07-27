"""Correct the C/D direction of Banco do Brasil statement records."""

from alembic import op


revision = "0009_statement_direction"
down_revision = "0008_reconciliation_processes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        UPDATE movimentos_extrato m
        SET natureza = CASE
            WHEN m.texto_original ~ '[0-9][[:space:]]+C([[:space:]]|$)' THEN 'saída'
            WHEN m.texto_original ~ '[0-9][[:space:]]+D([[:space:]]|$)' THEN 'entrada'
            ELSE m.natureza
        END
        FROM arquivos a
        WHERE a.id = m.arquivo_id
          AND a.banco_selecionado = 'Banco do Brasil'
          AND m.texto_original ~ '[0-9][[:space:]]+[CD]([[:space:]]|$)'
    """)


def downgrade() -> None:
    # This is a data correction; reversing it would corrupt new records.
    pass
