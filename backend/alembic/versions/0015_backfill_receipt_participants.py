"""Reextract participant fields from stored receipt text."""

from alembic import op
import sqlalchemy as sa

from app.services.parsers import extract_receipts


revision = "0015_receipt_backfill"
down_revision = "0014_receipt_cnpjs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    receipts = connection.execute(sa.text("SELECT id, texto_original, pagina_numero FROM comprovantes WHERE texto_original IS NOT NULL AND texto_original <> ''")).mappings()
    for receipt in receipts:
        parsed = extract_receipts(receipt["texto_original"], receipt["pagina_numero"])
        if not parsed:
            continue
        item = parsed[0]
        beneficiary = item.beneficiario or item.favorecido
        final_beneficiary = item.beneficiario_final
        connection.execute(sa.text("""
            UPDATE comprovantes
            SET beneficiario = :beneficiario,
                nome_fantasia = :nome_fantasia,
                beneficiario_final = :beneficiario_final,
                pagador = :pagador,
                cnpj_beneficiario = :cnpj_beneficiario,
                cnpj_beneficiario_final = :cnpj_beneficiario_final,
                favorecido = :favorecido
            WHERE id = :id
        """), {"id": receipt["id"], "beneficiario": beneficiary, "nome_fantasia": item.nome_fantasia, "beneficiario_final": final_beneficiary, "pagador": item.pagador, "cnpj_beneficiario": item.cnpj_beneficiario, "cnpj_beneficiario_final": item.cnpj_beneficiario_final, "favorecido": final_beneficiary or beneficiary})


def downgrade() -> None:
    pass
