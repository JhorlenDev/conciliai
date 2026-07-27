from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes import accounting_csv, apply_accounting_rules
from app.core.database import Base
from app.models import Arquivo, Cliente, Conciliacao, MovimentoExtrato, RegraContabil
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

    assert apply_accounting_rules(reconciliation, session) == 1
    session.commit()

    response = accounting_csv(reconciliation.id, session)
    csv = response.body.decode("utf-8-sig")
    assert csv.splitlines() == ["data;debito;credito;historico;complemento;valor", "02/01/2024;Despesa;Banco;Pagamento;Extrato;12,50"]
