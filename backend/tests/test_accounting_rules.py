from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes import accounting_csv, accounting_rules, apply_accounting_rules
from app.core.database import Base
from app.models import Arquivo, Cliente, Conciliacao, ContaBancaria, LancamentoContabil, MovimentoExtrato, RegraContabil
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
    assert data["resumo"]["razao"] == {"debito": "12.50", "credito": "0"}


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
    assert data["salvas"][0]["natureza"] == "entrada"
    entry = session.query(LancamentoContabil).filter_by(status="aplicado_por_regra").one()
    assert (entry.valor, entry.conta_debito, entry.conta_credito) == (Decimal("20.00"), "Banco", "Receita")
    assert data["resumo"]["razao"] == {"debito": "0", "credito": "20.00"}


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
