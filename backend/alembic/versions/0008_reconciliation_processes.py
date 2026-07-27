"""group bank reconciliations in persistent processes"""

from alembic import op
import sqlalchemy as sa
from uuid import uuid4


revision = "0008_reconciliation_processes"
down_revision = "0007_important_documents"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "processos_conciliacao",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("cliente_id", sa.String(36), sa.ForeignKey("clientes.id"), nullable=False),
        sa.Column("data_inicio", sa.Date(), nullable=False),
        sa.Column("data_fim", sa.Date(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="em_andamento"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_processos_conciliacao_cliente_id", "processos_conciliacao", ["cliente_id"])
    op.add_column("conciliacoes", sa.Column("processo_id", sa.String(36), nullable=True))
    op.create_foreign_key("fk_conciliacoes_processo_id", "conciliacoes", "processos_conciliacao", ["processo_id"], ["id"])
    op.create_index("ix_conciliacoes_processo_id", "conciliacoes", ["processo_id"])

    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id, cliente_id, data_inicio, data_fim, status, created_at FROM conciliacoes WHERE processo_id IS NULL")).mappings()
    for row in rows:
        process_id = str(uuid4())
        connection.execute(sa.text("INSERT INTO processos_conciliacao (id, cliente_id, data_inicio, data_fim, status, created_at, updated_at) VALUES (:id, :cliente_id, :data_inicio, :data_fim, :status, :created_at, :updated_at)"), {"id": process_id, "cliente_id": row["cliente_id"], "data_inicio": row["data_inicio"], "data_fim": row["data_fim"], "status": "concluido" if row["status"] == "concluido" else "em_andamento", "created_at": row["created_at"], "updated_at": row["created_at"]})
        connection.execute(sa.text("UPDATE conciliacoes SET processo_id = :process_id WHERE id = :id"), {"process_id": process_id, "id": row["id"]})


def downgrade():
    op.drop_index("ix_conciliacoes_processo_id", table_name="conciliacoes")
    op.drop_constraint("fk_conciliacoes_processo_id", "conciliacoes", type_="foreignkey")
    op.drop_column("conciliacoes", "processo_id")
    op.drop_index("ix_processos_conciliacao_cliente_id", table_name="processos_conciliacao")
    op.drop_table("processos_conciliacao")
