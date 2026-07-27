"""add global important documents"""

from alembic import op
import sqlalchemy as sa

revision = "0007_important_documents"
down_revision = "0006_bank_account_configuration"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "documentos_importantes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tipo", sa.String(30), nullable=False),
        sa.Column("nome_original", sa.String(255), nullable=False),
        sa.Column("caminho", sa.String(500), nullable=False),
        sa.Column("extensao", sa.String(10), nullable=False),
        sa.Column("catalogo", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade():
    op.drop_table("documentos_importantes")
