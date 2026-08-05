"""Store tax complements per accounting entry."""

from alembic import op
import sqlalchemy as sa


revision = "0026_entry_tax_complement"
down_revision = "0025_repair_rfb_values"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("lancamentos_contabeis", sa.Column("complemento", sa.Text(), nullable=False, server_default=""))
    op.alter_column("lancamentos_contabeis", "complemento", server_default=None)


def downgrade() -> None:
    op.drop_column("lancamentos_contabeis", "complemento")
