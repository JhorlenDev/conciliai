"""Allow global rules to be ignored in one reconciliation."""

from alembic import op
import sqlalchemy as sa


revision = "0027_rule_period_exceptions"
down_revision = "0026_entry_tax_complement"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "regras_contabeis_excecoes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("regra_contabil_id", sa.String(length=36), nullable=False),
        sa.Column("conciliacao_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["conciliacao_id"], ["conciliacoes.id"]),
        sa.ForeignKeyConstraint(["regra_contabil_id"], ["regras_contabeis.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("regra_contabil_id", "conciliacao_id", name="uq_regra_excecao_conciliacao"),
    )
    op.create_index("ix_regras_contabeis_excecoes_regra_contabil_id", "regras_contabeis_excecoes", ["regra_contabil_id"])
    op.create_index("ix_regras_contabeis_excecoes_conciliacao_id", "regras_contabeis_excecoes", ["conciliacao_id"])


def downgrade() -> None:
    op.drop_index("ix_regras_contabeis_excecoes_conciliacao_id", table_name="regras_contabeis_excecoes")
    op.drop_index("ix_regras_contabeis_excecoes_regra_contabil_id", table_name="regras_contabeis_excecoes")
    op.drop_table("regras_contabeis_excecoes")
