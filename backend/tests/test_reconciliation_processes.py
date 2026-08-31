from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api import routes
from app.api.routes import ContaBancariaClienteInput, RegraFonteInput, accounting_integrity, accounting_rules, apply_accounting_rules, banks, client_bank_accounts, create_reconciliation_process, create_source_accounting_rule, delete_client_bank_account, delete_process_bank, delete_reconciliation_process, list_reconciliation_processes, reconcile, reprocess_document, result, resume_process_bank, review, save_client_bank_account, source_accounting_csv, source_accounting_rules, unused_documents
from app.core.database import Base
from app.models import Arquivo, Cliente, Comprovante, Conciliacao, ContaBancaria, Correspondencia, LancamentoContabil, MovimentoExtrato, NotaFiscal, ProcessoConciliacao, RegraContabil, RegraContabilExcecao
from app.services.normalization import normalize_name
from app.api.routes import ProcessoBancoInput, ProcessoConciliacaoInput


def test_getnet_is_hidden_from_new_bank_list_but_legacy_processes_still_work():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = Cliente(nome="Cliente")
    session.add(client); session.commit()

    assert "Santander" in banks()
    assert "Vendas com Cartão" not in banks()
    assert "Comissões Getnet" not in banks()
    assert "Notas" in banks()

    process = create_reconciliation_process(ProcessoConciliacaoInput(cliente_id=client.id, data_inicio=date(2024, 1, 1), data_fim=date(2024, 1, 31)), session)
    legacy = resume_process_bank(process["id"], ProcessoBancoInput(banco="Comissões Getnet"), session)

    assert legacy["banco"] == "Comissões Getnet"
    assert legacy["processo_id"] == process["id"]


def test_scanned_loan_pdf_without_tesseract_reports_ocr_requirement(monkeypatch, tmp_path):
    monkeypatch.setattr(routes.shutil, "which", lambda command: None)
    monkeypatch.setattr(routes, "local_tesseract_path", lambda: None)

    with pytest.raises(ValueError, match="PDF escaneado sem texto pesquisável"):
        routes.extract_scanned_pdf_pages(tmp_path / "emprestimo.pdf")


def test_process_resumes_the_same_bank_without_cross_bank_rule_source():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = Cliente(nome="Cliente")
    session.add(client); session.commit()
    process = create_reconciliation_process(ProcessoConciliacaoInput(cliente_id=client.id, data_inicio=date(2024, 1, 1), data_fim=date(2024, 1, 31), banco="Santander"), session)
    santander = resume_process_bank(process["id"], ProcessoBancoInput(banco="Santander"), session)
    bradesco = resume_process_bank(process["id"], ProcessoBancoInput(banco="Bradesco"), session)
    assert santander["id"] == process["bancos"][0]["id"]
    assert santander["processo_id"] == bradesco["processo_id"] == process["id"]

    statement = Arquivo(conciliacao_id=bradesco["id"], tipo_documento="extrato", banco_selecionado="Bradesco", nome_original="extrato.pdf", caminho="/tmp/extrato.pdf")
    session.add(statement); session.flush()
    session.add(MovimentoExtrato(conciliacao_id=bradesco["id"], arquivo_id=statement.id, pagina_numero=1, data=date(2024, 1, 2), historico="PIX FORNECEDOR", natureza="saída"))
    session.add(RegraContabil(cliente_id=client.id, conciliacao_id=santander["id"], banco="Santander", tipo_fonte="extrato", tipo_operacao="saída", favorecido_normalizado=normalize_name("PIX"), conta_debito="Despesa", conta_credito="Banco", historico="Pagamento"))
    session.commit()

    rules = accounting_rules(bradesco["id"], session)
    assert rules["pendentes"][0].get("regra_compartilhada") is None
    assert rules["salvas"] == []


def test_process_creation_reuses_existing_period_and_adds_requested_module():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = Cliente(nome="Cliente")
    session.add(client); session.commit()

    first = create_reconciliation_process(ProcessoConciliacaoInput(cliente_id=client.id, data_inicio=date(2024, 1, 1), data_fim=date(2024, 1, 31), banco="Banco do Brasil"), session)
    second = create_reconciliation_process(ProcessoConciliacaoInput(cliente_id=client.id, data_inicio=date(2024, 1, 1), data_fim=date(2024, 1, 31), banco="Folha de Pagamento"), session)

    assert second["id"] == first["id"]
    assert session.query(ProcessoConciliacao).count() == 1
    assert {item["banco"] for item in second["bancos"]} == {"Banco do Brasil", "Folha de Pagamento"}


def test_process_list_includes_compact_rule_progress_by_bank():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = Cliente(nome="Cliente")
    session.add(client); session.commit()
    process = create_reconciliation_process(ProcessoConciliacaoInput(cliente_id=client.id, data_inicio=date(2024, 1, 1), data_fim=date(2024, 1, 31), banco="Banco do Brasil"), session)
    reconciliation_id = process["bancos"][0]["id"]
    file = Arquivo(conciliacao_id=reconciliation_id, tipo_documento="extrato", banco_selecionado="Banco do Brasil", nome_original="extrato.pdf", caminho="/tmp/extrato.pdf")
    session.add(file); session.flush()
    covered = MovimentoExtrato(conciliacao_id=reconciliation_id, arquivo_id=file.id, pagina_numero=1, data=date(2024, 1, 2), historico="PIX", natureza="Crédito")
    pending = MovimentoExtrato(conciliacao_id=reconciliation_id, arquivo_id=file.id, pagina_numero=1, data=date(2024, 1, 3), historico="TED", natureza="Débito")
    session.add_all([covered, pending]); session.flush()
    match = Correspondencia(conciliacao_id=reconciliation_id, movimento_extrato_id=covered.id)
    session.add(match); session.flush()
    rule = RegraContabil(cliente_id=client.id, conciliacao_id=reconciliation_id, banco="Banco do Brasil", tipo_fonte="extrato", tipo_operacao="Crédito", favorecido_normalizado=normalize_name("PIX"), conta_debito="Banco", conta_credito="Receita", historico="Receita")
    session.add(rule); session.flush()
    session.add(LancamentoContabil(correspondencia_id=match.id, regra_contabil_id=rule.id, valor=Decimal("10.00"), status="aplicado_por_regra"))
    session.commit()

    data = list_reconciliation_processes(db=session)
    progress = data[0]["bancos"][0]["progresso_regras"]

    assert progress == {"total": 2, "cobertos": 1, "percentual": 50}


def test_basa_review_exposes_initial_available_balance_as_previous_balance():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = Cliente(nome="Cliente")
    session.add(client); session.commit()
    reconciliation = Conciliacao(cliente_id=client.id, banco="BASA", data_inicio=date(2024, 1, 1), data_fim=date(2024, 1, 31))
    session.add(reconciliation); session.flush()
    file = Arquivo(
        conciliacao_id=reconciliation.id,
        tipo_documento="extrato",
        banco_selecionado="BASA",
        nome_original="01.24.pdf",
        caminho="/tmp/01.24.pdf",
        texto_bruto="Titular : CENTRO ODONTOLOGICO FIGUEIRO Saldo Disponível Inicial: 40.363,30",
    )
    session.add(file); session.commit()

    data = review(reconciliation.id, session)
    rules = accounting_rules(reconciliation.id, session)

    assert routes.extract_basa_initial_balance(file.texto_bruto) == Decimal("40363.30")
    assert data["saldos"] == {"saldo_anterior": "R$ 40.363,30"}
    assert rules["resumo"]["extrato"]["saldo_anterior"] == "40363.30"


def test_manual_complementary_entries_with_same_component_are_not_merged():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = Cliente(nome="Cliente")
    session.add(client); session.commit()
    reconciliation = Conciliacao(cliente_id=client.id, banco="Banco do Brasil", data_inicio=date(2024, 1, 1), data_fim=date(2024, 1, 31))
    session.add(reconciliation); session.flush()
    file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="extrato", banco_selecionado="Banco do Brasil", nome_original="extrato.pdf", caminho="/tmp/extrato.pdf")
    session.add(file); session.flush()
    movement = MovimentoExtrato(conciliacao_id=reconciliation.id, arquivo_id=file.id, pagina_numero=1, data=date(2024, 1, 2), historico="AJUSTE", valor=Decimal("15.00"), natureza="Débito")
    session.add(movement); session.flush()
    match = Correspondencia(conciliacao_id=reconciliation.id, movimento_extrato_id=movement.id)
    session.add(match); session.flush()
    session.add_all([
        LancamentoContabil(correspondencia_id=match.id, componente="OUTRO", origem="manual", valor=Decimal("10.00"), conta_debito="1", conta_credito="2", historico="Complementar A", status="editado_manual", ordem=1),
        LancamentoContabil(correspondencia_id=match.id, componente="OUTRO", origem="manual", valor=Decimal("5.00"), conta_debito="1", conta_credito="2", historico="Complementar B", status="editado_manual", ordem=2),
    ])
    session.commit()

    row = result(reconciliation.id, session)[0]
    integrity = accounting_integrity(reconciliation, session)

    assert [item["historico"] for item in row["lancamentos"]] == ["Complementar A", "Complementar B"]
    assert len(integrity["lancamentos_validos"]) == 2


def test_client_bank_account_crud_preserves_accounting_account():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = Cliente(nome="Cliente")
    session.add(client); session.flush()
    session.add(ContaBancaria(cliente_id=client.id, banco="Santander", conta_contabil="1.1.02 - Banco"))
    session.commit()

    saved = save_client_bank_account(client.id, "Santander", ContaBancariaClienteInput(agencia="1234-5", conta="98765-4", titular="Cliente Titular"), session)

    assert saved == {"id": saved["id"], "banco": "Santander", "agencia": "1234-5", "conta": "98765-4", "titular": "Cliente Titular", "conta_contabil": "1.1.02 - Banco"}
    assert client_bank_accounts(client.id, session) == [saved]
    delete_client_bank_account(client.id, "Santander", session)
    assert client_bank_accounts(client.id, session) == []


def test_delete_process_removes_its_reconciliations_and_files(tmp_path):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = Cliente(nome="Cliente")
    session.add(client); session.commit()
    process = create_reconciliation_process(ProcessoConciliacaoInput(cliente_id=client.id, data_inicio=date(2024, 1, 1), data_fim=date(2024, 1, 31), banco="Santander"), session)
    reconciliation_id = process["bancos"][0]["id"]
    file_path = tmp_path / "extrato.pdf"
    file_path.write_text("conteúdo")
    file = Arquivo(conciliacao_id=reconciliation_id, tipo_documento="extrato", banco_selecionado="Santander", nome_original="extrato.pdf", caminho=str(file_path))
    session.add(file); session.flush()
    movement = MovimentoExtrato(conciliacao_id=reconciliation_id, arquivo_id=file.id, pagina_numero=1, historico="PIX", natureza="saída")
    global_rule = RegraContabil(cliente_id=client.id, conciliacao_id=reconciliation_id, banco="Santander", tipo_fonte="extrato", tipo_operacao="saída", favorecido_normalizado=normalize_name("PIX"), conta_debito="Despesa", conta_credito="Banco", historico="Pagamento", escopo="global")
    local_rule = RegraContabil(cliente_id=client.id, conciliacao_id=reconciliation_id, banco="Santander", tipo_fonte="extrato", tipo_operacao="saída", favorecido_normalizado=normalize_name("TED"), conta_debito="Despesa", conta_credito="Banco", historico="Pagamento", escopo="periodo")
    session.add_all([movement, global_rule, local_rule]); session.flush()
    match = Correspondencia(conciliacao_id=reconciliation_id, movimento_extrato_id=movement.id, regra_contabil_id=local_rule.id)
    session.add(match); session.flush()
    session.add_all([
        LancamentoContabil(correspondencia_id=match.id, regra_contabil_id=local_rule.id, componente="PRINCIPAL", valor=Decimal("10.00"), status="aplicado_por_regra"),
        RegraContabilExcecao(regra_contabil_id=global_rule.id, conciliacao_id=reconciliation_id),
    ])
    session.commit()

    delete_reconciliation_process(process["id"], session)

    assert session.get(ProcessoConciliacao, process["id"]) is None
    assert session.query(Conciliacao).filter_by(processo_id=process["id"]).count() == 0
    assert not file_path.exists()
    assert session.get(RegraContabil, global_rule.id).ativo is True
    assert session.get(RegraContabil, global_rule.id).conciliacao_id is None
    assert session.get(RegraContabil, local_rule.id).ativo is False
    assert session.get(RegraContabil, local_rule.id).conciliacao_id is None
    assert session.query(RegraContabilExcecao).filter_by(conciliacao_id=reconciliation_id).count() == 0


def test_delete_notes_area_keeps_process_and_bank_reconciliations(tmp_path):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = Cliente(nome="Cliente")
    session.add(client); session.commit()
    process = create_reconciliation_process(ProcessoConciliacaoInput(cliente_id=client.id, data_inicio=date(2024, 1, 1), data_fim=date(2024, 1, 31), banco="Banco do Brasil"), session)
    bank_id = process["bancos"][0]["id"]
    notes = resume_process_bank(process["id"], ProcessoBancoInput(banco="Notas"), session)
    file_path = tmp_path / "notas.pdf"
    file_path.write_text("conteúdo")
    file = Arquivo(conciliacao_id=notes["id"], tipo_documento="nota", banco_selecionado="Notas", nome_original="notas.pdf", caminho=str(file_path))
    session.add(file); session.flush()
    session.add(NotaFiscal(conciliacao_id=notes["id"], arquivo_id=file.id, pagina_numero=1, fornecedor="Cliente", numero_nota="123", valor_total=Decimal("100.00")))
    rule = RegraContabil(cliente_id=client.id, conciliacao_id=notes["id"], banco="Notas", tipo_fonte="nota", tipo_operacao="Débito", favorecido_normalizado=normalize_name("Cliente"), conta_debito="Clientes", conta_credito="Receita", historico="Nota", escopo="periodo")
    session.add(rule); session.commit()

    delete_process_bank(process["id"], "Notas", session)

    assert session.get(ProcessoConciliacao, process["id"]) is not None
    assert session.get(Conciliacao, bank_id) is not None
    assert session.query(Conciliacao).filter_by(processo_id=process["id"], banco="Notas").count() == 0
    assert session.query(NotaFiscal).filter_by(conciliacao_id=notes["id"]).count() == 0
    assert session.get(RegraContabil, rule.id).ativo is False
    assert not file_path.exists()


def test_note_source_rule_can_use_payment_type_as_trigger():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = Cliente(nome="Cliente")
    session.add(client); session.commit()
    process = create_reconciliation_process(ProcessoConciliacaoInput(cliente_id=client.id, data_inicio=date(2024, 1, 1), data_fim=date(2024, 1, 31)), session)
    notes = resume_process_bank(process["id"], ProcessoBancoInput(banco="Notas"), session)
    file = Arquivo(conciliacao_id=notes["id"], tipo_documento="nota", banco_selecionado="Notas", nome_original="notas.pdf", caminho="/tmp/notas.pdf")
    session.add(file); session.flush()
    session.add(NotaFiscal(
        conciliacao_id=notes["id"],
        arquivo_id=file.id,
        pagina_numero=1,
        data_emissao=date(2024, 1, 3),
        fornecedor="ANDERSON DA SILVA CUNHA",
        numero_nota="1195",
        valor_total=Decimal("120.00"),
        dados_originais={"tipo_pagamento_label": "Cartão de crédito", "tipo_pagamento": "CARTAO_CREDITO", "data_pagamento": "2024-01-03", "gera_lancamento": True},
    ))
    session.commit()

    data = source_accounting_rules(notes["id"], "nota", session)
    assert data["pendentes"][0]["tipo_pagamento_label"] == "Cartão crédito"

    result = create_source_accounting_rule(notes["id"], "nota", RegraFonteInput(gatilho="cartao credito", conta_debito="Clientes diversos", conta_credito="Cartão", historico="Venda cartão", complemento="1195"), session)

    assert result["regras"]["resumo"] == {"total": 1, "classificados": 1, "pendentes": 0}
    assert result["regras"]["salvas"][0]["cobertos"] == 1


def test_reprocessing_statement_clears_previous_reconciliation_results(tmp_path):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = Cliente(nome="Cliente")
    session.add(client); session.commit()
    process = create_reconciliation_process(ProcessoConciliacaoInput(cliente_id=client.id, data_inicio=date(2024, 1, 1), data_fim=date(2024, 1, 31), banco="Banco do Brasil"), session)
    reconciliation_id = process["bancos"][0]["id"]
    file_path = tmp_path / "extrato.pdf"
    file_path.write_text("conteúdo")
    text = "02/01/2024\n0000\n13105 144 Pix - Enviado\n10.202\n520,52 C\n02/01 09:40 Lia Da Silva Alexandre"
    file = Arquivo(conciliacao_id=reconciliation_id, tipo_documento="extrato", banco_selecionado="Banco do Brasil", nome_original="extrato.pdf", caminho=str(file_path), texto_bruto=text)
    session.add(file); session.flush()
    movement = MovimentoExtrato(conciliacao_id=reconciliation_id, arquivo_id=file.id, pagina_numero=1, historico="PIX", natureza="entrada")
    session.add(movement); session.flush()
    match = Correspondencia(conciliacao_id=reconciliation_id, movimento_extrato_id=movement.id)
    session.add(match); session.flush()
    session.add(LancamentoContabil(correspondencia_id=match.id, valor=1))
    session.commit()

    reprocess_document(file.id, session)

    assert session.query(Correspondencia).filter_by(conciliacao_id=reconciliation_id).count() == 0
    assert session.query(LancamentoContabil).count() == 0
    assert session.query(MovimentoExtrato).filter_by(arquivo_id=file.id, natureza="Crédito").count() == 1


def test_boleto_matches_paid_value_once_and_creates_component_items():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = Cliente(nome="Cliente")
    session.add(client); session.flush()
    reconciliation = Conciliacao(cliente_id=client.id, banco="Banco do Brasil", data_inicio=date(2024, 1, 1), data_fim=date(2024, 1, 31))
    session.add(reconciliation); session.flush()
    statement_file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="extrato", banco_selecionado="Banco do Brasil", nome_original="extrato.pdf", caminho="/tmp/extrato.pdf")
    receipt_file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="comprovante", banco_selecionado="Banco do Brasil", nome_original="boleto.pdf", caminho="/tmp/boleto.pdf")
    session.add_all([statement_file, receipt_file]); session.flush()
    movement = MovimentoExtrato(conciliacao_id=reconciliation.id, arquivo_id=statement_file.id, pagina_numero=7, data=date(2024, 1, 31), historico="Pagamento de Boleto CONSELHO FEDERAL DE ODONTOLOGIA", valor=Decimal("493.14"), natureza="saída")
    receipt = Comprovante(conciliacao_id=reconciliation.id, arquivo_id=receipt_file.id, pagina_numero=32, data=date(2024, 1, 31), favorecido="CONSELHO FEDERAL DE ODONTOLOGI", valor=Decimal("493.14"), valor_original=Decimal("547.93"), valor_desconto_abatimento=Decimal("54.79"), valor_pago=Decimal("493.14"))
    session.add_all([movement, receipt]); session.commit()

    reconcile(reconciliation.id, session)

    match = session.query(Correspondencia).filter_by(movimento_extrato_id=movement.id).one()
    items = session.query(LancamentoContabil).filter_by(correspondencia_id=match.id).order_by(LancamentoContabil.ordem).all()
    assert match.comprovante_id == receipt.id
    assert [(item.componente, item.valor, item.efeito_no_total) for item in items] == [("VALOR_COBRADO", Decimal("493.14"), "SOMA"), ("DESCONTO_ABATIMENTO", Decimal("54.79"), "OUTROS")]
    row = result(reconciliation.id, session)[0]
    assert (row["total_lancamentos"], row["diferenca"]) == ("R$ 493,14", "R$ 0,00")


def test_caixa_generic_boleto_matches_receipt_by_partial_document_number():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = Cliente(nome="Cliente")
    session.add(client); session.flush()
    reconciliation = Conciliacao(cliente_id=client.id, banco="Caixa", data_inicio=date(2024, 1, 1), data_fim=date(2024, 1, 31))
    session.add(reconciliation); session.flush()
    statement_file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="extrato", banco_selecionado="Caixa", nome_original="extrato.pdf", caminho="/tmp/extrato.pdf")
    receipt_file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="comprovante", banco_selecionado="Caixa", nome_original="boleto.pdf", caminho="/tmp/boleto.pdf")
    session.add_all([statement_file, receipt_file]); session.flush()
    movement = MovimentoExtrato(conciliacao_id=reconciliation.id, arquivo_id=statement_file.id, pagina_numero=2, data=date(2024, 1, 25), historico="PAG BOLETO", valor=Decimal("1710.87"), natureza="Débito", dados_originais={"numero_documento": "084072"})
    receipt = Comprovante(conciliacao_id=reconciliation.id, arquivo_id=receipt_file.id, pagina_numero=1, data=date(2024, 1, 25), hora="10:35:36", favorecido="MAPEMI BRASIL MATERIAIS MEDICOS E ODONTO", beneficiario="MAPEMI BRASIL MATERIAIS MEDICOS E ODONTO", numero_documento="025084072", valor=Decimal("1710.87"), valor_original=Decimal("1710.87"), valor_pago=Decimal("1710.87"), tipo_operacao="BOLETO")
    session.add_all([movement, receipt]); session.commit()

    reconcile(reconciliation.id, session)

    match = session.query(Correspondencia).filter_by(movimento_extrato_id=movement.id).one()
    assert match.comprovante_id == receipt.id
    assert match.criterio_correspondencia == "Correspondência pelo código Caixa sem prefixo do dia"
    assert unused_documents(reconciliation.id, session)["comprovantes"] == []


def test_bradesco_boleto_matches_receipt_by_document_number_with_leading_zeroes():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = Cliente(nome="Cliente")
    session.add(client); session.flush()
    reconciliation = Conciliacao(cliente_id=client.id, banco="Bradesco", data_inicio=date(2024, 1, 1), data_fim=date(2024, 1, 31))
    session.add(reconciliation); session.flush()
    statement_file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="extrato", banco_selecionado="Bradesco", nome_original="extrato.pdf", caminho="/tmp/extrato.pdf")
    receipt_file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="comprovante", banco_selecionado="Bradesco", nome_original="boleto.pdf", caminho="/tmp/boleto.pdf")
    session.add_all([statement_file, receipt_file]); session.flush()
    movement = MovimentoExtrato(conciliacao_id=reconciliation.id, arquivo_id=statement_file.id, pagina_numero=1, data=date(2024, 1, 11), historico="PAGTO ELETRON COBRANCA PGTO BOLETO STA CRUZ", valor=Decimal("105.17"), natureza="Débito", dados_originais={"numero_documento": "4519"})
    receipt = Comprovante(conciliacao_id=reconciliation.id, arquivo_id=receipt_file.id, pagina_numero=1, data=date(2024, 1, 11), favorecido="DISTR DE MEDI SANTA CRUZ LTDA", beneficiario="DISTR DE MEDI SANTA CRUZ LTDA", numero_documento="0004519", valor=Decimal("105.17"), valor_original=Decimal("104.65"), valor_pago=Decimal("105.17"), tipo_operacao="BOLETO")
    session.add_all([movement, receipt]); session.commit()

    reconcile(reconciliation.id, session)

    match = session.query(Correspondencia).filter_by(movimento_extrato_id=movement.id).one()
    assert match.comprovante_id == receipt.id
    assert match.criterio_correspondencia == "Correspondência pelo número do documento"
    assert unused_documents(reconciliation.id, session)["comprovantes"] == []


def test_generic_boleto_fallback_does_not_guess_ambiguous_same_day_value_receipts():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = Cliente(nome="Cliente")
    session.add(client); session.flush()
    reconciliation = Conciliacao(cliente_id=client.id, banco="Caixa", data_inicio=date(2024, 1, 1), data_fim=date(2024, 1, 31))
    session.add(reconciliation); session.flush()
    statement_file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="extrato", banco_selecionado="Caixa", nome_original="extrato.pdf", caminho="/tmp/extrato.pdf")
    receipt_file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="comprovante", banco_selecionado="Caixa", nome_original="boleto.pdf", caminho="/tmp/boleto.pdf")
    session.add_all([statement_file, receipt_file]); session.flush()
    movement = MovimentoExtrato(conciliacao_id=reconciliation.id, arquivo_id=statement_file.id, pagina_numero=2, data=date(2024, 1, 25), historico="PAG BOLETO", valor=Decimal("1710.87"), natureza="Débito")
    receipts = [
        Comprovante(conciliacao_id=reconciliation.id, arquivo_id=receipt_file.id, pagina_numero=1, data=date(2024, 1, 25), favorecido="Fornecedor A", valor=Decimal("1710.87"), valor_pago=Decimal("1710.87"), tipo_operacao="BOLETO"),
        Comprovante(conciliacao_id=reconciliation.id, arquivo_id=receipt_file.id, pagina_numero=2, data=date(2024, 1, 25), favorecido="Fornecedor B", valor=Decimal("1710.87"), valor_pago=Decimal("1710.87"), tipo_operacao="BOLETO"),
    ]
    session.add(movement); session.add_all(receipts); session.commit()

    reconcile(reconciliation.id, session)

    match = session.query(Correspondencia).filter_by(movimento_extrato_id=movement.id).one()
    assert match.comprovante_id is None
    assert len(unused_documents(reconciliation.id, session)["comprovantes"]) == 2


def test_accounting_rules_do_not_show_stale_principal_duplicate_for_discounted_boleto():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = Cliente(nome="Cliente")
    session.add(client); session.flush()
    reconciliation = Conciliacao(cliente_id=client.id, banco="Banco do Brasil", data_inicio=date(2024, 1, 1), data_fim=date(2024, 1, 31))
    session.add(reconciliation); session.flush()
    statement_file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="extrato", banco_selecionado="Banco do Brasil", nome_original="extrato.pdf", caminho="/tmp/extrato.pdf")
    receipt_file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="comprovante", banco_selecionado="Banco do Brasil", nome_original="boleto.pdf", caminho="/tmp/boleto.pdf")
    session.add_all([statement_file, receipt_file]); session.flush()
    movement = MovimentoExtrato(conciliacao_id=reconciliation.id, arquivo_id=statement_file.id, pagina_numero=7, data=date(2024, 1, 31), historico="Pagamento de Boleto CONSELHO FEDERAL DE ODONTOLOGIA", valor=Decimal("493.14"), natureza="saída")
    receipt = Comprovante(conciliacao_id=reconciliation.id, arquivo_id=receipt_file.id, pagina_numero=32, data=date(2024, 1, 31), favorecido="CONSELHO FEDERAL DE ODONTOLOGI", valor=Decimal("493.14"), valor_original=Decimal("547.93"), valor_desconto_abatimento=Decimal("54.79"), valor_pago=Decimal("493.14"))
    session.add_all([movement, receipt]); session.commit()
    reconcile(reconciliation.id, session)
    match = session.query(Correspondencia).filter_by(movimento_extrato_id=movement.id).one()
    session.add(LancamentoContabil(correspondencia_id=match.id, componente="PRINCIPAL", categoria="PRINCIPAL", valor=Decimal("493.14"), origem="extrato", ordem=1, status="pendente_regra"))
    session.commit()

    rule = RegraContabil(cliente_id=client.id, conciliacao_id=reconciliation.id, banco=reconciliation.banco, tipo_fonte="extrato", tipo_operacao="Crédito", tipo_componente="VALOR_COBRADO", favorecido_normalizado=normalize_name("CONSELHO FEDERAL"), conta_debito="Despesa", conta_credito="Banco", historico="Pagamento")
    session.add(rule); session.commit()

    apply_accounting_rules(reconciliation, session)
    data = accounting_rules(reconciliation.id, session)
    stored_components = [item.componente for item in session.query(LancamentoContabil).filter_by(correspondencia_id=match.id).order_by(LancamentoContabil.ordem, LancamentoContabil.id)]

    assert [(item["tipo_componente"], Decimal(item["valor"])) for item in data["pendentes"]] == [("DESCONTO_ABATIMENTO", Decimal("54.79"))]
    assert data["pendentes"][0]["componentes_documento"] == ["VALOR_COBRADO", "DESCONTO_ABATIMENTO"]
    assert data["pendentes"][0]["componentes_cobertos"] == [{"componente": "VALOR_COBRADO", "valor": "493.14"}]
    assert stored_components == ["VALOR_COBRADO", "DESCONTO_ABATIMENTO"]
    row = result(reconciliation.id, session)[0]
    assert (row["total_lancamentos"], row["diferenca"]) == ("R$ 493,14", "R$ 0,00")


def test_result_shows_final_beneficiary_for_bambuno_receipt():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = Cliente(nome="Cliente")
    session.add(client); session.flush()
    reconciliation = Conciliacao(cliente_id=client.id, banco="Banco do Brasil", data_inicio=date(2024, 1, 1), data_fim=date(2024, 1, 31))
    session.add(reconciliation); session.flush()
    statement_file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="extrato", banco_selecionado="Banco do Brasil", nome_original="extrato.pdf", caminho="/tmp/extrato.pdf")
    receipt_file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="comprovante", banco_selecionado="Banco do Brasil", nome_original="boleto.pdf", caminho="/tmp/boleto.pdf")
    session.add_all([statement_file, receipt_file]); session.flush()
    movement = MovimentoExtrato(conciliacao_id=reconciliation.id, arquivo_id=statement_file.id, pagina_numero=1, data=date(2024, 1, 30), historico="Pagamento de Boleto", nome_encontrado="BAMBUNO TECNOLOGIA LTDA", valor=Decimal("497.00"), natureza="saída")
    receipt = Comprovante(conciliacao_id=reconciliation.id, arquivo_id=receipt_file.id, pagina_numero=1, data=date(2024, 1, 30), favorecido="BAMBUNO TECNOLOGIA LTDA", beneficiario="BAMBUNO TECNOLOGIA LTDA", beneficiario_final="SUCESSODONTO CURSOS E TREINAMENTOS", nome_fantasia="BAMBUNO TECNOLOGIA - EIRELI", valor_pago=Decimal("497.00"))
    session.add_all([movement, receipt]); session.commit()

    reconcile(reconciliation.id, session)
    row = result(reconciliation.id, session)[0]

    assert "Beneficiário: BAMBUNO TECNOLOGIA LTDA" in row["comprovante_bancario"]
    assert "Beneficiário final: SUCESSODONTO CURSOS E TREINAMENTOS" in row["comprovante_bancario"]


def test_reconciliation_refresh_preserves_manual_component_edits():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = Cliente(nome="Cliente")
    session.add(client); session.flush()
    reconciliation = Conciliacao(cliente_id=client.id, banco="Banco do Brasil", data_inicio=date(2024, 1, 1), data_fim=date(2024, 1, 31))
    session.add(reconciliation); session.flush()
    statement_file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="extrato", banco_selecionado="Banco do Brasil", nome_original="extrato.pdf", caminho="/tmp/extrato.pdf")
    receipt_file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="comprovante", banco_selecionado="Banco do Brasil", nome_original="boleto.pdf", caminho="/tmp/boleto.pdf")
    session.add_all([statement_file, receipt_file]); session.flush()
    movement = MovimentoExtrato(conciliacao_id=reconciliation.id, arquivo_id=statement_file.id, pagina_numero=1, data=date(2024, 1, 31), historico="Pagamento de Boleto Conselho Federal", valor=Decimal("100.00"), natureza="saída")
    receipt = Comprovante(conciliacao_id=reconciliation.id, arquivo_id=receipt_file.id, pagina_numero=1, data=date(2024, 1, 31), favorecido="Conselho Federal", valor_original=Decimal("110.00"), valor_desconto=Decimal("10.00"), valor_pago=Decimal("100.00"))
    session.add_all([movement, receipt]); session.commit()

    reconcile(reconciliation.id, session)
    match = session.query(Correspondencia).filter_by(movimento_extrato_id=movement.id).one()
    item = session.query(LancamentoContabil).filter_by(correspondencia_id=match.id, componente="VALOR_COBRADO").one()
    item.conta_debito = "Despesa"; item.status = "editado_manual"
    session.commit()
    reconcile(reconciliation.id, session)

    items = session.query(LancamentoContabil).filter_by(correspondencia_id=match.id).all()
    assert len(items) == 2
    assert next(entry for entry in items if entry.componente == "VALOR_COBRADO").conta_debito == "Despesa"


def test_duplicate_value_and_date_pairs_each_statement_to_one_receipt():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = Cliente(nome="Cliente")
    session.add(client); session.flush()
    reconciliation = Conciliacao(cliente_id=client.id, banco="Banco do Brasil", data_inicio=date(2024, 1, 1), data_fim=date(2024, 1, 31))
    session.add(reconciliation); session.flush()
    statement_file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="extrato", banco_selecionado="Banco do Brasil", nome_original="extrato.pdf", caminho="/tmp/extrato.pdf")
    receipt_file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="comprovante", banco_selecionado="Banco do Brasil", nome_original="boleto.pdf", caminho="/tmp/boleto.pdf")
    session.add_all([statement_file, receipt_file]); session.flush()
    for page in (7, 8):
        session.add(MovimentoExtrato(conciliacao_id=reconciliation.id, arquivo_id=statement_file.id, pagina_numero=page, data=date(2024, 1, 31), historico="Pagamento de Boleto CONSELHO FEDERAL DE ODONTOLOGIA", valor=Decimal("493.14"), natureza="saída"))
    for page in (32, 33):
        session.add(Comprovante(conciliacao_id=reconciliation.id, arquivo_id=receipt_file.id, pagina_numero=page, data=date(2024, 1, 31), favorecido="CONSELHO FEDERAL DE ODONTOLOGI", valor=Decimal("493.14"), valor_original=Decimal("547.93"), valor_desconto_abatimento=Decimal("54.79"), valor_pago=Decimal("493.14")))
    session.commit()

    reconcile(reconciliation.id, session)
    reconcile(reconciliation.id, session)

    matches = session.query(Correspondencia).filter_by(conciliacao_id=reconciliation.id).all()
    assert len(matches) == 2
    assert len({item.movimento_extrato_id for item in matches}) == len({item.comprovante_id for item in matches}) == 2
    assert session.query(LancamentoContabil).count() == 4


def test_bambuno_receipt_matches_beneficiary_not_final_beneficiary():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = Cliente(nome="Cliente")
    session.add(client); session.flush()
    reconciliation = Conciliacao(cliente_id=client.id, banco="Banco do Brasil", data_inicio=date(2024, 1, 1), data_fim=date(2024, 1, 31))
    session.add(reconciliation); session.flush()
    file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="extrato", banco_selecionado="Banco do Brasil", nome_original="extrato.pdf", caminho="/tmp/extrato.pdf")
    receipt_file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="comprovante", banco_selecionado="Banco do Brasil", nome_original="boleto.pdf", caminho="/tmp/boleto.pdf")
    session.add_all([file, receipt_file]); session.flush()
    movement = MovimentoExtrato(conciliacao_id=reconciliation.id, arquivo_id=file.id, pagina_numero=7, data=date(2024, 1, 30), historico="Pagamento de Boleto BAMBUNO TECNOLOGIA LTDA", valor=Decimal("1000.00"), natureza="saída")
    receipt = Comprovante(conciliacao_id=reconciliation.id, arquivo_id=receipt_file.id, pagina_numero=32, data=date(2024, 1, 30), favorecido="BAMBUNO TECNOLOGIA LTDA", beneficiario="BAMBUNO TECNOLOGIA LTDA", nome_fantasia="BAMBUNO TECNOLOGIA EIRELI", beneficiario_final="SUCESSODONTO CURSOS E TREINAMENTOS", valor=Decimal("1000.00"), valor_original=Decimal("1000.00"), valor_pago=Decimal("1000.00"))
    session.add_all([movement, receipt]); session.commit()

    reconcile(reconciliation.id, session)

    match = session.query(Correspondencia).filter_by(movimento_extrato_id=movement.id).one()
    assert match.comprovante_id == receipt.id
    assert match.criterio_correspondencia == "Correspondência pelo beneficiário"
    assert accounting_rules(reconciliation.id, session)["pendentes"][0]["historico"] == "Pagamento de Boleto SUCESSODONTO CURSOS E TREINAMENTOS"


def test_transfer_without_counterparty_matches_unique_receipt_by_date_value_and_type():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = Cliente(nome="Cliente")
    session.add(client); session.flush()
    reconciliation = Conciliacao(cliente_id=client.id, banco="Banco do Brasil", data_inicio=date(2024, 1, 1), data_fim=date(2024, 1, 31))
    session.add(reconciliation); session.flush()
    file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="extrato", banco_selecionado="Banco do Brasil", nome_original="extrato.pdf", caminho="/tmp/extrato.pdf")
    receipt_file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="comprovante", banco_selecionado="Banco do Brasil", nome_original="transferencia.pdf", caminho="/tmp/transferencia.pdf")
    session.add_all([file, receipt_file]); session.flush()
    movement = MovimentoExtrato(conciliacao_id=reconciliation.id, arquivo_id=file.id, pagina_numero=1, data=date(2024, 1, 17), data_origem="15/01", historico="Transferência Agendada", nome_encontrado="", valor=Decimal("1302.00"), natureza="saída")
    receipt = Comprovante(conciliacao_id=reconciliation.id, arquivo_id=receipt_file.id, pagina_numero=1, data=date(2024, 1, 17), favorecido="MARIA LUZIRDA C MIRANDA", valor=Decimal("1302.00"), valor_pago=Decimal("1302.00"), tipo_operacao="TRANSFERÊNCIA")
    session.add_all([movement, receipt]); session.commit()

    reconcile(reconciliation.id, session)

    match = session.query(Correspondencia).filter_by(movimento_extrato_id=movement.id).one()
    assert match.comprovante_id == receipt.id
    assert match.criterio_correspondencia == "Correspondência pelo data, valor e tipo transferência"


def test_pix_agendamento_caixa_matches_cef_receipt_without_operation_type():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = Cliente(nome="Cliente")
    session.add(client); session.flush()
    reconciliation = Conciliacao(cliente_id=client.id, banco="Banco do Brasil", data_inicio=date(2024, 4, 1), data_fim=date(2024, 4, 30))
    session.add(reconciliation); session.flush()
    file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="extrato", banco_selecionado="Banco do Brasil", nome_original="extrato.pdf", caminho="/tmp/extrato.pdf")
    receipt_file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="comprovante", banco_selecionado="Banco do Brasil", nome_original="pix.pdf", caminho="/tmp/pix.pdf")
    session.add_all([file, receipt_file]); session.flush()
    movement = MovimentoExtrato(conciliacao_id=reconciliation.id, arquivo_id=file.id, pagina_numero=1, data=date(2024, 4, 4), hora="07:00", historico="13105 144 Pix - Agendamento Caixa Economica Federal", valor=Decimal("89.57"), natureza="saída")
    receipt = Comprovante(conciliacao_id=reconciliation.id, arquivo_id=receipt_file.id, pagina_numero=1, data=date(2024, 4, 4), hora="07:05:26", favorecido="Cef Matriz", valor=Decimal("89.57"), valor_pago=Decimal("89.57"), tipo_operacao="")
    session.add_all([movement, receipt]); session.commit()

    reconcile(reconciliation.id, session)

    match = session.query(Correspondencia).filter_by(movimento_extrato_id=movement.id).one()
    assert match.comprovante_id == receipt.id
    assert match.criterio_correspondencia == "Correspondência pelo beneficiário"
    assert unused_documents(reconciliation.id, session)["comprovantes"] == []


def test_pix_agendamento_matches_abbreviated_person_name():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = Cliente(nome="Cliente")
    session.add(client); session.flush()
    reconciliation = Conciliacao(cliente_id=client.id, banco="Banco do Brasil", data_inicio=date(2024, 4, 1), data_fim=date(2024, 4, 30))
    session.add(reconciliation); session.flush()
    file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="extrato", banco_selecionado="Banco do Brasil", nome_original="extrato.pdf", caminho="/tmp/extrato.pdf")
    receipt_file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="comprovante", banco_selecionado="Banco do Brasil", nome_original="pix.pdf", caminho="/tmp/pix.pdf")
    session.add_all([file, receipt_file]); session.flush()
    movement = MovimentoExtrato(conciliacao_id=reconciliation.id, arquivo_id=file.id, pagina_numero=1, data=date(2024, 4, 5), hora="07:00", historico="13105 144 Pix - Agendamento Adrielle Colares Frazao De", valor=Decimal("100.00"), natureza="saída")
    receipt = Comprovante(conciliacao_id=reconciliation.id, arquivo_id=receipt_file.id, pagina_numero=1, data=date(2024, 4, 5), hora="07:05:27", favorecido="Adrielle C F Queiroz", valor=Decimal("100.00"), valor_pago=Decimal("100.00"), tipo_operacao="PIX")
    session.add_all([movement, receipt]); session.commit()

    reconcile(reconciliation.id, session)

    match = session.query(Correspondencia).filter_by(movimento_extrato_id=movement.id).one()
    assert match.comprovante_id == receipt.id
    assert match.criterio_correspondencia == "Correspondência pelo beneficiário"
    assert unused_documents(reconciliation.id, session)["comprovantes"] == []


def test_pix_agendamento_caixa_matches_receipt_with_small_statement_time_difference():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = Cliente(nome="Cliente")
    session.add(client); session.flush()
    reconciliation = Conciliacao(cliente_id=client.id, banco="Banco do Brasil", data_inicio=date(2024, 4, 1), data_fim=date(2024, 4, 30))
    session.add(reconciliation); session.flush()
    file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="extrato", banco_selecionado="Banco do Brasil", nome_original="extrato.pdf", caminho="/tmp/extrato.pdf")
    receipt_file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="comprovante", banco_selecionado="Banco do Brasil", nome_original="pix.pdf", caminho="/tmp/pix.pdf")
    session.add_all([file, receipt_file]); session.flush()
    movement = MovimentoExtrato(conciliacao_id=reconciliation.id, arquivo_id=file.id, pagina_numero=5, data=date(2024, 4, 19), hora="05:32", historico="13105 144 Pix - Agendamento Caixa Economica Federal", valor=Decimal("408.80"), natureza="saída")
    receipt = Comprovante(conciliacao_id=reconciliation.id, arquivo_id=receipt_file.id, pagina_numero=5, data=date(2024, 4, 19), hora="05:33:26", favorecido="Cef Matriz", valor=Decimal("408.80"), valor_pago=Decimal("408.80"), tipo_operacao="PIX")
    session.add_all([movement, receipt]); session.commit()

    reconcile(reconciliation.id, session)

    match = session.query(Correspondencia).filter_by(movimento_extrato_id=movement.id).one()
    assert match.comprovante_id == receipt.id
    assert match.criterio_correspondencia == "Correspondência pelo beneficiário"
    assert unused_documents(reconciliation.id, session)["comprovantes"] == []


def test_ted_caixa_matches_cef_receipt_with_document_number():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = Cliente(nome="Cliente")
    session.add(client); session.flush()
    reconciliation = Conciliacao(cliente_id=client.id, banco="Banco do Brasil", data_inicio=date(2024, 4, 1), data_fim=date(2024, 4, 30))
    session.add(reconciliation); session.flush()
    file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="extrato", banco_selecionado="Banco do Brasil", nome_original="extrato.pdf", caminho="/tmp/extrato.pdf")
    receipt_file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="comprovante", banco_selecionado="Banco do Brasil", nome_original="ted.pdf", caminho="/tmp/ted.pdf")
    session.add_all([file, receipt_file]); session.flush()
    movement = MovimentoExtrato(conciliacao_id=reconciliation.id, arquivo_id=file.id, pagina_numero=1, data=date(2024, 4, 19), historico="13105 438 TED Caixa Economica Federal", valor=Decimal("8000.00"), natureza="saída")
    receipt = Comprovante(conciliacao_id=reconciliation.id, arquivo_id=receipt_file.id, pagina_numero=5, data=date(2024, 4, 19), hora="05:33:26", favorecido="610.577.000.025.632", beneficiario="Cef Matriz", numero_documento="610.577.000.025.632", valor=Decimal("8000.00"), valor_pago=Decimal("8000.00"), tipo_operacao="TED")
    session.add_all([movement, receipt]); session.commit()

    reconcile(reconciliation.id, session)

    match = session.query(Correspondencia).filter_by(movimento_extrato_id=movement.id).one()
    assert match.comprovante_id == receipt.id
    assert match.criterio_correspondencia == "Correspondência pelo beneficiário"
    assert unused_documents(reconciliation.id, session)["comprovantes"] == []


def test_ted_matches_abbreviated_and_truncated_counterparty_name():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = Cliente(nome="Cliente")
    session.add(client); session.flush()
    reconciliation = Conciliacao(cliente_id=client.id, banco="Banco do Brasil", data_inicio=date(2024, 1, 1), data_fim=date(2024, 1, 31))
    session.add(reconciliation); session.flush()
    file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="extrato", banco_selecionado="Banco do Brasil", nome_original="extrato.pdf", caminho="/tmp/extrato.pdf")
    receipt_file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="comprovante", banco_selecionado="Banco do Brasil", nome_original="ted.pdf", caminho="/tmp/ted.pdf")
    session.add_all([file, receipt_file]); session.flush()
    movement = MovimentoExtrato(conciliacao_id=reconciliation.id, arquivo_id=file.id, pagina_numero=1, data=date(2024, 1, 2), historico="Transferência", nome_encontrado="13105 438 TED 033 2478 008695575000188 CENTRO ODONTO", valor=Decimal("2300.00"), natureza="saída")
    receipt = Comprovante(conciliacao_id=reconciliation.id, arquivo_id=receipt_file.id, pagina_numero=1, data=date(2024, 1, 2), favorecido="C ODONTO FIGUEIRO", beneficiario="C ODONTO FIGUEIRO", valor=Decimal("2300.00"), valor_pago=Decimal("2300.00"), tipo_operacao="TED")
    session.add_all([movement, receipt]); session.commit()

    reconcile(reconciliation.id, session)

    match = session.query(Correspondencia).filter_by(movimento_extrato_id=movement.id).one()
    assert match.comprovante_id == receipt.id
    assert match.criterio_correspondencia == "Correspondência pelo beneficiário"


def test_loan_document_matches_statement_by_contract_and_creates_components():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = Cliente(nome="Cliente")
    session.add(client); session.flush()
    reconciliation = Conciliacao(cliente_id=client.id, banco="Banco do Brasil", data_inicio=date(2024, 1, 1), data_fim=date(2024, 1, 31))
    session.add(reconciliation); session.flush()
    statement_file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="extrato", banco_selecionado="Banco do Brasil", nome_original="extrato.pdf", caminho="/tmp/extrato.pdf")
    loan_file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="emprestimo", banco_selecionado="Banco do Brasil", nome_original="emprestimo.pdf", caminho="/tmp/emprestimo.pdf")
    session.add_all([statement_file, loan_file]); session.flush()
    movement = MovimentoExtrato(conciliacao_id=reconciliation.id, arquivo_id=statement_file.id, pagina_numero=1, data=date(2024, 1, 15), historico="13128 500 Cap Giro Dig Amortização 57.709.569.000.109", valor=Decimal("2817.00"), natureza="saída")
    loan = Comprovante(conciliacao_id=reconciliation.id, arquivo_id=loan_file.id, pagina_numero=1, data=date(2024, 1, 15), favorecido="Empréstimo/Financiamento 057.709.569", beneficiario="Empréstimo/Financiamento 057.709.569", numero_documento="057.709.569", valor=Decimal("2817.00"), valor_original=Decimal("2083.33"), valor_juros=Decimal("733.67"), valor_pago=Decimal("2817.00"), tipo_operacao="EMPRÉSTIMO/FINANCIAMENTO")
    session.add_all([movement, loan]); session.commit()

    reconcile(reconciliation.id, session)

    match = session.query(Correspondencia).filter_by(movimento_extrato_id=movement.id).one()
    assert match.comprovante_id == loan.id
    assert match.criterio_correspondencia == "Correspondência pelo número do documento"
    entries = session.query(LancamentoContabil).filter_by(correspondencia_id=match.id).order_by(LancamentoContabil.ordem).all()
    assert [(entry.componente, entry.valor, entry.origem) for entry in entries] == [
        ("PRINCIPAL", Decimal("2083.33"), "emprestimo"),
        ("JUROS", Decimal("733.67"), "emprestimo"),
    ]
    unused = unused_documents(reconciliation.id, session)
    assert unused["emprestimos"] == []
    rows = result(reconciliation.id, session)
    assert rows[0]["comprovante_tipo"] == "emprestimo"
    rules = accounting_rules(reconciliation.id, session)
    loan_pending = [item for item in rules["pendentes"] if item["comprovante_tipo"] == "emprestimo"]
    assert {item["tipo_componente"] for item in loan_pending} == {"PRINCIPAL", "JUROS"}
    assert all("Comprovante de empréstimo/financiamento" in item["composicao_simples"] for item in loan_pending)


def test_loan_document_matches_statement_by_loan_operation_when_contract_is_missing():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = Cliente(nome="Cliente")
    session.add(client); session.flush()
    reconciliation = Conciliacao(cliente_id=client.id, banco="Banco do Brasil", data_inicio=date(2024, 1, 1), data_fim=date(2024, 1, 31))
    session.add(reconciliation); session.flush()
    statement_file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="extrato", banco_selecionado="Banco do Brasil", nome_original="extrato.pdf", caminho="/tmp/extrato.pdf")
    loan_file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="emprestimo", banco_selecionado="Banco do Brasil", nome_original="emprestimo.xlsx", caminho="/tmp/emprestimo.xlsx")
    session.add_all([statement_file, loan_file]); session.flush()
    movement = MovimentoExtrato(conciliacao_id=reconciliation.id, arquivo_id=statement_file.id, pagina_numero=1, data=date(2024, 1, 15), historico="13128 500 Cap Giro Dig Amortização", valor=Decimal("2817.00"), natureza="Débito")
    loan = Comprovante(conciliacao_id=reconciliation.id, arquivo_id=loan_file.id, pagina_numero=1, data=date(2024, 1, 15), favorecido="Empréstimo/Financiamento 057.709.569", beneficiario="Empréstimo/Financiamento 057.709.569", numero_documento="057.709.569", valor=Decimal("2817.00"), valor_original=Decimal("2083.33"), valor_juros=Decimal("733.67"), valor_pago=Decimal("2817.00"), tipo_operacao="EMPRESTIMO")
    session.add_all([movement, loan]); session.commit()

    reconcile(reconciliation.id, session)

    match = session.query(Correspondencia).filter_by(movimento_extrato_id=movement.id).one()
    assert match.comprovante_id == loan.id
    assert match.criterio_correspondencia == "Correspondência pelo lançamento de empréstimo"
    rows = result(reconciliation.id, session)
    assert rows[0]["natureza"] == "Débito"
    assert rows[0]["natureza_contabil"] == "Crédito"
    rules = accounting_rules(reconciliation.id, session)
    loan_pending = [item for item in rules["pendentes"] if item["comprovante_tipo"] == "emprestimo"]
    assert {item["tipo_componente"] for item in loan_pending} == {"PRINCIPAL", "JUROS"}


def test_invoice_rules_are_independent_and_export_own_csv():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = Cliente(nome="Cliente")
    session.add(client); session.flush()
    reconciliation = Conciliacao(cliente_id=client.id, banco="Notas", data_inicio=date(2024, 1, 1), data_fim=date(2024, 1, 31))
    session.add(reconciliation); session.flush()
    file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="nota", banco_selecionado="Notas", nome_original="nota.pdf", caminho="/tmp/nota.pdf")
    session.add(file); session.flush()
    invoice = NotaFiscal(conciliacao_id=reconciliation.id, arquivo_id=file.id, pagina_numero=1, data_emissao=date(2024, 1, 10), fornecedor="CLINICA EXEMPLO LTDA", cpf_cnpj="12.345.678/0001-90", numero_nota="12345", valor_total=Decimal("1250.75"), dados_originais=routes.enrich_invoice_data({"forma_pagamento": "Dinheiro", "data_pagamento": "2024-01-10"}, date(2024, 1, 10), Decimal("1250.75")))
    session.add(invoice); session.commit()

    initial = source_accounting_rules(reconciliation.id, "nota", session)
    assert initial["resumo"] == {"total": 1, "classificados": 0, "pendentes": 1}

    created = create_source_accounting_rule(reconciliation.id, "nota", RegraFonteInput(gatilho="clinica exemplo", conta_debito="401 - Serviços", conta_credito="221 - Fornecedores", historico="Serviços tomados", complemento="Conforme nota fiscal"), session)

    assert created["regras"]["resumo"] == {"total": 1, "classificados": 1, "pendentes": 0}
    csv = source_accounting_csv(reconciliation.id, "nota", session).body.decode("utf-8-sig")
    assert "401;221;Serviços tomados;1250.75;Conforme nota fiscal;DINHEIRO;CAIXA" in csv


@pytest.mark.parametrize(
    ("emission", "due", "payment", "expected"),
    [
        (date(2024, 1, 10), date(2024, 1, 10), date(2024, 1, 10), "NORMAL"),
        (date(2024, 1, 10), date(2024, 1, 10), date(2024, 1, 8), "ANTECIPACAO_EMISSAO_E_VENCIMENTO"),
        (date(2024, 1, 10), date(2024, 1, 10), date(2024, 1, 12), "NORMAL"),
        (date(2024, 1, 31), None, date(2024, 1, 30), "ANTECIPACAO_EMISSAO"),
        (date(2024, 2, 1), None, date(2024, 1, 31), "ANTECIPACAO_EMISSAO"),
        (date(2027, 1, 2), None, date(2026, 12, 31), "ANTECIPACAO_EMISSAO"),
        (date(2024, 2, 1), date(2024, 2, 5), date(2024, 1, 31), "ANTECIPACAO_EMISSAO_E_VENCIMENTO"),
        (None, date(2024, 1, 5), date(2024, 1, 3), "ANTECIPACAO_VENCIMENTO"),
        (date(2024, 1, 1), date(2024, 1, 10), date(2024, 1, 5), "ANTECIPACAO_VENCIMENTO"),
        (date(2024, 1, 5), date(2024, 1, 10), None, "REVISAR"),
    ],
)
def test_invoice_anticipation_classification_matrix(emission, due, payment, expected):
    classification, _ = routes.invoice_anticipation(emission, due, payment)
    assert classification == expected


@pytest.mark.parametrize(
    ("raw", "kind", "generates", "destination"),
    [
        ("Cartão Débito", "CARTAO_DEBITO", True, "CARTAO"),
        ("Cartao de Credito", "CARTAO_CREDITO", True, "CARTAO"),
        ("Dinheiro", "DINHEIRO", True, "CAIXA"),
        ("PIX", "PIX", False, "EXTRATO_BANCARIO"),
        ("Deposito bancário", "DEPOSITO", False, "REVISAR_EXTRATO"),
        ("TED", "TRANSFERENCIA", False, "REVISAR_EXTRATO"),
        ("Boleto", "BOLETO", False, "REVISAR_BOLETO"),
        ("Pagamento à vista", "DINHEIRO", True, "CAIXA"),
        ("Pagamento dividido", "PAGAMENTO_DIVIDIDO", False, "REVISAR_PAGAMENTO_DIVIDIDO"),
        ("", "NAO_IDENTIFICADO", False, "REVISAR"),
    ],
)
def test_invoice_payment_type_and_generation_decision(raw, kind, generates, destination):
    payment_type = routes.invoice_payment_type(raw)
    decision = routes.invoice_generation_decision(payment_type)

    assert payment_type == kind
    assert decision[:2] == (generates, destination)


def test_invoice_csv_generates_card_and_skips_pix_to_avoid_duplicate_statement_entry():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = Cliente(nome="Cliente")
    session.add(client); session.flush()
    reconciliation = Conciliacao(cliente_id=client.id, banco="Notas", data_inicio=date(2024, 1, 1), data_fim=date(2024, 1, 31))
    session.add(reconciliation); session.flush()
    file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="nota", banco_selecionado="Notas", nome_original="nota.pdf", caminho="/tmp/nota.pdf")
    session.add(file); session.flush()
    session.add_all([
        NotaFiscal(conciliacao_id=reconciliation.id, arquivo_id=file.id, pagina_numero=1, data_emissao=date(2024, 1, 31), fornecedor="CLIENTE CARTAO", cpf_cnpj="", numero_nota="1", valor_total=Decimal("300.00"), dados_originais=routes.enrich_invoice_data({"forma_pagamento": "Cartão Crédito", "data_vencimento": "2024-02-05", "data_pagamento": "2024-01-31", "valor_pagamento": "300.00"}, date(2024, 1, 31), Decimal("300.00"))),
        NotaFiscal(conciliacao_id=reconciliation.id, arquivo_id=file.id, pagina_numero=2, data_emissao=date(2024, 1, 31), fornecedor="CLIENTE PIX", cpf_cnpj="", numero_nota="2", valor_total=Decimal("700.00"), dados_originais=routes.enrich_invoice_data({"forma_pagamento": "PIX", "data_vencimento": "2024-02-05", "data_pagamento": "2024-01-31", "valor_pagamento": "700.00"}, date(2024, 1, 31), Decimal("700.00"))),
    ])
    session.commit()

    create_source_accounting_rule(reconciliation.id, "nota", RegraFonteInput(gatilho="cliente", conta_debito="112 - Cartões", conta_credito="311 - Receita", historico="Venda nota", complemento="Conforme nota"), session)
    data = source_accounting_rules(reconciliation.id, "nota", session)
    csv = source_accounting_csv(reconciliation.id, "nota", session).body.decode("utf-8-sig")

    assert data["resumo"] == {"total": 2, "classificados": 2, "pendentes": 0}
    pix_row = next(item for item in data["classificados"] if item["texto"] == "CLIENTE PIX")
    assert pix_row["gera_lancamento"] == "Via extrato"
    assert "CLIENTE PIX" not in csv
    assert "112;311;Venda nota;300.00;Conforme nota;CARTAO_CREDITO;CARTAO" in csv


def test_invoice_anticipation_creates_separate_rule_rows_and_csv_entries():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = Cliente(nome="Cliente")
    session.add(client); session.flush()
    reconciliation = Conciliacao(cliente_id=client.id, banco="Notas", data_inicio=date(2024, 1, 1), data_fim=date(2024, 1, 31))
    session.add(reconciliation); session.flush()
    file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="nota", banco_selecionado="Notas", nome_original="nota.pdf", caminho="/tmp/nota.pdf")
    session.add(file); session.flush()
    session.add(NotaFiscal(
        conciliacao_id=reconciliation.id,
        arquivo_id=file.id,
        pagina_numero=1,
        data_emissao=date(2024, 2, 1),
        fornecedor="CLIENTE ANTECIPADO",
        cpf_cnpj="",
        numero_nota="55",
        valor_total=Decimal("450.00"),
        dados_originais=routes.enrich_invoice_data(
            {"forma_pagamento": "Cartão Crédito", "data_vencimento": "2024-02-10", "data_pagamento": "2024-01-31", "valor_pagamento": "450.00"},
            date(2024, 2, 1),
            Decimal("450.00"),
        ),
    ))
    session.commit()

    initial = source_accounting_rules(reconciliation.id, "nota", session)
    assert initial["resumo"] == {"total": 2, "classificados": 0, "pendentes": 2}
    assert {item["tipo_lancamento_label"] for item in initial["pendentes"]} == {"Antecipação", "Baixa da antecipação"}

    create_source_accounting_rule(
        reconciliation.id,
        "nota",
        RegraFonteInput(gatilho="cliente antecipado", tipo_componente="ANTECIPACAO_CLIENTES", conta_debito="112 - Cartões", conta_credito="232 - Antecipação de clientes", historico="Antecipação de clientes", complemento="NF 55 - antecipação"),
        session,
    )
    create_source_accounting_rule(
        reconciliation.id,
        "nota",
        RegraFonteInput(gatilho="cliente antecipado", tipo_componente="BAIXA_ANTECIPACAO", conta_debito="232 - Antecipação de clientes", conta_credito="311 - Receita", historico="Baixa da antecipação", complemento="NF 55 - baixa"),
        session,
    )
    data = source_accounting_rules(reconciliation.id, "nota", session)
    csv = source_accounting_csv(reconciliation.id, "nota", session).body.decode("utf-8-sig")

    assert data["resumo"] == {"total": 2, "classificados": 2, "pendentes": 0}
    assert {item["tipo_lancamento_label"] for item in data["classificados"]} == {"Antecipação", "Baixa da antecipação"}
    assert "31/01/2024;112;232;Antecipação de clientes;450.00;NF 55 - antecipação;CARTAO_CREDITO;ANTECIPACAO_CLIENTES" in csv
    assert "01/02/2024;232;311;Baixa da antecipação;450.00;NF 55 - baixa;CARTAO_CREDITO;BAIXA_ANTECIPACAO" in csv
