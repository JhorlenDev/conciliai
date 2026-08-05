from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes import accounting_csv, sync_document_items, tax_complement
from app.core.database import Base
from app.models import Arquivo, Cliente, Comprovante, ComprovanteRfb, Conciliacao, ContaBancaria, Correspondencia, LancamentoContabil, MovimentoExtrato
from app.services.rfb import extract_competence
from app.services.rule_source import RuleLine


def tax_session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = Cliente(nome="Cliente")
    session.add(client); session.flush()
    reconciliation = Conciliacao(cliente_id=client.id, banco="Banco do Brasil", data_inicio=date(2024, 1, 1), data_fim=date(2024, 1, 31))
    session.add(reconciliation); session.flush()
    file = Arquivo(conciliacao_id=reconciliation.id, tipo_documento="extrato", banco_selecionado=reconciliation.banco, nome_original="extrato.pdf", caminho="/tmp/extrato.pdf")
    session.add(file); session.flush()
    movement = MovimentoExtrato(conciliacao_id=reconciliation.id, arquivo_id=file.id, pagina_numero=1, data=date(2024, 1, 10), historico="IMPOSTOS", valor=Decimal("100.00"), natureza="saída")
    session.add(movement); session.flush()
    match = Correspondencia(conciliacao_id=reconciliation.id, movimento_extrato_id=movement.id)
    session.add(match); session.flush()
    return session, reconciliation, file, match


def linked_rfb(session, reconciliation, file, match, tipo="DARF", competencia="01/2024"):
    rfb = ComprovanteRfb(conciliacao_id=reconciliation.id, arquivo_id=file.id, pagina_numero=1, tipo=tipo, competencia=competencia, texto_original=f"Competência: {competencia}")
    session.add(rfb); session.flush()
    match.comprovante_rfb_id = rfb.id
    return rfb


def test_simples_nacional_gets_competence_complement_and_csv_value():
    session, reconciliation, file, match = tax_session()
    linked_rfb(session, reconciliation, file, match, tipo="DAS")
    sync_document_items(match, [RuleLine("SIMPLES_NACIONAL", Decimal("100.00"), descricao="SIMPLES NACIONAL", origem="rfb")], session)
    entry = session.query(LancamentoContabil).one()
    entry.conta_debito, entry.conta_credito, entry.historico, entry.status = "219", "101", "Simples", "editado_manual"
    session.add(ContaBancaria(cliente_id=reconciliation.cliente_id, banco=reconciliation.banco, conta_contabil="219 - Banco"))
    session.commit()

    csv = accounting_csv(reconciliation.id, session).body.decode("utf-8-sig")

    assert entry.complemento == "SIMPLES NACIONAL - COMPETÊNCIA 01/2024"
    assert csv.splitlines()[1].endswith("SIMPLES NACIONAL - COMPETÊNCIA 01/2024")


def test_irrf_and_inss_keep_individual_complements_from_same_receipt():
    session, reconciliation, file, match = tax_session()
    linked_rfb(session, reconciliation, file, match)
    sync_document_items(match, [RuleLine("IRRF", Decimal("30.00"), "0561", "IRRF", origem="rfb"), RuleLine("INSS", Decimal("70.00"), "1082", "INSS", origem="rfb")], session)

    entries = session.query(LancamentoContabil).order_by(LancamentoContabil.ordem).all()

    assert [(entry.componente, entry.valor, entry.complemento) for entry in entries] == [("IRRF", Decimal("30.00"), "IRRF - COMPETÊNCIA 01/2024"), ("INSS", Decimal("70.00"), "INSS - COMPETÊNCIA 01/2024")]


def test_fgts_uses_competence_from_its_linked_bank_receipt():
    session, reconciliation, file, match = tax_session()
    receipt = Comprovante(conciliacao_id=reconciliation.id, arquivo_id=file.id, pagina_numero=1, texto_original="FGTS\nPA: 012024")
    session.add(receipt); session.flush()
    match.comprovante_id = receipt.id
    sync_document_items(match, [RuleLine("PRINCIPAL", Decimal("100.00"), descricao="FGTS", origem="comprovante")], session)

    assert session.query(LancamentoContabil).one().complemento == "FGTS - COMPETÊNCIA 01/2024"


def test_tax_without_competence_keeps_complement_empty_and_is_signaled():
    session, reconciliation, file, match = tax_session()
    linked_rfb(session, reconciliation, file, match, competencia="")
    sync_document_items(match, [RuleLine("IRRF", Decimal("100.00"), "0561", "IRRF", origem="rfb")], session)
    entry = session.query(LancamentoContabil).one()

    tax, competence, complement, source = tax_complement(entry, match, session)

    assert (tax, competence, complement, source, entry.complemento) == ("IRRF", "", "", "Comprovante RFB", "")


@pytest.mark.parametrize(("value", "expected"), [("01/2024", "01/2024"), ("01-2024", "01/2024"), ("012024", "01/2024"), ("01/09/2024", "09/2024")])
def test_competence_formats_are_normalized(value, expected):
    assert extract_competence(f"Período de Apuração: {value}") == expected


def test_manual_complement_is_preserved_and_common_entry_is_unchanged():
    session, reconciliation, file, match = tax_session()
    linked_rfb(session, reconciliation, file, match)
    manual = LancamentoContabil(correspondencia_id=match.id, componente="IRRF", valor=Decimal("100.00"), complemento="IRRF - COMPETÊNCIA CORRIGIDA", status="editado_manual")
    common = LancamentoContabil(correspondencia_id=match.id, componente="PRINCIPAL", valor=Decimal("1.00"), descricao="Fornecedor", status="pendente_regra")
    session.add_all([manual, common]); session.commit()

    sync_document_items(match, [RuleLine("IRRF", Decimal("100.00"), "0561", "IRRF", origem="rfb")], session)

    assert manual.complemento == "IRRF - COMPETÊNCIA CORRIGIDA"
    assert common.complemento == ""
