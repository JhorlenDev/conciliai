from datetime import date
from decimal import Decimal

import pytest
import fitz
from fastapi import HTTPException, Response
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.api.routes import RegraContabilInput, RegraContabilPreviaInput, accounting_csv, accounting_integrity, accounting_pdf, accounting_rules, apply_accounting_rules, create_accounting_rule, delete_accounting_rule, delete_accounting_rule_for_reconciliation, delete_all_accounting_rules, delete_zero_covered_accounting_rules, ignore_rule_in_period, preview_accounting_rule, result, restore_rule_in_period, review, rule_matches_movement, unused_documents, update_accounting_rule
import app.api.routes as routes
from app.core.database import Base
from app.models import Arquivo, Cliente, Comprovante, ComprovanteRfb, Conciliacao, ContaBancaria, Correspondencia, LancamentoContabil, MovimentoExtrato, RegraContabil, RegraContabilExcecao
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
    rule = RegraContabil(cliente_id=client.id, conciliacao_id=reconciliation.id, banco="Santander", tipo_fonte="extrato", tipo_operacao="saída", favorecido_normalizado=normalize_name("PIX"), conta_debito="1.1.01 - Despesa", conta_credito="1.1.02 - Banco", historico="101 - Pagamento", complemento="Pagamento ao fornecedor conforme extrato")
    session.add_all([covered, pending, rule]); session.flush()
    session.add(ContaBancaria(cliente_id=client.id, banco="Santander", conta_contabil="1.1.02 - Banco"))

    assert apply_accounting_rules(reconciliation, session) == 1
    assert apply_accounting_rules(reconciliation, session) == 1
    assert session.query(LancamentoContabil).filter_by(status="aplicado_por_regra").count() == 1
    session.commit()

    response = accounting_csv(reconciliation.id, session)
    csv = response.body.decode("utf-8-sig")
    assert csv.splitlines() == ["Data;Debito;Credito;Historico;Valor;Complemento", "02/01/2024;1.1.01;1.1.02;101;12.50;Pagamento ao fornecedor conforme extrato"]
    data = accounting_rules(reconciliation.id, session)
    assert len(data["pendentes"]) == 1
    entry = session.query(LancamentoContabil).filter_by(status="aplicado_por_regra").one()
    assert (entry.valor, entry.conta_debito, entry.conta_credito) == (Decimal("12.50"), "1.1.01 - Despesa", "1.1.02 - Banco")
    assert data["resumo"]["razao"] == {"debito": "0.00", "credito": "12.50", "outros": "0.00", "outros_debito": "0.00", "outros_credito": "0.00"}


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
    rule = RegraContabil(cliente_id=client.id, conciliacao_id=reconciliation.id, banco="Banco do Brasil", tipo_fonte="extrato", tipo_operacao="entrada", favorecido_normalizado=normalize_name("RECEBIMENTO"), conta_debito="Banco", conta_credito="Receita", historico="Recebimento", complemento="Extrato")
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
    assert data["resumo"]["razao"] == {"debito": "20.00", "credito": "0.00", "outros": "0.00", "outros_debito": "0.00", "outros_credito": "0.00"}


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
    debit_rule = RegraContabil(cliente_id=client.id, conciliacao_id=reconciliation.id, banco="Banco do Brasil", tipo_fonte="extrato", tipo_operacao="saída", favorecido_normalizado=normalize_name("RECEBIDO"), conta_debito="Banco", conta_credito="Receita", historico="Recebimento")
    credit_rule = RegraContabil(cliente_id=client.id, conciliacao_id=reconciliation.id, banco="Banco do Brasil", tipo_fonte="extrato", tipo_operacao="entrada", favorecido_normalizado=normalize_name("ENVIADO"), conta_debito="Despesa", conta_credito="Banco", historico="Pagamento")
    session.add_all([debit, credit, debit_rule, credit_rule]); session.flush()

    assert apply_accounting_rules(reconciliation, session) == 2
    assert apply_accounting_rules(reconciliation, session) == 2
    data = accounting_rules(reconciliation.id, session)

    assert session.query(LancamentoContabil).filter_by(status="aplicado_por_regra").count() == 2
    assert data["resumo"]["razao"] == {"debito": "100.00", "credito": "100.00", "outros": "0.00", "outros_debito": "0.00", "outros_credito": "0.00"}


def test_rule_requires_its_statement_and_receipt_triggers():
    movement = MovimentoExtrato(historico="Transferência Agendada", nome_encontrado="32.600.000.023.452", natureza="Débito")
    receipt = Comprovante(favorecido="Maria Luzirda C Miranda", beneficiario="Maria Luzirda C Miranda", tipo_operacao="Transferência", texto_original="AGENCIA: 0326-3 CONTA: 23.452-4")
    rule = RegraContabil(tipo_fonte="extrato", favorecido_normalizado=normalize_name("Transferência Agendada"), gatilho_comprovante_normalizado=normalize_name("Maria Luzirda C Miranda"))

    assert rule_matches_movement(rule, movement, receipt)
    assert not rule_matches_movement(rule, movement, Comprovante(favorecido="Outra Pessoa"))
    assert rule_matches_movement(RegraContabil(tipo_fonte="extrato", favorecido_normalizado=normalize_name("Transferência Agendada")), movement, None)


def test_rule_with_only_receipt_trigger_is_saved_and_applied():
    session, reconciliation, movement = rules_session("PAGAMENTO DIVERSO")
    receipt = Comprovante(conciliacao_id=reconciliation.id, arquivo_id=movement.arquivo_id, pagina_numero=1, favorecido="Fornecedor específico")
    session.add(receipt); session.flush()
    session.add(Correspondencia(conciliacao_id=reconciliation.id, movimento_extrato_id=movement.id, comprovante_id=receipt.id)); session.commit()

    create_accounting_rule(reconciliation.id, rule_input("", "FORNECEDOR ESPECÍFICO"), session)

    data = accounting_rules(reconciliation.id, session)
    assert data["pendentes"] == []
    assert data["salvas"][0]["cobertos"] == 1


def test_rule_receipt_trigger_combines_bank_and_rfb_keywords():
    movement = MovimentoExtrato(historico="Pagamento de Boleto", natureza="saída")
    receipt = Comprovante(favorecido="Bambuno Tecnologia")
    rfb = ComprovanteRfb(tipo="DAS", razao_social="Empresa Simples Nacional")
    rule = RegraContabil(tipo_fonte="extrato", favorecido_normalizado=normalize_name("Pagamento Boleto"), gatilho_comprovante_normalizado=normalize_name("Bambuno Simples"))

    assert rule_matches_movement(rule, movement, receipt, "", rfb)
    assert not rule_matches_movement(rule, movement, receipt, "", ComprovanteRfb(tipo="DARF", razao_social="Outra Empresa"))


def test_pending_payload_exposes_linked_bank_and_rfb_documents():
    session, reconciliation, movement = rules_session()
    receipt = Comprovante(conciliacao_id=reconciliation.id, arquivo_id=movement.arquivo_id, pagina_numero=2, favorecido="Fornecedor Banco", numero_documento="13.101")
    rfb = ComprovanteRfb(conciliacao_id=reconciliation.id, arquivo_id=movement.arquivo_id, pagina_numero=3, tipo="DAS", razao_social="Empresa Simples Nacional")
    session.add_all([receipt, rfb]); session.flush()
    session.add(Correspondencia(conciliacao_id=reconciliation.id, movimento_extrato_id=movement.id, comprovante_id=receipt.id, comprovante_rfb_id=rfb.id)); session.commit()

    pending = accounting_rules(reconciliation.id, session)["pendentes"][0]

    assert pending["comprovante_arquivo_id"] == receipt.arquivo_id
    assert pending["comprovante_rfb_arquivo_id"] == rfb.arquivo_id
    assert "FORNECEDOR" in pending["palavras_comprovante_banco"]
    assert "13.101" in pending["palavras_comprovante_banco"]
    assert "SIMPLES" in pending["palavras_comprovante_rfb"]


def test_legacy_rule_without_receipt_trigger_can_match_its_receipt_party():
    movement = MovimentoExtrato(historico="Pagamento de Boleto", nome_encontrado="BAMBUNO TECNOLOGIA", natureza="saída")
    receipt = Comprovante(favorecido="Bambuno Tecnologia", beneficiario_final="Sucessodonto Cursos e Treinamentos")
    rule = RegraContabil(tipo_fonte="extrato", tipo_operacao="Crédito", tipo_componente="VALOR_COBRADO", favorecido_normalizado=normalize_name("Pagamento Boleto Sucessodonto Cursos e Treinamentos"))

    assert rule_matches_movement(rule, movement, receipt, "VALOR_COBRADO")


def test_rule_does_not_match_receipt_payer_as_counterparty():
    movement = MovimentoExtrato(historico="13105 109 Pagamento de Boleto", nome_encontrado="QUANTITY SERVICOS E COMERCIO", natureza="Débito")
    receipt = Comprovante(favorecido="Quantity Servicos", beneficiario="Quantity Servicos", pagador="Leandro Barbosa Figueiro")
    rule = RegraContabil(tipo_fonte="extrato", tipo_operacao="Crédito", tipo_componente="VALOR_COBRADO", favorecido_normalizado=normalize_name("Leandro Barbosa Figueiro"))

    assert not rule_matches_movement(rule, movement, receipt, "VALOR_COBRADO")


def test_mixed_text_and_number_trigger_does_not_match_only_by_digits():
    movement = MovimentoExtrato(historico="99021 470 Transferência enviada", nome_encontrado="AIRTON MONTEIRO", natureza="Débito")
    rule = RegraContabil(tipo_fonte="extrato", tipo_operacao="Crédito", tipo_componente="PRINCIPAL", favorecido_normalizado=normalize_name("99021 470 Transferencia enviada Leandro Barbosa Figueiro"))

    assert not rule_matches_movement(rule, movement, None, "PRINCIPAL")


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


def rule_input(trigger="FORNECEDOR", receipt_trigger="", scope="periodo"):
    return RegraContabilInput(gatilho=trigger, gatilho_comprovante=receipt_trigger, natureza="Crédito", tipo_componente="PRINCIPAL", conta_debito="Despesa", conta_credito="Banco", historico="Pagamento", complemento="Extrato", escopo=scope)


def test_new_eligible_rule_is_returned_as_pending_suggestion():
    session, reconciliation, _ = rules_session()

    data = accounting_rules(reconciliation.id, session)
    assert len(data["pendentes"]) == 1
    assert data["resumo"]["razao"] == {"debito": "0.00", "credito": "0.00", "outros": "0.00", "outros_debito": "0.00", "outros_credito": "0.00"}


def test_rule_without_eligible_movement_is_not_saved():
    session, reconciliation, _ = rules_session()

    with pytest.raises(HTTPException, match="não cobre nenhum lançamento"):
        create_accounting_rule(reconciliation.id, rule_input("GATILHO INEXISTENTE"), session)

    assert session.query(RegraContabil).count() == 0


def test_saved_rule_disappears_from_pending_and_is_returned_as_saved_after_refresh():
    session, reconciliation, _ = rules_session()

    create_accounting_rule(reconciliation.id, rule_input(), session)
    first_load = accounting_rules(reconciliation.id, session)
    refreshed_load = accounting_rules(reconciliation.id, session)

    assert first_load["pendentes"] == refreshed_load["pendentes"] == []
    assert len(first_load["salvas"]) == 1
    assert first_load["salvas"][0]["cobertos"] == 1


def test_rule_keywords_match_statement_regardless_of_selected_word_order():
    session, reconciliation, _ = rules_session("PIX FORNECEDOR")

    preview = preview_accounting_rule(reconciliation.id, RegraContabilPreviaInput(gatilho="FORNECEDOR PIX", natureza="Crédito", tipo_componente="PRINCIPAL"), session)
    created = create_accounting_rule(reconciliation.id, rule_input("FORNECEDOR PIX"), session)
    data = accounting_rules(reconciliation.id, session)

    assert preview["quantidade"] == 1
    assert created["movimentos_aplicados"] == 1
    assert data["pendentes"] == []
    assert data["salvas"][0]["gatilho"] == "FORNECEDOR PIX"
    assert data["salvas"][0]["cobertos"] == 1


def test_rule_created_in_one_period_does_not_apply_to_another_period():
    session, reconciliation, _ = rules_session()
    next_period = Conciliacao(cliente_id=reconciliation.cliente_id, banco=reconciliation.banco, data_inicio=date(2024, 2, 1), data_fim=date(2024, 2, 29))
    session.add(next_period); session.flush()
    file = Arquivo(conciliacao_id=next_period.id, tipo_documento="extrato", banco_selecionado=next_period.banco, nome_original="fevereiro.pdf", caminho="/tmp/fevereiro.pdf")
    session.add(file); session.flush()
    session.add(MovimentoExtrato(conciliacao_id=next_period.id, arquivo_id=file.id, pagina_numero=1, data=date(2024, 2, 2), historico="PIX FORNECEDOR", valor=Decimal("20.00"), natureza="saída"))
    session.commit()
    create_accounting_rule(reconciliation.id, rule_input(), session)

    data = accounting_rules(next_period.id, session)

    assert len(data["pendentes"]) == 1
    assert data["salvas"] == []


def test_global_rule_created_in_one_period_applies_to_next_period():
    session, reconciliation, _ = rules_session()
    next_period = Conciliacao(cliente_id=reconciliation.cliente_id, banco=reconciliation.banco, data_inicio=date(2024, 2, 1), data_fim=date(2024, 2, 29))
    session.add(next_period); session.flush()
    file = Arquivo(conciliacao_id=next_period.id, tipo_documento="extrato", banco_selecionado=next_period.banco, nome_original="fevereiro.pdf", caminho="/tmp/fevereiro.pdf")
    session.add(file); session.flush()
    session.add(MovimentoExtrato(conciliacao_id=next_period.id, arquivo_id=file.id, pagina_numero=1, data=date(2024, 2, 2), historico="PIX FORNECEDOR", valor=Decimal("20.00"), natureza="saída"))
    session.commit()

    create_accounting_rule(reconciliation.id, rule_input(scope="global"), session)
    data = accounting_rules(next_period.id, session)

    assert data["pendentes"] == []
    assert len(data["salvas"]) == 1
    assert data["salvas"][0]["escopo"] == "global"
    assert data["salvas"][0]["cobertos"] == 1
    assert data["salvas"][0]["movimentos"][0]["valor"] == "20.00"


def test_accounting_rule_input_defaults_to_global_scope():
    session, reconciliation, _ = rules_session()
    payload = RegraContabilInput(gatilho="FORNECEDOR", natureza="Crédito", tipo_componente="PRINCIPAL", conta_debito="Despesa", conta_credito="Banco", historico="Pagamento")

    created = create_accounting_rule(reconciliation.id, payload, session)

    assert session.get(RegraContabil, created["id"]).escopo == "global"


def test_backend_preview_and_save_match_beneficiary_final_trigger():
    session, reconciliation, movement = rules_session("PAGAMENTO DE BOLETO")
    file = session.get(Arquivo, movement.arquivo_id)
    receipt = Comprovante(conciliacao_id=reconciliation.id, arquivo_id=file.id, pagina_numero=1, favorecido="Operadora", beneficiario_final="Telefone TIM")
    session.add(receipt); session.flush()
    match = Correspondencia(conciliacao_id=reconciliation.id, movimento_extrato_id=movement.id, comprovante_id=receipt.id)
    session.add(match); session.flush()
    session.add(LancamentoContabil(correspondencia_id=match.id, componente="VALOR_COBRADO", valor=movement.valor, origem="comprovante", status="pendente_regra")); session.commit()

    preview = preview_accounting_rule(reconciliation.id, RegraContabilPreviaInput(gatilho="telefone TIM", natureza="Crédito", tipo_componente="PRINCIPAL"), session)
    created = create_accounting_rule(reconciliation.id, rule_input("telefone TIM"), session)

    assert preview["quantidade"] == 1
    assert preview["lancamentos"][0]["fonte"] == "Beneficiário final"
    assert created["movimentos_aplicados"] == 1


def test_rule_preview_uses_batched_queries_for_large_period():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = Cliente(nome="Cliente")
    session.add(client); session.flush()
    reconciliation = Conciliacao(cliente_id=client.id, banco="Santander", data_inicio=date(2024, 1, 1), data_fim=date(2024, 1, 31))
    session.add(reconciliation); session.flush()
    file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="extrato", banco_selecionado="Santander", nome_original="extrato.pdf", caminho="/tmp/extrato.pdf")
    session.add(file); session.flush()
    for number in range(80):
        movement = MovimentoExtrato(conciliacao_id=reconciliation.id, arquivo_id=file.id, pagina_numero=1, data=date(2024, 1, 2), historico=f"PIX FORNECEDOR {number}", valor=Decimal("10.00"), natureza="saída")
        session.add(movement); session.flush()
        match = Correspondencia(conciliacao_id=reconciliation.id, movimento_extrato_id=movement.id)
        session.add(match); session.flush()
        session.add(LancamentoContabil(correspondencia_id=match.id, componente="PRINCIPAL", valor=movement.valor, status="pendente"))
    session.commit()
    queries = []
    event.listen(engine, "before_cursor_execute", lambda *args: queries.append(1))

    preview = preview_accounting_rule(reconciliation.id, RegraContabilPreviaInput(gatilho="PIX FORNECEDOR", natureza="Crédito", tipo_componente="PRINCIPAL"), session)

    assert preview["quantidade"] == 80
    assert len(queries) <= 5


def test_accounting_rules_load_uses_batched_queries_for_large_period():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = Cliente(nome="Cliente")
    session.add(client); session.flush()
    reconciliation = Conciliacao(cliente_id=client.id, banco="Santander", data_inicio=date(2024, 1, 1), data_fim=date(2024, 1, 31))
    session.add(reconciliation); session.flush()
    file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="extrato", banco_selecionado="Santander", nome_original="extrato.pdf", caminho="/tmp/extrato.pdf")
    session.add(file); session.flush()
    rule = RegraContabil(cliente_id=client.id, conciliacao_id=reconciliation.id, banco="Santander", tipo_fonte="extrato", tipo_operacao="Crédito", favorecido_normalizado=normalize_name("PIX FORNECEDOR"), conta_debito="Despesa", conta_credito="Banco", historico="Pagamento")
    session.add(rule); session.flush()
    for number in range(80):
        movement = MovimentoExtrato(conciliacao_id=reconciliation.id, arquivo_id=file.id, pagina_numero=1, data=date(2024, 1, 2), historico=f"PIX FORNECEDOR {number}", valor=Decimal("10.00"), natureza="saída")
        session.add(movement); session.flush()
        receipt = Comprovante(conciliacao_id=reconciliation.id, arquivo_id=file.id, pagina_numero=1, favorecido=f"Fornecedor {number}")
        session.add(receipt); session.flush()
        match = Correspondencia(conciliacao_id=reconciliation.id, movimento_extrato_id=movement.id, comprovante_id=receipt.id)
        session.add(match); session.flush()
        session.add(LancamentoContabil(correspondencia_id=match.id, regra_contabil_id=rule.id, componente="PRINCIPAL", valor=movement.valor, conta_debito="Despesa", conta_credito="Banco", historico="Pagamento", status="aplicado_por_regra"))
    session.commit()
    queries = []
    event.listen(engine, "before_cursor_execute", lambda *args: queries.append(1))

    data = accounting_rules(reconciliation.id, session)

    assert len(data["salvas"]) == 1
    assert data["salvas"][0]["cobertos"] == 80
    assert len(queries) <= 18


def test_apply_accounting_rules_uses_batched_queries_for_large_period():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = Cliente(nome="Cliente")
    session.add(client); session.flush()
    reconciliation = Conciliacao(cliente_id=client.id, banco="Santander", data_inicio=date(2024, 1, 1), data_fim=date(2024, 1, 31))
    session.add(reconciliation); session.flush()
    file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="extrato", banco_selecionado="Santander", nome_original="extrato.pdf", caminho="/tmp/extrato.pdf")
    session.add(file); session.flush()
    session.add(RegraContabil(cliente_id=client.id, conciliacao_id=reconciliation.id, banco="Santander", tipo_fonte="extrato", tipo_operacao="Crédito", favorecido_normalizado=normalize_name("PIX FORNECEDOR"), conta_debito="Despesa", conta_credito="Banco", historico="Pagamento"))
    for number in range(80):
        movement = MovimentoExtrato(conciliacao_id=reconciliation.id, arquivo_id=file.id, pagina_numero=1, data=date(2024, 1, 2), historico=f"PIX FORNECEDOR {number}", valor=Decimal("10.00"), natureza="saída")
        session.add(movement); session.flush()
        match = Correspondencia(conciliacao_id=reconciliation.id, movimento_extrato_id=movement.id)
        session.add(match); session.flush()
        session.add(LancamentoContabil(correspondencia_id=match.id, componente="PRINCIPAL", valor=movement.valor, status="pendente"))
    session.commit()
    queries = []
    event.listen(engine, "before_cursor_execute", lambda *args: queries.append(1))

    assert apply_accounting_rules(reconciliation, session) == 80
    assert len(queries) <= 10


def test_result_load_uses_batched_queries_for_large_period():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = Cliente(nome="Cliente")
    session.add(client); session.flush()
    reconciliation = Conciliacao(cliente_id=client.id, banco="Santander", data_inicio=date(2024, 1, 1), data_fim=date(2024, 1, 31))
    session.add(reconciliation); session.flush()
    file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="extrato", banco_selecionado="Santander", nome_original="extrato.pdf", caminho="/tmp/extrato.pdf")
    session.add(file); session.flush()
    rule = RegraContabil(cliente_id=client.id, conciliacao_id=reconciliation.id, banco="Santander", tipo_fonte="extrato", tipo_operacao="Crédito", favorecido_normalizado=normalize_name("PIX FORNECEDOR"), conta_debito="Despesa", conta_credito="Banco", historico="Pagamento")
    session.add(rule); session.flush()
    for number in range(80):
        movement = MovimentoExtrato(conciliacao_id=reconciliation.id, arquivo_id=file.id, pagina_numero=1, data=date(2024, 1, 2), historico=f"PIX FORNECEDOR {number}", valor=Decimal("10.00"), natureza="saída")
        receipt = Comprovante(conciliacao_id=reconciliation.id, arquivo_id=file.id, pagina_numero=1, data=date(2024, 1, 2), favorecido=f"Fornecedor {number}", valor_pago=Decimal("10.00"), tipo_operacao="PIX")
        session.add_all([movement, receipt]); session.flush()
        match = Correspondencia(conciliacao_id=reconciliation.id, movimento_extrato_id=movement.id, comprovante_id=receipt.id, regra_contabil_id=rule.id, status="Conciliado")
        session.add(match); session.flush()
        session.add(LancamentoContabil(correspondencia_id=match.id, regra_contabil_id=rule.id, componente="PRINCIPAL", valor=movement.valor, conta_debito="Despesa", conta_credito="Banco", historico="Pagamento", status="aplicado_por_regra"))
    session.commit()
    queries = []
    event.listen(engine, "before_cursor_execute", lambda *args: queries.append(1))

    rows = result(reconciliation.id, session)

    assert len(rows) == 80
    assert rows[0]["lancamentos"][0]["historico"] == "Pagamento"
    assert len(queries) <= 8


def test_persisted_covered_entry_does_not_return_zero_eligible_suggestion():
    session, reconciliation, movement = rules_session("PIX ATUAL")
    legacy_rule = RegraContabil(cliente_id=reconciliation.cliente_id, conciliacao_id=reconciliation.id, banco="Santander", tipo_fonte="extrato", tipo_operacao="Crédito", favorecido_normalizado=normalize_name("FORNECEDOR ANTIGO"), conta_debito="Despesa", conta_credito="Banco", historico="Pagamento")
    session.add(legacy_rule); session.flush()
    match = Correspondencia(conciliacao_id=reconciliation.id, movimento_extrato_id=movement.id, regra_contabil_id=legacy_rule.id)
    session.add(match); session.flush()
    session.add(LancamentoContabil(correspondencia_id=match.id, regra_contabil_id=legacy_rule.id, componente="PRINCIPAL", valor=movement.valor, status="aplicado_por_regra"))

    data = accounting_rules(reconciliation.id, session)

    assert len(data["pendentes"]) == 1
    assert len(data["salvas"]) == 1
    assert data["salvas"][0]["cobertos"] == 0
    assert data["integridade"]["movimentos_incompletos"][0]["movimento_id"] == movement.id


def test_saved_rule_preview_counts_its_currently_covered_entries_when_editing_trigger():
    session, reconciliation, _ = rules_session("821 PIX RECEBIDO")
    created = create_accounting_rule(reconciliation.id, rule_input("821 PIX RECEBIDO"), session)

    preview = preview_accounting_rule(reconciliation.id, RegraContabilPreviaInput(gatilho="Pix", natureza="Crédito", tipo_componente="PRINCIPAL", regra_id=created["id"]), session)

    assert preview["quantidade"] == 1
    assert preview["motivo"] == ""


def test_saved_rule_preview_can_recover_complete_entries_left_without_active_rule():
    session, reconciliation, movement = rules_session("821 PIX RECEBIDO")
    created = create_accounting_rule(reconciliation.id, rule_input("821 PIX RECEBIDO"), session)
    match = session.query(Correspondencia).filter_by(movimento_extrato_id=movement.id).one()
    entry = session.query(LancamentoContabil).filter_by(correspondencia_id=match.id).one()
    entry.regra_contabil_id = None
    match.regra_contabil_id = None
    session.commit()

    preview = preview_accounting_rule(reconciliation.id, RegraContabilPreviaInput(gatilho="Pix", natureza="Crédito", tipo_componente="PRINCIPAL", regra_id=created["id"]), session)

    assert preview["quantidade"] == 1
    assert preview["motivo"] == ""


def test_deleting_saved_rule_recalculates_its_pending_suggestion():
    session, reconciliation, _ = rules_session()
    created = create_accounting_rule(reconciliation.id, rule_input(scope="global"), session)

    delete_accounting_rule(created["id"], session)

    assert len(accounting_rules(reconciliation.id, session)["pendentes"]) == 1


def test_ignoring_global_rule_only_removes_it_from_current_period_and_can_restore():
    session, reconciliation, _ = rules_session()
    created = create_accounting_rule(reconciliation.id, rule_input(scope="global"), session)

    removed = ignore_rule_in_period(reconciliation.id, created["id"], session)

    rule = session.get(RegraContabil, created["id"])
    assert rule.ativo is True
    assert session.query(RegraContabilExcecao).filter_by(regra_contabil_id=rule.id, conciliacao_id=reconciliation.id).count() == 1
    assert removed["regras"]["ignoradas"]
    assert accounting_rules(reconciliation.id, session)["salvas"] == []
    assert len(accounting_rules(reconciliation.id, session)["pendentes"]) == 1
    apply_accounting_rules(reconciliation, session)
    assert accounting_rules(reconciliation.id, session)["salvas"] == []

    restored = restore_rule_in_period(reconciliation.id, created["id"], session)

    assert "restaurada" in restored["message"]
    assert session.query(RegraContabilExcecao).filter_by(regra_contabil_id=rule.id, conciliacao_id=reconciliation.id).count() == 0
    assert len(accounting_rules(reconciliation.id, session)["salvas"]) == 1


def test_creating_equivalent_hidden_rule_restores_existing_rule_instead_of_blocking():
    session, reconciliation, _ = rules_session()
    created = create_accounting_rule(reconciliation.id, rule_input(scope="global"), session)
    ignore_rule_in_period(reconciliation.id, created["id"], session)

    restored = create_accounting_rule(reconciliation.id, rule_input(scope="global"), session)

    assert restored["id"] == created["id"]
    assert restored["reativada"] is True
    assert restored["movimentos_aplicados"] == 1
    assert session.query(RegraContabil).filter_by(ativo=True).count() == 1
    assert session.query(RegraContabilExcecao).filter_by(regra_contabil_id=created["id"], conciliacao_id=reconciliation.id).count() == 0
    assert len(accounting_rules(reconciliation.id, session)["salvas"]) == 1


def test_global_deletion_returns_affected_periods_and_removes_period_exceptions():
    session, reconciliation, _ = rules_session()
    created = create_accounting_rule(reconciliation.id, rule_input(scope="global"), session)
    ignore_rule_in_period(reconciliation.id, created["id"], session)

    deleted = delete_accounting_rule_for_reconciliation(reconciliation.id, created["id"], session)

    assert deleted["periodos_afetados"] == 1
    assert session.get(RegraContabil, created["id"]).ativo is False
    assert session.query(RegraContabilExcecao).filter_by(regra_contabil_id=created["id"]).count() == 0


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


def test_rule_save_rolls_back_when_accounting_entry_creation_fails(monkeypatch):
    session, reconciliation, _ = rules_session()

    monkeypatch.setattr(routes, "apply_accounting_rules", lambda *_: (_ for _ in ()).throw(RuntimeError("falha")))

    with pytest.raises(RuntimeError, match="falha"):
        create_accounting_rule(reconciliation.id, rule_input(), session)
    assert session.query(RegraContabil).count() == 0
    assert session.query(LancamentoContabil).count() == 0


def test_equal_date_and_beneficiary_movements_keep_separate_accounting_entries():
    session, reconciliation, first = rules_session("PAGAMENTO BOLETO SUCESSODONTO")
    second = MovimentoExtrato(conciliacao_id=reconciliation.id, arquivo_id=first.arquivo_id, pagina_numero=1, data=first.data, historico=first.historico, valor=Decimal("1000.00"), natureza="saída")
    session.add(second); session.flush()

    create_accounting_rule(reconciliation.id, rule_input("SUCESSODONTO"), session)

    entries = session.query(LancamentoContabil).filter_by(status="aplicado_por_regra").all()
    assert sorted(entry.valor for entry in entries) == [Decimal("12.50"), Decimal("1000.00")]
    assert len({entry.correspondencia_id for entry in entries}) == 2


def test_csv_is_blocked_when_integrity_reports_an_unbalanced_reason(monkeypatch):
    session, reconciliation, _ = rules_session()
    session.add(ContaBancaria(cliente_id=reconciliation.cliente_id, banco=reconciliation.banco, conta_contabil="Banco"))
    monkeypatch.setattr(routes, "accounting_integrity", lambda *_: {"debito": Decimal("100.00"), "credito": Decimal("0.00"), "diferenca": Decimal("100.00"), "movimentos_incompletos": [], "csv_permitido": False, "lancamentos_validos": []})

    with pytest.raises(HTTPException, match=r"diferença de R\$ 100.00"):
        accounting_csv(reconciliation.id, session)


def test_dynamic_reconciliation_endpoints_are_never_cached():
    session, reconciliation, _ = rules_session()

    for endpoint in (result, review, unused_documents):
        response = Response()
        endpoint(reconciliation.id, session, response)
        assert response.headers["cache-control"] == "no-store, no-cache, must-revalidate"


def test_discount_is_accounted_as_other_and_exported_in_main_csv():
    session, reconciliation, movement = rules_session()
    match = Correspondencia(conciliacao_id=reconciliation.id, movimento_extrato_id=movement.id)
    session.add(match); session.flush()
    session.add_all([
        LancamentoContabil(correspondencia_id=match.id, componente="VALOR_COBRADO", valor=Decimal("12.50"), conta_debito="Despesa", conta_credito="Banco", historico="Pagamento", ordem=1, status="editado_manual"),
        LancamentoContabil(correspondencia_id=match.id, componente="DESCONTO", efeito_no_total="SOMA", valor=Decimal("2.50"), conta_debito="Descontos", conta_credito="Despesa", historico="Desconto obtido", ordem=2, status="editado_manual"),
    ])
    session.add(ContaBancaria(cliente_id=reconciliation.cliente_id, banco=reconciliation.banco, conta_contabil="Banco"))
    session.commit()

    integrity = accounting_integrity(reconciliation, session)
    csv = accounting_csv(reconciliation.id, session).body.decode("utf-8-sig")

    assert (integrity["debito"], integrity["credito"], integrity["outros"], integrity["outros_debito"], integrity["outros_credito"]) == (Decimal("0.00"), Decimal("12.50"), Decimal("2.50"), Decimal("2.50"), Decimal("0.00"))
    assert csv.splitlines() == ["Data;Debito;Credito;Historico;Valor;Complemento", "02/01/2024;Despesa;Banco;Pagamento;12.50;", "02/01/2024;Descontos;Despesa;Desconto obtido;2.50;"]


def test_csv_is_ordered_by_date_and_names_the_client_bank_account():
    session, reconciliation, later_movement = rules_session()
    earlier_movement = MovimentoExtrato(conciliacao_id=reconciliation.id, arquivo_id=later_movement.arquivo_id, pagina_numero=1, data=date(2024, 1, 1), historico="PIX ANTERIOR", valor=Decimal("10.00"), natureza="saída")
    session.add(earlier_movement); session.flush()
    later_match = Correspondencia(conciliacao_id=reconciliation.id, movimento_extrato_id=later_movement.id)
    earlier_match = Correspondencia(conciliacao_id=reconciliation.id, movimento_extrato_id=earlier_movement.id)
    session.add_all([later_match, earlier_match]); session.flush()
    session.add_all([
        LancamentoContabil(correspondencia_id=later_match.id, valor=Decimal("12.50"), conta_debito="254", conta_credito="219", historico="348", status="editado_manual"),
        LancamentoContabil(correspondencia_id=earlier_match.id, valor=Decimal("10.00"), conta_debito="254", conta_credito="219", historico="348", status="editado_manual"),
    ])
    session.add(ContaBancaria(cliente_id=reconciliation.cliente_id, banco="Santander", conta_contabil="219 - Banco", agencia="1234-5", conta="98765-4"))
    session.commit()

    response = accounting_csv(reconciliation.id, session)

    assert response.body.decode("utf-8-sig").splitlines()[1:3] == ["01/01/2024;254;219;348;10.00;", "02/01/2024;254;219;348;12.50;"]
    assert response.headers["content-disposition"] == 'attachment; filename="0124219.csv"'


def test_saved_discount_rule_is_listed_after_being_applied_as_other():
    session, reconciliation, movement = rules_session()
    match = Correspondencia(conciliacao_id=reconciliation.id, movimento_extrato_id=movement.id)
    session.add(match); session.flush()
    session.add(LancamentoContabil(correspondencia_id=match.id, componente="DESCONTO", efeito_no_total="OUTROS", valor=Decimal("2.50"), origem="comprovante", status="pendente_regra"))
    session.commit()

    create_accounting_rule(reconciliation.id, RegraContabilInput(gatilho="FORNECEDOR", natureza="Crédito", tipo_componente="DESCONTO", conta_debito="Descontos", conta_credito="Despesa", historico="Desconto obtido"), session)

    data = accounting_rules(reconciliation.id, session)
    assert data["pendentes"] == []
    assert [(rule["tipo_componente"], rule["cobertos"]) for rule in data["salvas"]] == [("DESCONTO", 1)]


def test_saved_rules_keep_each_component_value_in_document_order():
    session, reconciliation, movement = rules_session()
    match = Correspondencia(conciliacao_id=reconciliation.id, movimento_extrato_id=movement.id)
    session.add(match); session.flush()
    rules = [
        RegraContabil(cliente_id=reconciliation.cliente_id, conciliacao_id=reconciliation.id, banco=reconciliation.banco, tipo_fonte="extrato", tipo_operacao="Crédito", tipo_componente=component, favorecido_normalizado=normalize_name("FORNECEDOR"), conta_debito="Débito", conta_credito="Crédito", historico=component)
        for component in ("PRINCIPAL", "MULTA", "JUROS")
    ]
    session.add_all(rules); session.flush()
    session.add_all([
        LancamentoContabil(correspondencia_id=match.id, regra_contabil_id=rules[0].id, componente="PRINCIPAL", valor=Decimal("100.00"), conta_debito="Débito", conta_credito="Crédito", historico="Principal", ordem=1, status="aplicado_por_regra"),
        LancamentoContabil(correspondencia_id=match.id, regra_contabil_id=rules[1].id, componente="MULTA", valor=Decimal("3.00"), conta_debito="Débito", conta_credito="Crédito", historico="Multa", ordem=2, status="aplicado_por_regra"),
        LancamentoContabil(correspondencia_id=match.id, regra_contabil_id=rules[2].id, componente="JUROS", valor=Decimal("2.00"), conta_debito="Débito", conta_credito="Crédito", historico="Juros", ordem=3, status="aplicado_por_regra"),
    ])
    session.commit()

    data = accounting_rules(reconciliation.id, session)

    assert [(rule["tipo_componente"], rule["cobertos"], rule["movimentos"][0]["valor"]) for rule in data["salvas"]] == [("PRINCIPAL", 1, "100.00"), ("MULTA", 1, "3.00"), ("JUROS", 1, "2.00")]


def test_remaining_discount_stays_identified_as_a_compound_pending_component():
    session, reconciliation, movement = rules_session()
    match = Correspondencia(conciliacao_id=reconciliation.id, movimento_extrato_id=movement.id)
    session.add(match); session.flush()
    session.add_all([
        LancamentoContabil(correspondencia_id=match.id, componente="VALOR_COBRADO", valor=Decimal("12.50"), origem="comprovante", status="pendente_regra"),
        LancamentoContabil(correspondencia_id=match.id, componente="DESCONTO", valor=Decimal("2.50"), origem="comprovante", efeito_no_total="OUTROS", status="pendente_regra"),
    ])
    session.commit()

    create_accounting_rule(reconciliation.id, RegraContabilInput(gatilho="FORNECEDOR", natureza="Crédito", tipo_componente="VALOR_COBRADO", conta_debito="Despesa", conta_credito="Banco", historico="Pagamento"), session)

    pending = accounting_rules(reconciliation.id, session)["pendentes"]
    assert [(item["tipo_componente"], item["movimento_composto"], item["componentes_documento"], item["componentes_cobertos"]) for item in pending] == [("DESCONTO", True, ["VALOR_COBRADO", "DESCONTO"], [{"componente": "VALOR_COBRADO", "valor": "12.50"}])]


def test_zero_value_component_is_not_listed_for_accounting_rules():
    session, reconciliation, movement = rules_session()
    match = Correspondencia(conciliacao_id=reconciliation.id, movimento_extrato_id=movement.id)
    session.add(match); session.flush()
    session.add_all([
        LancamentoContabil(correspondencia_id=match.id, componente="MULTA", valor=Decimal("18.82"), origem="rfb", status="pendente_regra"),
        LancamentoContabil(correspondencia_id=match.id, componente="JUROS", valor=Decimal("0.00"), origem="rfb", status="pendente_regra"),
    ])
    session.commit()

    pending = accounting_rules(reconciliation.id, session)["pendentes"]

    assert [(item["tipo_componente"], item["valor"]) for item in pending] == [("MULTA", "18.82")]


def test_clearing_all_rules_recalculates_pending_movements_without_deleting_them():
    session, reconciliation, movement = rules_session()
    create_accounting_rule(reconciliation.id, rule_input(), session)

    delete_all_accounting_rules(reconciliation.id, session)

    data = accounting_rules(reconciliation.id, session)
    assert data["salvas"] == []
    assert len(data["pendentes"]) == 1
    assert session.get(MovimentoExtrato, movement.id) is not None
    entry = session.query(LancamentoContabil).one()
    assert (entry.regra_contabil_id, entry.status) == (None, "pendente")


def test_clearing_all_rules_removes_entries_left_by_inactive_rules():
    session, reconciliation, _ = rules_session()
    created = create_accounting_rule(reconciliation.id, rule_input(), session)
    session.get(RegraContabil, created["id"]).ativo = False
    session.commit()

    delete_all_accounting_rules(reconciliation.id, session)

    assert session.query(LancamentoContabil).filter_by(status="aplicado_por_regra").count() == 0
    assert accounting_rules(reconciliation.id, session)["resumo"]["razao"] == {"debito": "0.00", "credito": "0.00", "outros": "0.00", "outros_debito": "0.00", "outros_credito": "0.00"}


def test_clearing_zero_covered_rules_hides_only_current_period_and_keeps_global_rule():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = Cliente(nome="Cliente")
    session.add(client); session.flush()
    january = Conciliacao(cliente_id=client.id, banco="Banco do Brasil", data_inicio=date(2024, 1, 1), data_fim=date(2024, 1, 31))
    february = Conciliacao(cliente_id=client.id, banco="Banco do Brasil", data_inicio=date(2024, 2, 1), data_fim=date(2024, 2, 29))
    session.add_all([january, february]); session.flush()
    january_file = Arquivo(conciliacao_id=january.id, tipo_documento="extrato", banco_selecionado=january.banco, nome_original="jan.pdf", caminho="/tmp/jan.pdf")
    february_file = Arquivo(conciliacao_id=february.id, tipo_documento="extrato", banco_selecionado=february.banco, nome_original="fev.pdf", caminho="/tmp/fev.pdf")
    session.add_all([january_file, february_file]); session.flush()
    session.add_all([
        MovimentoExtrato(conciliacao_id=january.id, arquivo_id=january_file.id, pagina_numero=1, data=date(2024, 1, 5), historico="PIX FORNECEDOR", valor=Decimal("100.00"), natureza="saída"),
        MovimentoExtrato(conciliacao_id=february.id, arquivo_id=february_file.id, pagina_numero=1, data=date(2024, 2, 5), historico="TED OUTRO", valor=Decimal("200.00"), natureza="saída"),
    ])
    session.commit()
    created = create_accounting_rule(january.id, rule_input("PIX", scope="global"), session)

    before = accounting_rules(february.id, session)
    assert before["salvas"][0]["cobertos"] == 0

    response = delete_zero_covered_accounting_rules(february.id, session)

    assert response["quantidade"] == 1
    assert response["regras"]["salvas"] == []
    assert session.get(RegraContabil, created["id"]).ativo is True
    assert session.query(RegraContabilExcecao).filter_by(regra_contabil_id=created["id"], conciliacao_id=february.id).count() == 1
    assert accounting_rules(january.id, session)["salvas"][0]["cobertos"] == 1


def test_deleting_a_rule_immediately_removes_its_value_from_reason():
    session, reconciliation, _ = rules_session()
    created = create_accounting_rule(reconciliation.id, rule_input(), session)

    delete_accounting_rule(created["id"], session)

    assert accounting_rules(reconciliation.id, session)["resumo"]["razao"] == {"debito": "0.00", "credito": "0.00", "outros": "0.00", "outros_debito": "0.00", "outros_credito": "0.00"}


def test_updating_a_rule_to_zero_covered_is_rejected_and_keeps_previous_rule():
    session, reconciliation, _ = rules_session()
    created = create_accounting_rule(reconciliation.id, rule_input(), session)

    with pytest.raises(HTTPException, match="não cobre nenhum lançamento"):
        update_accounting_rule(reconciliation.id, created["id"], rule_input("INEXISTENTE"), session)

    data = accounting_rules(reconciliation.id, session)
    assert data["resumo"]["razao"] == {"debito": "0.00", "credito": "12.50", "outros": "0.00", "outros_debito": "0.00", "outros_credito": "0.00"}
    assert len(data["salvas"]) == 1
    assert data["salvas"][0]["gatilho"] == "FORNECEDOR"
    assert data["salvas"][0]["cobertos"] == 1


def test_inactive_rule_residue_is_excluded_from_reason_and_coverage():
    session, reconciliation, _ = rules_session()
    created = create_accounting_rule(reconciliation.id, rule_input(), session)
    session.get(RegraContabil, created["id"]).ativo = False
    session.commit()

    data = accounting_rules(reconciliation.id, session)

    assert data["resumo"]["razao"] == {"debito": "0.00", "credito": "0.00", "outros": "0.00", "outros_debito": "0.00", "outros_credito": "0.00"}
    assert len(data["pendentes"]) == 1


def test_new_rule_preview_can_cover_entries_left_by_inactive_rule():
    session, reconciliation, _ = rules_session("821 PIX RECEBIDO")
    created = create_accounting_rule(reconciliation.id, rule_input("821 PIX RECEBIDO"), session)
    session.get(RegraContabil, created["id"]).ativo = False
    session.commit()

    preview = preview_accounting_rule(reconciliation.id, RegraContabilPreviaInput(gatilho="Pix", natureza="Crédito", tipo_componente="PRINCIPAL"), session)

    assert preview["quantidade"] == 1
    assert preview["motivo"] == ""


def test_other_bank_rule_never_enters_current_bank_reason():
    session, reconciliation, movement = rules_session()
    foreign_rule = RegraContabil(cliente_id=reconciliation.cliente_id, conciliacao_id=reconciliation.id, banco="Banco do Brasil", tipo_fonte="extrato", tipo_operacao="Crédito", favorecido_normalizado=normalize_name("FORNECEDOR"), conta_debito="Despesa", conta_credito="Banco", historico="Pagamento")
    session.add(foreign_rule); session.flush()
    match = Correspondencia(conciliacao_id=reconciliation.id, movimento_extrato_id=movement.id, regra_contabil_id=foreign_rule.id)
    session.add(match); session.flush()
    session.add(LancamentoContabil(correspondencia_id=match.id, regra_contabil_id=foreign_rule.id, componente="PRINCIPAL", valor=movement.valor, conta_debito="Despesa", conta_credito="Banco", historico="Pagamento", status="aplicado_por_regra"))
    session.commit()

    data = accounting_rules(reconciliation.id, session)

    assert data["resumo"]["razao"] == {"debito": "0.00", "credito": "0.00", "outros": "0.00", "outros_debito": "0.00", "outros_credito": "0.00"}
    assert len(data["pendentes"]) == 1


def test_pdf_export_groups_valid_entries_into_a_report():
    session, reconciliation, _ = rules_session()
    create_accounting_rule(reconciliation.id, RegraContabilInput(gatilho="FORNECEDOR", natureza="Crédito", tipo_componente="PRINCIPAL", conta_debito="1.1.01 - Despesa", conta_credito="1.1.02 - Banco", historico="101 - Pagamento", complemento="Pagamento ao fornecedor conforme extrato"), session)

    response = accounting_pdf(reconciliation.id, session)
    document = fitz.open(stream=response.body, filetype="pdf")
    text = "".join(page.get_text() for page in document)

    assert response.media_type == "application/pdf"
    assert response.body.startswith(b"%PDF")
    assert response.headers["content-disposition"] == 'attachment; filename="lancamentos-contabeis.pdf"'
    assert "Data" in text and "Debito" in text and "Credito" in text and "Historico" in text and "Valor" in text and "Complemento" in text
    assert "1.1.01" in text and "1.1.02" in text and "101" in text
    assert "Pagamento ao fornecedor conforme extrato" in text
