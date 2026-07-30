from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes import RegraContabilInput, accounting_csv, accounting_rules, apply_accounting_rules, create_accounting_rule, delete_accounting_rule, rule_matches_movement
from app.core.database import Base
from app.models import Arquivo, Cliente, Comprovante, Conciliacao, ContaBancaria, Correspondencia, LancamentoContabil, MovimentoExtrato, RegraContabil
from app.services.normalization import normalize_name


def test_rule_application_and_csv_include_only_covered_movements():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = Cliente(nome="Cliente")
    session.add(client); session.flush()
    reconciliation = Conciliacao(cliente_id=client.id, banco="Santander", data_inicio=date(2024, 1, 1), data_fim=date(2024, 1, 31))
    session.add(reconciliation); session.flush()
    file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="extrato", banco_selecionado="Santander", nome_original="extrato.pdf", caminho="/tmp/extrato.pdf")
    session.add(file); session.flush()
    covered = MovimentoExtrato(conciliacao_id=reconciliation.id, arquivo_id=file.id, pagina_numero=1, data=date(2024, 1, 2), historico="PIX FORNECEDOR", valor=Decimal("12.50"), natureza="saída")
    pending = MovimentoExtrato(conciliacao_id=reconciliation.id, arquivo_id=file.id, pagina_numero=1, data=date(2024, 1, 3), historico="TARIFA", valor=Decimal("5.00"), natureza="saída")
    rule = RegraContabil(cliente_id=client.id, banco="Santander", tipo_fonte="extrato", tipo_operacao="saída", favorecido_normalizado=normalize_name("PIX"), conta_debito="Despesa", conta_credito="Banco", historico="Pagamento", complemento="Extrato")
    session.add_all([covered, pending, rule]); session.flush()
    session.add(ContaBancaria(cliente_id=client.id, banco="Santander", conta_contabil="Banco"))

    assert apply_accounting_rules(reconciliation, session) == 1
    assert apply_accounting_rules(reconciliation, session) == 1
    assert session.query(LancamentoContabil).filter_by(status="aplicado_por_regra").count() == 1
    session.commit()

    response = accounting_csv(reconciliation.id, session)
    csv = response.body.decode("utf-8-sig")
    assert csv.splitlines() == ["data;debito;credito;historico;complemento;valor", "02/01/2024;Despesa;Banco;Pagamento;Extrato;12,50"]
    data = accounting_rules(reconciliation.id, session)
    assert len(data["pendentes"]) == 1
    entry = session.query(LancamentoContabil).filter_by(status="aplicado_por_regra").one()
    assert (entry.valor, entry.conta_debito, entry.conta_credito) == (Decimal("12.50"), "Despesa", "Banco")
    assert data["resumo"]["razao"] == {"debito": "0", "credito": "12.50"}


def test_credit_rule_moves_entry_to_saved_and_reason_only_sums_covered_value():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = Cliente(nome="Cliente")
    session.add(client); session.flush()
    reconciliation = Conciliacao(cliente_id=client.id, banco="Banco do Brasil", data_inicio=date(2024, 1, 1), data_fim=date(2024, 1, 31))
    session.add(reconciliation); session.flush()
    file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="extrato", banco_selecionado="Banco do Brasil", nome_original="extrato.pdf", caminho="/tmp/extrato.pdf")
    session.add(file); session.flush()
    movement = MovimentoExtrato(conciliacao_id=reconciliation.id, arquivo_id=file.id, pagina_numero=1, data=date(2024, 1, 2), historico="RECEBIMENTO CLIENTE", valor=Decimal("20.00"), natureza="entrada")
    rule = RegraContabil(cliente_id=client.id, banco="Banco do Brasil", tipo_fonte="extrato", tipo_operacao="entrada", favorecido_normalizado=normalize_name("RECEBIMENTO"), conta_debito="Banco", conta_credito="Receita", historico="Recebimento", complemento="Extrato")
    session.add_all([movement, rule]); session.flush()

    assert apply_accounting_rules(reconciliation, session) == 1
    data = accounting_rules(reconciliation.id, session)

    assert data["pendentes"] == []
    assert data["salvas"][0]["natureza"] == "Débito"
    assert data["salvas"][0]["movimentos"][0]["texto_extrato"] == "RECEBIMENTO CLIENTE"
    assert data["salvas"][0]["movimentos"][0]["tem_comprovante"] is False
    assert data["salvas"][0]["movimentos"][0]["texto_comprovante"] == ""
    entry = session.query(LancamentoContabil).filter_by(status="aplicado_por_regra").one()
    assert (entry.valor, entry.conta_debito, entry.conta_credito) == (Decimal("20.00"), "Banco", "Receita")
    assert data["resumo"]["razao"] == {"debito": "20.00", "credito": "0"}


def test_reason_separates_debit_and_credit_movements_without_double_counting():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = Cliente(nome="Cliente")
    session.add(client); session.flush()
    reconciliation = Conciliacao(cliente_id=client.id, banco="Banco do Brasil", data_inicio=date(2024, 1, 1), data_fim=date(2024, 1, 31))
    session.add(reconciliation); session.flush()
    file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="extrato", banco_selecionado="Banco do Brasil", nome_original="extrato.pdf", caminho="/tmp/extrato.pdf")
    session.add(file); session.flush()
    debit = MovimentoExtrato(conciliacao_id=reconciliation.id, arquivo_id=file.id, pagina_numero=1, data=date(2024, 1, 2), historico="PIX RECEBIDO", valor=Decimal("100.00"), natureza="saída")
    credit = MovimentoExtrato(conciliacao_id=reconciliation.id, arquivo_id=file.id, pagina_numero=1, data=date(2024, 1, 2), historico="PIX ENVIADO", valor=Decimal("100.00"), natureza="entrada")
    debit_rule = RegraContabil(cliente_id=client.id, banco="Banco do Brasil", tipo_fonte="extrato", tipo_operacao="saída", favorecido_normalizado=normalize_name("RECEBIDO"), conta_debito="Banco", conta_credito="Receita", historico="Recebimento")
    credit_rule = RegraContabil(cliente_id=client.id, banco="Banco do Brasil", tipo_fonte="extrato", tipo_operacao="entrada", favorecido_normalizado=normalize_name("ENVIADO"), conta_debito="Despesa", conta_credito="Banco", historico="Pagamento")
    session.add_all([debit, credit, debit_rule, credit_rule]); session.flush()

    assert apply_accounting_rules(reconciliation, session) == 2
    assert apply_accounting_rules(reconciliation, session) == 2
    data = accounting_rules(reconciliation.id, session)

    assert session.query(LancamentoContabil).filter_by(status="aplicado_por_regra").count() == 2
    assert data["resumo"]["razao"] == {"debito": "100.00", "credito": "100.00"}


def test_rule_requires_its_statement_and_receipt_triggers():
    movement = MovimentoExtrato(historico="Transferência Agendada", nome_encontrado="32.600.000.023.452", natureza="Débito")
    receipt = Comprovante(favorecido="Maria Luzirda C Miranda", beneficiario="Maria Luzirda C Miranda", tipo_operacao="Transferência", texto_original="AGENCIA: 0326-3 CONTA: 23.452-4")
    rule = RegraContabil(tipo_fonte="extrato", favorecido_normalizado=normalize_name("Transferência Agendada"), gatilho_comprovante_normalizado=normalize_name("Maria Luzirda C Miranda"))

    assert rule_matches_movement(rule, movement, receipt)
    assert not rule_matches_movement(rule, movement, Comprovante(favorecido="Outra Pessoa"))
    assert rule_matches_movement(RegraContabil(tipo_fonte="extrato", favorecido_normalizado=normalize_name("Transferência Agendada")), movement, None)


def test_legacy_rule_without_receipt_trigger_can_match_its_receipt_party():
    movement = MovimentoExtrato(historico="Pagamento de Boleto", nome_encontrado="BAMBUNO TECNOLOGIA", natureza="saída")
    receipt = Comprovante(favorecido="Bambuno Tecnologia", beneficiario_final="Sucessodonto Cursos e Treinamentos")
    rule = RegraContabil(tipo_fonte="extrato", tipo_operacao="Crédito", tipo_componente="VALOR_COBRADO", favorecido_normalizado=normalize_name("Pagamento Boleto Sucessodonto Cursos e Treinamentos"))

    assert rule_matches_movement(rule, movement, receipt, "VALOR_COBRADO")


def rules_session(history="PIX FORNECEDOR"):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = Cliente(nome="Cliente")
    session.add(client); session.flush()
    reconciliation = Conciliacao(cliente_id=client.id, banco="Santander", data_inicio=date(2024, 1, 1), data_fim=date(2024, 1, 31))
    session.add(reconciliation); session.flush()
    file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="extrato", banco_selecionado="Santander", nome_original="extrato.pdf", caminho="/tmp/extrato.pdf")
    session.add(file); session.flush()
    movement = MovimentoExtrato(conciliacao_id=reconciliation.id, arquivo_id=file.id, pagina_numero=1, data=date(2024, 1, 2), historico=history, valor=Decimal("12.50"), natureza="saída")
    session.add(movement); session.flush()
    return session, reconciliation, movement


def rule_input(trigger="FORNECEDOR", receipt_trigger=""):
    return RegraContabilInput(gatilho=trigger, gatilho_comprovante=receipt_trigger, natureza="Crédito", tipo_componente="PRINCIPAL", conta_debito="Despesa", conta_credito="Banco", historico="Pagamento", complemento="Extrato")


def test_new_eligible_rule_is_returned_as_pending_suggestion():
    session, reconciliation, _ = rules_session()

    assert len(accounting_rules(reconciliation.id, session)["pendentes"]) == 1


def test_saved_rule_disappears_from_pending_and_is_returned_as_saved_after_refresh():
    session, reconciliation, _ = rules_session()

    create_accounting_rule(reconciliation.id, rule_input(), session)
    first_load = accounting_rules(reconciliation.id, session)
    refreshed_load = accounting_rules(reconciliation.id, session)

    assert first_load["pendentes"] == refreshed_load["pendentes"] == []
    assert len(first_load["salvas"]) == 1
    assert first_load["salvas"][0]["cobertos"] == 1


def test_persisted_covered_entry_does_not_return_zero_eligible_suggestion():
    session, reconciliation, movement = rules_session("PIX ATUAL")
    legacy_rule = RegraContabil(cliente_id=reconciliation.cliente_id, banco="Santander", tipo_fonte="extrato", tipo_operacao="Crédito", favorecido_normalizado=normalize_name("FORNECEDOR ANTIGO"), conta_debito="Despesa", conta_credito="Banco", historico="Pagamento")
    session.add(legacy_rule); session.flush()
    match = Correspondencia(conciliacao_id=reconciliation.id, movimento_extrato_id=movement.id, regra_contabil_id=legacy_rule.id)
    session.add(match); session.flush()
    session.add(LancamentoContabil(correspondencia_id=match.id, regra_contabil_id=legacy_rule.id, componente="PRINCIPAL", valor=movement.valor, status="aplicado_por_regra"))

    data = accounting_rules(reconciliation.id, session)

    assert data["pendentes"] == []
    assert data["salvas"][0]["cobertos"] == 1


def test_deleting_saved_rule_recalculates_its_pending_suggestion():
    session, reconciliation, _ = rules_session()
    created = create_accounting_rule(reconciliation.id, rule_input(), session)

    delete_accounting_rule(created["id"], session)

    assert len(accounting_rules(reconciliation.id, session)["pendentes"]) == 1


def test_receipt_and_statement_triggers_must_both_match_when_filtering_pending():
    session, reconciliation, movement = rules_session("TRANSFERENCIA AGENDADA")
    receipt = Comprovante(conciliacao_id=reconciliation.id, arquivo_id="arquivo", pagina_numero=1, tipo_operacao="Transferência", favorecido="Maria Luzirda C Miranda", beneficiario_final="Destino Final")
    session.add(receipt); session.flush()
    session.add(Correspondencia(conciliacao_id=reconciliation.id, movimento_extrato_id=movement.id, comprovante_id=receipt.id)); session.commit()

    create_accounting_rule(reconciliation.id, rule_input("TRANSFERENCIA AGENDADA", "MARIA LUZIRDA C MIRANDA"), session)

    data = accounting_rules(reconciliation.id, session)
    assert data["pendentes"] == []
    assert data["salvas"][0]["movimentos"][0]["texto_comprovante"] == "Transferência Destino Final"


def test_equivalent_rule_with_reordered_keywords_is_not_saved_twice():
    session, reconciliation, _ = rules_session()
    create_accounting_rule(reconciliation.id, rule_input("PIX FORNECEDOR"), session)

    with pytest.raises(HTTPException, match="regra equivalente"):
        create_accounting_rule(reconciliation.id, rule_input("FORNECEDOR, PIX"), session)
