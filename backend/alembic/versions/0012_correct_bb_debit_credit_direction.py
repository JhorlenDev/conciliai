"""Use Banco do Brasil's D/C markers as the bank statement direction."""

from alembic import op


revision = "0012_bb_direction"
down_revision = "0011_accounting_items"
branch_labels = None
depends_on = None

MATCH = "m.texto_original ~ '[0-9][[:space:]]+[CD]([[:space:]]|$)'"
BB_RECONCILIATIONS = f"""
    SELECT DISTINCT m.conciliacao_id
    FROM movimentos_extrato m
    JOIN arquivos a ON a.id = m.arquivo_id
    WHERE a.banco_selecionado = 'Banco do Brasil' AND {MATCH}
"""


def upgrade() -> None:
    op.execute(f"""
        DELETE FROM lancamentos_contabeis l
        USING correspondencias c
        WHERE l.correspondencia_id = c.id
          AND c.conciliacao_id IN ({BB_RECONCILIATIONS})
    """)
    op.execute(f"DELETE FROM correspondencias WHERE conciliacao_id IN ({BB_RECONCILIATIONS})")
    op.execute(f"""
        UPDATE movimentos_extrato m
        SET natureza = CASE
            WHEN m.texto_original ~ '[0-9][[:space:]]+C([[:space:]]|$)' THEN 'entrada'
            WHEN m.texto_original ~ '[0-9][[:space:]]+D([[:space:]]|$)' THEN 'saída'
            ELSE m.natureza
        END
        FROM arquivos a
        WHERE a.id = m.arquivo_id
          AND a.banco_selecionado = 'Banco do Brasil'
          AND {MATCH}
    """)
    op.execute(f"UPDATE conciliacoes SET status = 'rascunho' WHERE id IN ({BB_RECONCILIATIONS})")
    op.execute("""
        UPDATE processos_conciliacao p SET status = 'em_andamento'
        FROM conciliacoes c WHERE c.processo_id = p.id AND c.status = 'rascunho'
    """)


def downgrade() -> None:
    pass
