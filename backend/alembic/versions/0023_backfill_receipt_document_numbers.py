"""Backfill document identifiers from already extracted bank receipts."""

from alembic import op
import sqlalchemy as sa

from app.services.parsers import receipt_document_number


revision = "0023_receipt_doc_backfill"
down_revision = "0022_receipt_document_number"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, texto_original FROM comprovantes WHERE COALESCE(numero_documento, '') = ''")).mappings()
    for row in rows:
        number = receipt_document_number(row["texto_original"] or "")
        if number:
            bind.execute(sa.text("UPDATE comprovantes SET numero_documento = :number WHERE id = :id"), {"id": row["id"], "number": number})


def downgrade() -> None:
    pass
