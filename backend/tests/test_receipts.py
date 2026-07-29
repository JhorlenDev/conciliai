from datetime import date
from decimal import Decimal

from app.services.normalization import accounting_nature, names_similar, normalize_statement_nature
from app.services.matching import invoice_is_candidate
from app.services.parsers import deduplicate_statement_records, extract_financial_values, extract_receipts, extract_statement, parse_brl, parse_date_time


def test_receipt_is_one_line_even_with_institutional_text():
    records = extract_receipts("VALOR: 520,52\nPAGO PARA: Lia Silva\nDATA: 02/01/2024 - 09:40:01\nSAC 0800\nOUVIDORIA", 1)
    assert len(records) == 1
    assert records[0].favorecido == "Lia Silva"


def test_pix_receipt_extracts_its_separate_tariff():
    values = extract_financial_values("VALOR: 2.100,00\nTARIFA: 10,00")

    assert values.valor_pago == Decimal("2100.00")
    assert values.valor_tarifa == Decimal("10.00")


def test_statement_and_accounting_natures_support_codes_and_legacy_values():
    assert normalize_statement_nature("C") == normalize_statement_nature("entrada") == "Crédito"
    assert normalize_statement_nature("D") == normalize_statement_nature("saída") == "Débito"
    assert accounting_nature("Crédito") == "Débito"
    assert accounting_nature("Débito") == "Crédito"


def test_documento_pix_and_ted_are_never_names():
    records = extract_receipts("VALOR: R$2.300,00\nTED\nDOCUMENTO: 12\nFAVORECIDO: C ODONTO\nDEBITO EM: 02/01/2024", 1)
    assert records[0].favorecido not in {"DOCUMENTO", "PIX", "TED"}
    assert records[0].tipo_operacao == "TED"


def test_abbreviated_names_match_only_when_initials_follow_full_name_order():
    assert names_similar("Adrielle Colares Frazao De Queiroz", "Adrielle C F Queiroz")
    assert names_similar("Adrielle Colares Frazao De Queiroz", "Adrielle C Queiroz")
    assert not names_similar("Adrielle Colares Frazao De Queiroz", "Adrielle Costa Ferreira")
    assert names_similar("Adrielle Colares Frazao De", "Adrielle C F Queiroz", allow_truncated_terminal=True)
    assert not names_similar("Adrielle Colares Frazao De", "Adrielle C F Queiroz")


def test_brazilian_value_date_and_optional_time():
    assert parse_brl("R$2.300,00") == Decimal("2300.00")
    assert parse_date_time("02/01/2024 - 09:40:01") == (date(2024, 1, 2), "09:40:01")
    record = extract_receipts("VALOR: 1.287,92\nFAVORECIDO: Ana\nDÉBITO EM: 02/01/2024", 1)[0]
    assert record.hora is None


def test_receipt_blocks_are_not_mixed_and_names_match_initials():
    text = "VALOR: 1,00\nPAGO PARA: Ana\nDATA: 02/01/2024\nVALOR: 2,00\nFAVORECIDO: Bia\nDATA: 03/01/2024"
    assert [item.favorecido for item in extract_receipts(text, 1)] == ["Ana", "Bia"]
    assert names_similar("Raquel O Jesus", "Raquel Oliveira De Jesus")


def test_invoice_is_not_matched_by_value_only():
    assert not invoice_is_candidate(
        Decimal("520.52"), date(2024, 1, 2), "Fornecedor A",
        Decimal("520.52"), date(2024, 1, 2), "Fornecedor B",
    )


def test_banco_do_brasil_credit_in_statement_becomes_credit_in_system():
    text = """02/01/2024
0000
13105 144 Pix - Enviado
10.202
520,52 C
02/01 09:40 Lia Da Silva Alexandre
"""
    record = extract_statement(text, 1, "Banco do Brasil")[0]
    assert record.data == date(2024, 1, 2)
    assert record.hora == "09:40"
    assert record.nome == "Lia Da Silva Alexandre"
    assert record.valor == Decimal("520.52")
    assert record.natureza == "Crédito"


def test_banco_do_brasil_debit_in_statement_becomes_debit_in_system():
    text = """02/01/2024
0000
13105 144 Pix - Recebido
10.202
520,52 D
02/01 09:40 Lia Da Silva Alexandre
"""
    assert extract_statement(text, 1, "Banco do Brasil")[0].natureza == "Débito"


def test_banco_do_brasil_parser_is_not_used_for_other_banks():
    text = """02/01/2024
0000
13105 144 Pix - Enviado
10.202
520,52 C
02/01 09:40 Lia Da Silva Alexandre
"""
    assert extract_statement(text, 1, "Santander") == []


def test_banco_do_brasil_uses_first_cd_value_and_ignores_balance_rows():
    text = """02/01/2024
0000
BB Rende Fácil
10.202
100,00 C 1.000,00 C
02/01 09:40 Aplicação
02/01/2024
0000
Saldo do dia
10.203
1.000,00 C
02/01/2024
0000
PIX - Enviado
10.204
100,00 D 900,00 D
02/01 10:00 Fornecedor
"""

    records = extract_statement(text, 1, "Banco do Brasil")

    assert [(item.historico, item.valor, item.natureza) for item in records] == [
        ("BB Rende Fácil", Decimal("100.00"), "Crédito"),
        ("PIX - Enviado", Decimal("100.00"), "Débito"),
    ]


def test_banco_do_brasil_page_boundary_duplicate_is_kept_once():
    text = """02/01/2024
0000
PIX - Enviado
10.202
520,52 C
02/01 09:40 Lia Da Silva Alexandre
"""
    records = extract_statement(text, 1, "Banco do Brasil") + extract_statement(text, 2, "Banco do Brasil")

    assert len(deduplicate_statement_records(records)) == 1


def test_receipt_uses_payment_date_before_document_date():
    text = """VALOR: 493,14
FAVORECIDO: Conselho Federal
DATA: 31/12/2023
DATA DO PAGAMENTO: 02/01/2024
"""

    assert extract_receipts(text, 1)[0].data == date(2024, 1, 2)


def test_boleto_uses_paid_value_for_matching_and_keeps_accounting_components():
    text = """VALOR DO DOCUMENTO: 547,93
DESCONTO/ABATIMENTO: 54,79
VALOR COBRADO: 493,14
BENEFICIÁRIO: CONSELHO FEDERAL DE ODONTOLOGI
DATA DO PAGAMENTO: 31/01/2024
"""
    receipt = extract_receipts(text, 32)[0]

    assert receipt.data == date(2024, 1, 31)
    assert receipt.valor == Decimal("493.14")
    assert receipt.financeiros.valor_original == Decimal("547.93")
    assert receipt.financeiros.valor_desconto_abatimento == Decimal("54.79")


def test_receipt_keeps_beneficiary_when_final_beneficiary_differs():
    text = """VALOR: 1.000,00
BENEFICIÁRIO: BAMBUNO TECNOLOGIA LTDA
BENEFICIÁRIO FINAL: SUCESSODONTO CURSOS E TREINAMENTOS
PAGADOR: RENATA KAMILE DE SOUSA FIGUEIRO
DATA DO PAGAMENTO: 30/01/2024
"""
    receipt = extract_receipts(text, 1)[0]

    assert receipt.favorecido == "BAMBUNO TECNOLOGIA LTDA"
    assert receipt.beneficiario_final == "SUCESSODONTO CURSOS E TREINAMENTOS"
    assert receipt.pagador == "RENATA KAMILE DE SOUSA FIGUEIRO"


def test_receipt_reads_multiline_beneficiary_before_final_beneficiary():
    text = """VALOR COBRADO 1.000,00
BENEFICIARIO:
BAMBUNO TECNOLOGIA LTDA
BENEFICIARIO FINAL:
SUCESSODONTO CURSOS E TREINAMENTOS
DATA DO PAGAMENTO 30/01/2024
"""
    receipt = extract_receipts(text, 1)[0]

    assert receipt.beneficiario == "BAMBUNO TECNOLOGIA LTDA"
    assert receipt.beneficiario_final == "SUCESSODONTO CURSOS E TREINAMENTOS"


def test_banco_do_brasil_reads_inline_document_value_and_keeps_same_day_duplicates():
    text = """30/01/2024
0000
TED-Crédito em Conta
319.950.632 12.000,00 C
Cliente A
31/01/2024
0000
Pagamento de Boleto
13.101
493,14 D
Conselho Federal
31/01/2024
0000
Pagamento de Boleto
13.102
493,14 D
Conselho Federal
"""
    records = extract_statement(text, 1, "Banco do Brasil")

    assert [(item.valor, item.natureza) for item in records] == [
        (Decimal("12000.00"), "Crédito"),
        (Decimal("493.14"), "Débito"),
        (Decimal("493.14"), "Débito"),
    ]
    assert len(deduplicate_statement_records(records)) == 3


def test_payment_receipt_uses_beneficiario_final_and_valor_documento():
    text = """DATA DO PAGAMENTO: 02/01/2024
BENEFICIARIO FINAL: QUANTITY SERVICOS E COMERCIO DE PRO
VALOR DO DOCUMENTO: 680,49
"""
    record = extract_receipts(text, 1)[0]
    assert record.data == date(2024, 1, 2)
    assert record.favorecido == "QUANTITY SERVICOS E COMERCIO DE PRO"
    assert record.valor == Decimal("680.49")
    assert record.tipo_operacao == "PAGAMENTO"


def test_banco_do_brasil_payment_receipt_reads_name_on_next_line():
    text = """BENEFICIARIO FINAL:
QUANTITY SERVICOS E COMERCIO DE PRO
DATA DO PAGAMENTO                     02/01/2024
VALOR DO DOCUMENTO                        680,49
"""
    record = extract_receipts(text, 1)[0]
    assert record.favorecido == "QUANTITY SERVICOS E COMERCIO DE PRO"
    assert record.valor == Decimal("680.49")


def test_banco_do_brasil_transfer_receipt_reads_transferred_client():
    text = """DATA DA TRANSFERENCIA                 16/01/2024
VALOR TOTAL                             6.000,00
****** TRANSFERIDO PARA:
CLIENTE: LEANDRO BARBOSA FIGUEIRO
"""
    record = extract_receipts(text, 1)[0]
    assert record.favorecido == "LEANDRO BARBOSA FIGUEIRO"
    assert record.valor == Decimal("6000.00")
    assert record.tipo_operacao == "TRANSFERÊNCIA"


def test_receipt_with_received_from_is_valid():
    text = """DATA DO RECEBIMENTO: 02/01/2024
RECEBIDO DE: Cliente Exemplo
VALOR RECEBIDO: 250,00
"""
    record = extract_receipts(text, 1)[0]
    assert record.favorecido == "Cliente Exemplo"
    assert record.valor == Decimal("250.00")
    assert record.tipo_operacao == "RECEBIMENTO"


def test_beneficiario_is_used_once_when_payment_date_repeats():
    text = """DATA DO PAGAMENTO 08/01/2024
BENEFICIARIO: AMAZONAS ENERGIA S.A.
DATA DO PAGAMENTO 08/01/2024
VALOR: R$ 450,00
"""
    records = extract_receipts(text, 1)
    assert len(records) == 1
    assert records[0].data == date(2024, 1, 8)
    assert records[0].favorecido == "AMAZONAS ENERGIA S.A."
    assert records[0].valor == Decimal("450.00")


def test_beneficiario_is_kept_when_final_beneficiary_also_exists():
    text = """BENEFICIARIO: Nome Intermediario
BENEFICIARIO FINAL: Nome Final
DATA DO PAGAMENTO: 08/01/2024
VALOR: 450,00
"""
    assert extract_receipts(text, 1)[0].favorecido == "Nome Intermediario"


def test_convenio_is_used_when_no_higher_priority_name_exists():
    text = """Data do pagamento 08/01/2024
Convenio CLARO S.A.
Valor Total 89,26
"""
    record = extract_receipts(text, 1)[0]
    assert record.data == date(2024, 1, 8)
    assert record.hora is None
    assert record.favorecido == "CLARO S.A."
    assert record.valor == Decimal("89.26")
    assert record.origem_nome == "CONVENIO"


def test_convenio_does_not_override_beneficiario_final():
    text = """CONVENIO: CLARO S.A.
BENEFICIARIO FINAL: Energia Final
DATA DO PAGAMENTO: 08/01/2024
VALOR TOTAL: 89,26
"""
    assert extract_receipts(text, 1)[0].favorecido == "Energia Final"


def test_boleto_with_discount_uses_charged_value_for_reconciliation():
    text = """PAGO PARA: CRO-AM
DATA DO PAGAMENTO: 31/01/2024
VALOR DO DOCUMENTO: 547,93
DESCONTO/ABATIMENTO: 54,79
VALOR COBRADO: 493,14
"""
    records = extract_receipts(text, 1)
    assert len(records) == 1
    record = records[0]
    assert record.financeiros.valor_original == Decimal("547.93")
    assert record.financeiros.valor_desconto_abatimento == Decimal("54.79")
    assert record.financeiros.valor_pago == Decimal("493.14")
    assert record.valor == Decimal("493.14")
    assert not record.financeiros.composicao_divergente


def test_interest_and_fine_are_added_to_original_value():
    text = """FAVORECIDO: Fornecedor
DATA: 02/01/2024
VALOR ORIGINAL: 100,00
JUROS/MORA: 5,50
MULTA/MORA: 10,00
VALOR PAGO: 115,50
"""
    financial = extract_receipts(text, 1)[0].financeiros
    assert financial.valor_juros == Decimal("5.50")
    assert financial.valor_multa == Decimal("10.00")
    assert financial.valor_pago == Decimal("115.50")
    assert not financial.composicao_divergente


def test_simple_receipt_has_paid_and_original_value_without_invented_adjustments():
    text = """PAGO PARA: Lia Silva
DATA: 02/01/2024
VALOR: 520,52
"""
    financial = extract_receipts(text, 1)[0].financeiros
    assert financial.valor_original == Decimal("520.52")
    assert financial.valor_pago == Decimal("520.52")
    assert financial.valor_desconto is None
    assert financial.valor_juros is None
    assert financial.valor_multa is None
