"""Scope the C/D direction correction to Banco do Brasil and reset affected results."""

from alembic import op


revision = "0010_repair_direction"
down_revision = "0009_statement_direction"
branch_labels = None
depends_on = None

MATCH = "m.texto_original ~ '[0-9][[:space:]]+[CD]([[:space:]]|$)'"


def affected_reconciliations() -> str:
    return f"""
        SELECT DISTINCT m.conciliacao_id
        FROM movimentos_extrato m
        JOIN arquivos a ON a.id = m.arquivo_id
        WHERE a.banco_selecionado = 'Banco do Brasil' AND {MATCH}
    """


def upgrade() -> None:
    # Undo the previous broad update for non-BB records.
    op.execute(f"""
        UPDATE movimentos_extrato m
        SET natureza = CASE
            WHEN m.texto_original ~ '[0-9][[:space:]]+C([[:space:]]|$)' THEN 'entrada'
            WHEN m.texto_original ~ '[0-9][[:space:]]+D([[:space:]]|$)' THEN 'saída'
            ELSE m.natureza
        END
        FROM arquivos a
        WHERE a.id = m.arquivo_id
          AND a.banco_selecionado <> 'Banco do Brasil'
          AND {MATCH}
    """)
    op.execute(f"""
        UPDATE movimentos_extrato m
        SET natureza = CASE
            WHEN m.texto_original ~ '[0-9][[:space:]]+C([[:space:]]|$)' THEN 'saída'
            WHEN m.texto_original ~ '[0-9][[:space:]]+D([[:space:]]|$)' THEN 'entrada'
            ELSE m.natureza
        END
        FROM arquivos a
        WHERE a.id = m.arquivo_id
          AND a.banco_selecionado = 'Banco do Brasil'
          AND {MATCH}
    """)
    op.execute(f"""
        DELETE FROM lancamentos_contabeis l
        USING correspondencias c
        WHERE l.correspondencia_id = c.id
          AND c.conciliacao_id IN ({affected_reconciliations()})
    """)
    op.execute(f"DELETE FROM correspondencias WHERE conciliacao_id IN ({affected_reconciliations()})")
    op.execute(f"UPDATE conciliacoes SET status = 'rascunho' WHERE id IN ({affected_reconciliations()})")
    op.execute(f"""
        UPDATE processos_conciliacao p
        SET status = 'em_andamento'
        FROM conciliacoes c
        WHERE c.processo_id = p.id
          AND c.id IN ({affected_reconciliations()})
    """)


def downgrade() -> None:
    # This is a data repair. Reversing it would reintroduce stale results.
    pass
