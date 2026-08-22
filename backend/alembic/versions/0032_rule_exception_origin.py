"""track accounting rule exception origin"""
from alembic import op
import sqlalchemy as sa

revision = "0032_rule_exception_origin"
down_revision = "0031_movement_period_ignore"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("regras_contabeis_excecoes")}
    if "origem" in columns:
        return
    op.add_column("regras_contabeis_excecoes", sa.Column("origem", sa.String(30), nullable=False, server_default="auto_zero"))
    op.alter_column("regras_contabeis_excecoes", "origem", server_default=None)


def downgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("regras_contabeis_excecoes")}
    if "origem" not in columns:
        return
    op.drop_column("regras_contabeis_excecoes", "origem")
