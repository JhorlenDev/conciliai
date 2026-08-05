"""Repair swapped DARF item penalty columns and derived interest entries."""

from alembic import op
import sqlalchemy as sa

from app.services.rfb import parse_rfb_page


revision = "0025_repair_rfb_values"
down_revision = "0024_client_bank_details"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    receipts = bind.execute(sa.text("SELECT id, texto_original FROM comprovantes_rfb WHERE tipo = 'DARF'")).mappings()
    for receipt in receipts:
        parsed = parse_rfb_page(receipt["texto_original"] or "", 1)
        if not parsed:
            continue
        bind.execute(
            sa.text("UPDATE comprovantes_rfb SET valor_principal = :principal, valor_multa = :multa, valor_juros = :juros, valor_total = :total WHERE id = :id"),
            {"id": receipt["id"], "principal": parsed.valor_principal, "multa": parsed.valor_multa, "juros": parsed.valor_juros, "total": parsed.valor_total},
        )
        for item in parsed.itens:
            bind.execute(
                sa.text("UPDATE comprovantes_rfb_itens SET valor_principal = :principal, valor_multa = :multa, valor_juros = :juros, valor_total = :total WHERE comprovante_rfb_id = :receipt_id AND codigo = :codigo"),
                {"receipt_id": receipt["id"], "codigo": item.codigo, "principal": item.valor_principal, "multa": item.valor_multa, "juros": item.valor_juros, "total": item.valor_total},
            )
    bind.execute(sa.text("""
        DELETE FROM lancamentos_contabeis lancamento
        USING correspondencias correspondencia, comprovantes_rfb comprovante
        WHERE lancamento.correspondencia_id = correspondencia.id
          AND correspondencia.comprovante_rfb_id = comprovante.id
          AND lancamento.origem = 'rfb'
          AND lancamento.componente = 'JUROS'
          AND lancamento.status <> 'editado_manual'
          AND COALESCE(comprovante.valor_juros, 0) = 0
    """))


def downgrade() -> None:
    pass
