from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes import accounting_rules, create_reconciliation_process, delete_reconciliation_process, reconcile, reprocess_document, resume_process_bank
from app.core.database import Base
from app.models import Arquivo, Cliente, Comprovante, Conciliacao, Correspondencia, LancamentoContabil, MovimentoExtrato, ProcessoConciliacao, RegraContabil
from app.services.normalization import normalize_name
from app.api.routes import ProcessoBancoInput, ProcessoConciliacaoInput


def test_process_resumes_the_same_bank_and_exposes_shared_rule_source():
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
    session.add(RegraContabil(cliente_id=client.id, banco="Santander", tipo_fonte="extrato", tipo_operacao="saída", favorecido_normalizado=normalize_name("PIX"), conta_debito="Despesa", conta_credito="Banco", historico="Pagamento"))
    session.commit()

    rules = accounting_rules(bradesco["id"], session)
    source = rules["pendentes"][0]["regra_compartilhada"]
    assert source["banco_origem"] == "Santander"
    assert source["gatilho"] == normalize_name("PIX")
    assert rules["salvas"] == []


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
    session.add(MovimentoExtrato(conciliacao_id=reconciliation_id, arquivo_id=file.id, pagina_numero=1, historico="PIX", natureza="saída"))
    session.commit()

    delete_reconciliation_process(process["id"], session)

    assert session.get(ProcessoConciliacao, process["id"]) is None
    assert session.query(Conciliacao).filter_by(processo_id=process["id"]).count() == 0
    assert not file_path.exists()


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
    assert session.query(MovimentoExtrato).filter_by(arquivo_id=file.id, natureza="entrada").count() == 1


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
    assert [(item.componente, item.valor, item.efeito_no_total) for item in items] == [("VALOR_COBRADO", Decimal("493.14"), "SOMA"), ("DESCONTO_ABATIMENTO", Decimal("54.79"), "SOMA")]


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
