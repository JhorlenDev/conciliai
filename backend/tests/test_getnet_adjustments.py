from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes import RegraContabilInput, accounting_csv, accounting_integrity, accounting_rules, create_accounting_rule
from app.core.database import Base
from app.models import Arquivo, Cliente, Comprovante, Conciliacao, ContaBancaria, Correspondencia, LancamentoContabil, MovimentoExtrato
from app.services.getnet_adjustments import GETNET_ADJUSTMENT_ORIGIN, GETNET_ADJUSTMENT_STATUS, sync_getnet_anticipation_adjustments


def adjustment_session(bank="Santander", start=date(2024, 1, 1), end=date(2024, 1, 31)):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = Cliente(nome="Cliente")
    session.add(client)
    session.flush()
    reconciliation = Conciliacao(cliente_id=client.id, banco=bank, data_inicio=start, data_fim=end)
    session.add(reconciliation)
    session.flush()
    statement_file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="extrato", banco_selecionado=bank, nome_original="extrato.pdf", caminho="/tmp/extrato.pdf", paginas=3)
    getnet_file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="getnet_vendas", banco_selecionado=bank, nome_original="getnet.pdf", caminho="/tmp/getnet.pdf")
    session.add_all([statement_file, getnet_file, ContaBancaria(cliente_id=client.id, banco="Santander", conta_contabil="219 - Banco Santander")])
    session.flush()
    return session, reconciliation, statement_file, getnet_file


def add_santander_getnet(session, reconciliation, file, value, movement_date=date(2024, 1, 10), history="ANTECIPACAO GETNET"):
    movement = MovimentoExtrato(conciliacao_id=reconciliation.id, arquivo_id=file.id, pagina_numero=1, data=movement_date, historico=history, valor=Decimal(value), natureza="Crédito")
    session.add(movement)
    session.flush()
    return movement


def add_getnet_net(session, reconciliation, file, value, receipt_date=date(2024, 1, 10)):
    receipt = Comprovante(conciliacao_id=reconciliation.id, arquivo_id=file.id, pagina_numero=1, data=receipt_date, favorecido="GETNET - VISA DÉBITO", beneficiario="GETNET - VISA DÉBITO", valor_pago=Decimal(value), valor=Decimal(value), tipo_operacao="GETNET VENDAS")
    session.add(receipt)
    session.flush()
    return receipt


def generated_entries(session):
    return session.query(LancamentoContabil).filter_by(origem=GETNET_ADJUSTMENT_ORIGIN).all()


def movement_for_entry(session, entry):
    match = session.get(Correspondencia, entry.correspondencia_id)
    return session.get(MovimentoExtrato, match.movimento_extrato_id)


def test_getnet_net_greater_than_santander_generates_anticipation_expense_and_csv_line():
    session, reconciliation, statement_file, getnet_file = adjustment_session()
    add_getnet_net(session, reconciliation, getnet_file, "1100.00")
    add_santander_getnet(session, reconciliation, statement_file, "1000.00")
    add_santander_getnet(session, reconciliation, statement_file, "999.99", history="PIX RECEBIDO GETNET CLIENTE")

    summary = sync_getnet_anticipation_adjustments(reconciliation, session)
    session.commit()

    assert summary[0]["situacao"] == "Pendente em regras"
    assert summary[0]["total_getnet"] == "1100.00"
    assert summary[0]["total_santander"] == "1000.00"
    assert summary[0]["diferenca"] == "100.00"
    entry = generated_entries(session)[0]
    assert (entry.valor, entry.status, entry.conta_debito, entry.conta_credito) == (Decimal("100.00"), GETNET_ADJUSTMENT_STATUS, "", "219 - Banco Santander")
    movement = movement_for_entry(session, entry)
    assert (movement.data, movement.ativo) == (date(2024, 1, 31), False)

    rules = accounting_rules(reconciliation.id, session)
    pending = next(item for item in rules["pendentes"] if item["ajuste_getnet"])
    assert pending["gatilho_sugerido"] == "JUROS ANTECIPACOES GETNET"
    assert pending["natureza_contabil"] == "Crédito"
    assert "Getnet líquido: R$ 1.100,00" in pending["composicao_simples"]

    created = create_accounting_rule(reconciliation.id, RegraContabilInput(gatilho="JUROS ANTECIPACOES GETNET", natureza="Crédito", tipo_componente="JUROS_ANTECIPACAO_GETNET", conta_debito="Juros sobre antecipações", conta_credito="Banco Santander", historico="Juros Getnet", complemento="Diferença Getnet x Santander"), session)
    assert created["movimentos_aplicados"] == 1
    integrity = accounting_integrity(reconciliation, session)
    assert (integrity["outros_debito"], integrity["outros_credito"], integrity["outros"]) == (Decimal("100.00"), Decimal("100.00"), Decimal("0.00"))
    assert sync_getnet_anticipation_adjustments(reconciliation, session)[0]["situacao"] == "Ajuste lançado"
    csv = accounting_csv(reconciliation.id, session).body.decode("utf-8-sig")
    assert "Juros Getnet;100.00;DIFERENÇA ENTRE GETNET E RECEBIMENTOS NO SANTANDER" in csv


def test_equal_values_do_not_generate_adjustment():
    session, reconciliation, statement_file, getnet_file = adjustment_session()
    add_getnet_net(session, reconciliation, getnet_file, "1000.00")
    add_santander_getnet(session, reconciliation, statement_file, "1000.00")

    summary = sync_getnet_anticipation_adjustments(reconciliation, session)

    assert summary[0]["situacao"] == "Sem diferença"
    assert generated_entries(session) == []


def test_santander_greater_than_getnet_is_review_only():
    session, reconciliation, statement_file, getnet_file = adjustment_session()
    add_getnet_net(session, reconciliation, getnet_file, "900.00")
    add_santander_getnet(session, reconciliation, statement_file, "1000.00")

    summary = sync_getnet_anticipation_adjustments(reconciliation, session)

    assert summary[0]["situacao"] == "Divergência para revisão"
    assert summary[0]["diferenca"] == "100.00"
    assert generated_entries(session) == []


def test_missing_getnet_or_santander_data_is_insufficient():
    session, reconciliation, statement_file, getnet_file = adjustment_session()
    add_getnet_net(session, reconciliation, getnet_file, "1000.00")

    summary = sync_getnet_anticipation_adjustments(reconciliation, session)

    assert summary[0]["situacao"] == "Dados insuficientes"
    assert generated_entries(session) == []

    session, reconciliation, statement_file, _ = adjustment_session()
    add_santander_getnet(session, reconciliation, statement_file, "1000.00")

    summary = sync_getnet_anticipation_adjustments(reconciliation, session)

    assert summary[0]["situacao"] == "Dados insuficientes"
    assert generated_entries(session) == []


def test_sync_is_idempotent_updates_value_and_removes_only_automatic_adjustment():
    session, reconciliation, statement_file, getnet_file = adjustment_session()
    receipt = add_getnet_net(session, reconciliation, getnet_file, "1100.00")
    add_santander_getnet(session, reconciliation, statement_file, "1000.00")

    sync_getnet_anticipation_adjustments(reconciliation, session)
    sync_getnet_anticipation_adjustments(reconciliation, session)
    assert len(generated_entries(session)) == 1

    receipt.valor_pago = Decimal("1150.00")
    sync_getnet_anticipation_adjustments(reconciliation, session)
    assert [entry.valor for entry in generated_entries(session)] == [Decimal("150.00")]

    receipt.valor_pago = Decimal("1000.00")
    sync_getnet_anticipation_adjustments(reconciliation, session)
    assert generated_entries(session) == []


def test_multiple_months_and_leap_february_use_real_month_end():
    session, reconciliation, statement_file, getnet_file = adjustment_session(start=date(2024, 1, 1), end=date(2024, 2, 29))
    add_getnet_net(session, reconciliation, getnet_file, "1100.00", date(2024, 1, 5))
    add_santander_getnet(session, reconciliation, statement_file, "1000.00", date(2024, 1, 6))
    add_getnet_net(session, reconciliation, getnet_file, "2200.00", date(2024, 2, 5))
    add_santander_getnet(session, reconciliation, statement_file, "2000.00", date(2024, 2, 6), "PAGAMENTO CARTAO DE DEBITO GETNET-ELO DEBITO")

    summary = sync_getnet_anticipation_adjustments(reconciliation, session)
    entries = generated_entries(session)

    assert [(item["competencia"], item["diferenca"], item["situacao"]) for item in summary] == [
        ("2024-01", "100.00", "Pendente em regras"),
        ("2024-02", "200.00", "Pendente em regras"),
    ]
    assert sorted((movement_for_entry(session, entry).data for entry in entries)) == [date(2024, 1, 31), date(2024, 2, 29)]
    assert sorted(item["lancamento"]["data"] for item in summary) == ["29/02/2024", "31/01/2024"]


def test_other_bank_does_not_calculate_getnet_adjustment():
    session, reconciliation, statement_file, getnet_file = adjustment_session(bank="Banco do Brasil")
    add_getnet_net(session, reconciliation, getnet_file, "1100.00")
    add_santander_getnet(session, reconciliation, statement_file, "1000.00")

    assert sync_getnet_anticipation_adjustments(reconciliation, session) == []
    assert generated_entries(session) == []
