from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes import accounting_rules, create_reconciliation_process, delete_reconciliation_process, resume_process_bank
from app.core.database import Base
from app.models import Arquivo, Cliente, Conciliacao, MovimentoExtrato, ProcessoConciliacao, RegraContabil
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
    session.add(MovimentoExtrato(conciliacao_id=bradesco["id"], arquivo_id=statement.id, pagina_numero=1, historico="PIX FORNECEDOR", natureza="saída"))
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
