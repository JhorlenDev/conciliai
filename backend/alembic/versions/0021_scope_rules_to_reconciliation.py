"""Scope accounting rules to their reconciliation period."""

from alembic import op
import sqlalchemy as sa


revision = "0021_scope_rules"
down_revision = "0020_rename_caixa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("regras_contabeis")}
    if "conciliacao_id" not in columns:
        op.add_column("regras_contabeis", sa.Column("conciliacao_id", sa.String(36), sa.ForeignKey("conciliacoes.id"), nullable=True))
    indexes = {index["name"] for index in inspector.get_indexes("regras_contabeis")}
    if "ix_regras_contabeis_conciliacao_id" not in indexes:
        op.create_index("ix_regras_contabeis_conciliacao_id", "regras_contabeis", ["conciliacao_id"])
    op.execute("""
        CREATE TEMP TABLE regra_periodo_map AS
        SELECT
            regra.id AS regra_origem_id,
            correspondencia.conciliacao_id,
            CASE
                WHEN ROW_NUMBER() OVER (PARTITION BY regra.id ORDER BY correspondencia.conciliacao_id) = 1 THEN regra.id
                ELSE md5(regra.id || correspondencia.conciliacao_id)
            END AS regra_destino_id
        FROM regras_contabeis regra
        JOIN lancamentos_contabeis lancamento ON lancamento.regra_contabil_id = regra.id
        JOIN correspondencias correspondencia ON correspondencia.id = lancamento.correspondencia_id
        GROUP BY regra.id, correspondencia.conciliacao_id
    """)
    op.execute("""
        UPDATE regras_contabeis regra
        SET conciliacao_id = mapa.conciliacao_id
        FROM regra_periodo_map mapa
        WHERE regra.id = mapa.regra_origem_id
          AND regra.id = mapa.regra_destino_id
    """)
    op.execute("""
        INSERT INTO regras_contabeis (
            id, cliente_id, conciliacao_id, banco, tipo_fonte, tipo_operacao,
            tipo_componente, favorecido_normalizado, gatilho_comprovante_normalizado,
            codigo_receita, conta_debito, conta_credito, historico, complemento,
            ativo, created_at
        )
        SELECT
            mapa.regra_destino_id, regra.cliente_id, mapa.conciliacao_id,
            regra.banco, regra.tipo_fonte, regra.tipo_operacao, regra.tipo_componente,
            regra.favorecido_normalizado, regra.gatilho_comprovante_normalizado,
            regra.codigo_receita, regra.conta_debito, regra.conta_credito,
            regra.historico, regra.complemento, regra.ativo, regra.created_at
        FROM regra_periodo_map mapa
        JOIN regras_contabeis regra ON regra.id = mapa.regra_origem_id
        WHERE mapa.regra_destino_id <> mapa.regra_origem_id
    """)
    op.execute("""
        UPDATE lancamentos_contabeis lancamento
        SET regra_contabil_id = mapa.regra_destino_id
        FROM correspondencias correspondencia, regra_periodo_map mapa
        WHERE correspondencia.id = lancamento.correspondencia_id
          AND mapa.regra_origem_id = lancamento.regra_contabil_id
          AND mapa.conciliacao_id = correspondencia.conciliacao_id
    """)
    op.execute("""
        UPDATE correspondencias correspondencia
        SET regra_contabil_id = mapa.regra_destino_id
        FROM regra_periodo_map mapa
        WHERE mapa.regra_origem_id = correspondencia.regra_contabil_id
          AND mapa.conciliacao_id = correspondencia.conciliacao_id
    """)
    op.execute("""
        UPDATE regras_contabeis regra
        SET conciliacao_id = (
            SELECT conciliacao.id
            FROM conciliacoes conciliacao
            WHERE conciliacao.cliente_id = regra.cliente_id
              AND conciliacao.banco = regra.banco
            ORDER BY conciliacao.created_at DESC
            LIMIT 1
        )
        WHERE regra.conciliacao_id IS NULL
    """)


def downgrade() -> None:
    op.drop_index("ix_regras_contabeis_conciliacao_id", table_name="regras_contabeis")
    op.drop_column("regras_contabeis", "conciliacao_id")
