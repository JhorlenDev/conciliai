from datetime import date
from decimal import Decimal

import pytest

from app.services.normalization import accounting_nature, names_similar, normalize_statement_nature
from app.services.matching import invoice_is_candidate
from app.services.parsers import ParsedStatement, _validate_santander_expected_statement, deduplicate_statement_records, extract_financial_values, extract_invoices, extract_loan_receipts, extract_receipts, extract_santander_words_statement, extract_statement, extract_statement_pages, parse_brl, parse_date_time
from app.api.routes import receipt_match_criterion
from app.models import Comprovante


def test_receipt_is_one_line_even_with_institutional_text():
    records = extract_receipts("VALOR: 520,52\nPAGO PARA: Lia Silva\nDATA: 02/01/2024 - 09:40:01\nSAC 0800\nOUVIDORIA", 1)
    assert len(records) == 1
    assert records[0].favorecido == "Lia Silva"


def test_loan_receipt_extracts_contract_principal_interest_and_total():
    text = """COMPROVANTE DE EMPRÉSTIMO / FINANCIAMENTO
CONTRATO: 57.709.569
DATA DO DÉBITO: 15/01/2024
VALOR PRINCIPAL: 2.083,33
JUROS: 733,67
VALOR TOTAL: 2.817,00
"""
    records = extract_loan_receipts(text, 1)

    assert len(records) == 1
    record = records[0]
    assert record.data == date(2024, 1, 15)
    assert record.numero_documento == "57.709.569"
    assert record.valor == Decimal("2817.00")
    assert record.financeiros.valor_original == Decimal("2083.33")
    assert record.financeiros.valor_juros == Decimal("733.67")
    assert record.tipo_operacao == "EMPRÉSTIMO/FINANCIAMENTO"


def test_banco_do_brasil_loan_schedule_groups_interest_and_capital_by_date():
    text = """SISBB - Sistema de Informacoes do Banco do Brasil
Credito Rural e Comercial
Cronograma Reposicao Exigivel
Mutuario . . . : CENTRO ODONTOLOGICO FIGUEIRO LTDA ME     Operacao: 057.709.569
Vencimento Parcela                         Previsto      Realizado      Exigivel
15.01.2024 JUROS                             733,67        733,67         0,00
15.01.2024 CAPITAL                         2.083,33      2.083,33         0,00
15.02.2024 JUROS                             672,53        672,53         0,00
15.02.2024 CAPITAL                         2.083,33      2.083,33         0,00
"""
    records = extract_loan_receipts(text, 1)

    january = records[0]
    assert january.data == date(2024, 1, 15)
    assert january.numero_documento == "057.709.569"
    assert january.valor == Decimal("2817.00")
    assert january.financeiros.valor_original == Decimal("2083.33")
    assert january.financeiros.valor_juros == Decimal("733.67")
    assert january.financeiros.valor_encargos is None
    assert records[1].valor == Decimal("2755.86")


def test_banco_do_brasil_loan_schedule_tolerates_ocr_amount_noise():
    text = """Cronograma Reposicao Exigivel
Operacao: 057.709.569
Vencimento Parcela                         Previsto      Realizado      Exigivel
15.07.2024 JUROS                             355,00        355,00         0,00
15.07.2024 CAPITAL                         2.083, 33      2.083; 33      0,00
15.08.2024 JUROS                             305,70        305,70         0,00
15.08.2024 CAPITAL                         2.083,33      2:083,33       0,00
"""
    records = extract_loan_receipts(text, 1)

    assert records[0].data == date(2024, 7, 15)
    assert records[0].valor == Decimal("2438.33")
    assert records[0].financeiros.valor_original == Decimal("2083.33")
    assert records[0].financeiros.valor_juros == Decimal("355.00")
    assert records[1].valor == Decimal("2389.03")


def test_invoice_extracts_supplier_number_date_and_total():
    text = """NOTA FISCAL DE SERVIÇOS ELETRÔNICA
NÚMERO DA NOTA: 12345
DATA DE EMISSÃO: 10/01/2024
PRESTADOR: CLINICA EXEMPLO LTDA
CNPJ: 12.345.678/0001-90
VALOR TOTAL DA NOTA: 1.250,75
"""
    records = extract_invoices(text, 1)

    assert len(records) == 1
    record = records[0]
    assert record.data_emissao == date(2024, 1, 10)
    assert record.numero_nota == "12345"
    assert record.fornecedor == "CLINICA EXEMPLO LTDA"
    assert record.cpf_cnpj == "12.345.678/0001-90"
    assert record.valor_total == Decimal("1250.75")


def test_tefe_nfse_extracts_number_taker_total_and_payment_data():
    text = """PM DE TEFE - AM
NOTA FISCAL DE SERVIÇOS ELETRÔNICA - NFS-e
Número da NFS-e
512932
Data e Hora de Emissão da NFS-e
31/01/2024 às 16:48:55
PRESTADOR DE SERVIÇOS
CPF/CNPJ RG/Inscrição Estadual Inscrição Municipal Cadastro Nome/Razão Social
08.695.575/0001-88 01010240237001 000200437 CENTRO ODONTOLOGICO FIGUEIRO LTDA - ME
TOMADOR DE SERVIÇOS
CPF/CNPJ/Documento RG/Inscrição Estadual Inscrição Municipal Nome/Razão Social
014.782.102-90 KARLA DANIELY DE AMORIM PEREIRA
Discriminação dos Serviços
1.0 UN PRESTAÇÃO DE SERVIÇOS ODONTOLÓGICOS 120.0 R$ 120,00
Valor Líquido da NFS-e: R$ 120,00
FATURAS: PIX Venc: 27/01/2024 R$ 120,00 Doc: 1434 Obs: null
"""
    records = extract_invoices(text, 3)

    assert len(records) == 1
    record = records[0]
    assert record.pagina_numero == 3
    assert record.numero_nota == "512932"
    assert record.data_emissao == date(2024, 1, 31)
    assert record.fornecedor == "KARLA DANIELY DE AMORIM PEREIRA"
    assert record.cpf_cnpj == "014.782.102-90"
    assert record.valor_total == Decimal("120.00")
    assert record.dados["prestador"] == "CENTRO ODONTOLOGICO FIGUEIRO LTDA - ME"
    assert record.dados["forma_pagamento"] == "PIX"
    assert record.dados["data_pagamento"] == "2024-01-27"
    assert record.dados["documento_pagamento"] == "1434"


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
    assert records[0].numero_documento == "12"


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


def test_banco_do_brasil_extracts_multiple_receipts_on_same_page_without_mixing_values():
    text = """26/05/2026    -  BANCO  DO  BRASIL  -   10:55:20
          COMPROVANTE DE TRANSFERENCIA
DATA DA TRANSFERENCIA                 17/04/2024
NR. DOCUMENTO                 32.600.000.023.452
VALOR TOTAL                             1.700,00
******  TRANSFERIDO PARA:
CLIENTE: MARIA LUZIRDA C MIRANDA
================================================
SISBB  -  SISTEMA DE INFORMACOES BANCO DO BRASIL
                Comprovante Pix
PAGAMENTO VIA QR CODE
VALOR:                                    408,80
DATA:                      19/04/2024 - 05:33:26
PAGO PARA:  Cef Matriz
DOCUMENTO: 041901
================================================
22/04/2024    -  BANCO  DO  BRASIL  -   11:48:51
          COMPROVANTE DE TRANSFERENCIA
DATA DA TRANSFERENCIA                 22/04/2024
NR. DOCUMENTO                610.577.000.025.632
VALOR TOTAL                             8.000,00
******  TRANSFERIDO PARA:
CLIENTE: LEANDRO BARBOSA FIGUEIRO
"""

    records = extract_receipts(text, 5)

    assert [(item.data, item.tipo_operacao, item.favorecido, item.valor, item.numero_documento) for item in records] == [
        (date(2024, 4, 17), "TRANSFERÊNCIA", "MARIA LUZIRDA C MIRANDA", Decimal("1700.00"), "32.600.000.023.452"),
        (date(2024, 4, 19), "PIX", "Cef Matriz", Decimal("408.80"), "041901"),
        (date(2024, 4, 22), "TRANSFERÊNCIA", "LEANDRO BARBOSA FIGUEIRO", Decimal("8000.00"), "610.577.000.025.632"),
    ]


def test_banco_do_brasil_extracts_two_title_payment_receipts_on_same_page():
    text = """26/05/2026    -  BANCO  DO  BRASIL  -   10:55:20
     COMPROVANTE DE PAGAMENTO DE TITULOS
BENEFICIARIO:
MUNICIPIO DE TEFE
NR. DOCUMENTO                             43.001
DATA DO PAGAMENTO                     30/04/2024
VALOR DO DOCUMENTO                        508,04
VALOR COBRADO                             508,04
================================================
26/05/2026    -  BANCO  DO  BRASIL  -   10:55:20
     COMPROVANTE DE PAGAMENTO DE TITULOS
BENEFICIARIO:
MUNICIPIO DE TEFE
NR. DOCUMENTO                             43.002
DATA DO PAGAMENTO                     30/04/2024
VALOR DO DOCUMENTO                        401,25
VALOR COBRADO                             401,25
"""

    records = extract_receipts(text, 7)

    assert [(item.numero_documento, item.valor) for item in records] == [("43.001", Decimal("508.04")), ("43.002", Decimal("401.25"))]


def test_banco_do_brasil_extracts_automatic_debit_receipt_with_dotted_date():
    text = """SISBB  -  SISTEMA DE INFORMACOES BANCO DO BRASIL
        COMPROVANTE DE DEBITO AUTOMATICO
CONVENIO: 016551       BB SEGURO CRED PROT EMPR
DATA DO DEBITO:                       01.04.2024
VALOR DO DEBITO R$                        136,93
HISTORICO LANCAMENTO:  PAGAMENTO SEGURO BB
"""

    record = extract_receipts(text, 1)[0]

    assert record.data == date(2024, 4, 1)
    assert record.tipo_operacao == "DÉBITO AUTOMÁTICO"
    assert "BB SEGURO" in record.favorecido
    assert record.valor == Decimal("136.93")


def test_santander_extracts_receipts_from_consolidated_tables():
    text = """EXTRATO CONSOLIDADO INTELIGENTE
janeiro/2024
Débito Automático em Conta Corrente
Data
Descrição
Nº Identificação
Valor (R$)
Realizado
Motivo
Limite para
Débito (R$)
02/01
CARTAO DE CREDITO
MASTERCARD
55264202
2.320,83
Sim
-
NÃO HÁ
Comprovantes de Pagamento
Contas de Consumo
Data de
Pagamento Canal
Nome da
Empresa
Data de
Vencimento
Valor
(R$)
Código de Barras
Autenticação
Bancária
18/01
INTERNET
BANKING
TNL PSC SA - RJ
-
396,15
846800000032-961501132974-
878932903411-079167002009
50039143067323780040434
Transferências entre Contas, DOCs, TEDs e PIXs Enviados
Data Canal
Tipo
Favorecido
Banco Agência
Conta
Valor (R$)
10/01 INTERNET BANKING
TRANSF. CONTAS
LEANDRO BARBOSA FIGUEIRO
0033
2478
0000010026686
4.500,00
15/01 INTERNET BANKING
TED
LEANDRO BARBOSA FIGUEIRO
0001
0577
0000000256323
6.000,00
25/01 INTERNET BANKING
TED
RENATA FIGUEIRO
0001
0577
0000000236705
6.000,00
Não estão contempladas nesse quadro as transferências efetuadas
Créditos Contratados
"""

    records = extract_receipts(text, 5)

    assert [(item.data, item.tipo_operacao, item.favorecido, item.valor, item.numero_documento) for item in records] == [
        (date(2024, 1, 2), "DÉBITO AUTOMÁTICO", "CARTAO DE CREDITO MASTERCARD", Decimal("2320.83"), "55264202"),
        (date(2024, 1, 18), "PAGAMENTO", "TNL PSC SA - RJ", Decimal("396.15"), "50039143067323780040434"),
        (date(2024, 1, 10), "TRANSFERÊNCIA", "LEANDRO BARBOSA FIGUEIRO", Decimal("4500.00"), "0033 2478 0000010026686"),
        (date(2024, 1, 15), "TED", "LEANDRO BARBOSA FIGUEIRO", Decimal("6000.00"), "0001 0577 0000000256323"),
        (date(2024, 1, 25), "TED", "RENATA FIGUEIRO", Decimal("6000.00"), "0001 0577 0000000236705"),
    ]


def test_santander_extracts_internet_banking_title_receipt_with_charges():
    text = """CENTRO ODONTOLOGICO FIGUEIRO LTDA
Internet Banking Empresarial
Títulos > 2ª via de Comprovante
Dados do Beneﬁciário Original
CNPJ:
07.707.650/0001-10
Razão Social:
QUANTITY SERVICOS E
COMERCIO DE PRODUTOS
PARA SAUD
Nome Fantasia:
QUANTITY SERVICOS E
COMERCIO DE PRODUTOS
PARA SAUD
Dados do Pagador Original
Dados do Pagamento
Data de Vencimento:
10/01/2024
Valor Nominal:
R$ 835,00
Encargos:
R$ 1,40
Valor total pago:
R$ 836,40
Data da Transação:
15/01/2024
Número de Autenticação da Instituição Financeira Favorecida:
B9B664BB73A6A85535A8BAB
Canal:
Internet Banking
"""

    record = extract_receipts(text, 6)[0]

    assert record.data == date(2024, 1, 15)
    assert record.tipo_operacao == "PAGAMENTO"
    assert record.favorecido == "QUANTITY SERVICOS E COMERCIO DE PRODUTOS PARA SAUD"
    assert record.valor == Decimal("836.40")
    assert record.financeiros.valor_original == Decimal("835.00")
    assert record.financeiros.valor_encargos == Decimal("1.40")
    assert not record.financeiros.composicao_divergente
    assert record.cnpj_beneficiario == "07.707.650/0001-10"
    assert record.numero_documento == "B9B664BB73A6A85535A8BAB"


def test_getnet_sales_report_extracts_net_gross_fee_and_quantity():
    text = """O que vendi - Consolidado por Data de Vendas
Razão Social: CENTRO ODONTOLOGICO FIGUEIRO LTDA
Período: 01/01/2024 a 31/01/2024
MASTERCARD CRÉDITO
02/01/2024
12289884
R$ 220,00
R$ 215,29
- R$ 4,71
1
VISA DÉBITO
04/01/2024
12289884
R$ 540,00
R$ 534,60
- R$ 5,40
4
"""

    records = extract_receipts(text, 1)

    assert len(records) == 2
    assert records[0].data == date(2024, 1, 2)
    assert records[0].favorecido == "GETNET - MASTERCARD CRÉDITO"
    assert records[0].tipo_operacao == "GETNET VENDAS"
    assert records[0].valor == Decimal("215.29")
    assert records[0].financeiros.valor_original == Decimal("220.00")
    assert records[0].financeiros.valor_tarifa == Decimal("4.71")
    assert records[0].financeiros.valor_pago == Decimal("215.29")
    assert records[0].financeiros.detalhes["quantidade_vendas"] == "1"
    assert not records[0].financeiros.composicao_divergente
    assert records[1].financeiros.detalhes["quantidade_vendas"] == "4"


def test_getnet_sales_report_extracts_inline_rows_without_header():
    text = """12289884 VISA DÉBITO  15/07/2024  1       R$ 200,00  - R$ 2,74  R$ 197,26
12289884 MASTERCARD DÉBITO 08/07/2024 2    R$ 0,00    R$ 0,00    R$ 0,00
"""

    records = extract_receipts(text, 2)

    assert len(records) == 1
    assert records[0].data == date(2024, 7, 15)
    assert records[0].favorecido == "GETNET - VISA DÉBITO"
    assert records[0].financeiros.valor_original == Decimal("200.00")
    assert records[0].financeiros.valor_tarifa == Decimal("2.74")
    assert records[0].financeiros.valor_pago == Decimal("197.26")


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


def test_basa_extracts_statement_table_rows():
    text = """DATA    NR DOC HISTÓRICO                             VALOR LANCTO D/C       SALDO
   02/01/2024 026577 1127 - AUTOMATIZACAO TARIFA MANUTENCAO PJ -45,00 D     40.318,30
   02/01/2024 021031 1025 - TARIFA ENVIO SMS EM CONTA CORRENTE -0,22 D      40.318,08
   15/01/2024 235096 1417 - DEB PARCELA CONTRATO FOMENTO   -248,94  D       40.069,14
                                                            Total de débito:  294,16
                                                           Total de crédito:
"""
    records = extract_statement(text, 1, "BASA")

    assert len(records) == 3
    assert records[0].data == date(2024, 1, 2)
    assert records[0].numero_documento == "026577"
    assert records[0].historico == "1127 - AUTOMATIZACAO TARIFA MANUTENCAO PJ"
    assert records[0].nome == "AUTOMATIZACAO TARIFA MANUTENCAO PJ"
    assert records[0].valor == Decimal("45.00")
    assert records[0].natureza == "Débito"
    assert sum(record.valor for record in records if record.natureza == "Débito") == Decimal("294.16")


def test_basa_extracts_credit_from_dc_column():
    text = """DATA    NR DOC HISTÓRICO                             VALOR LANCTO D/C       SALDO
   03/01/2024 000123 9999 - CREDITO PIX RECEBIDO 1.234,56 C     41.552,64
"""
    record = extract_statement(text, 1, "BASA")[0]

    assert record.numero_documento == "000123"
    assert record.valor == Decimal("1234.56")
    assert record.natureza == "Crédito"


def test_santander_extracts_single_date_column_statement_without_bb_rules():
    text = """Resumo - janeiro/2024
Conta Corrente
Movimentação
Data
Descrição
Nº Documento
SALDO EM 31/12
02/01
TARIFA MENSALIDADE PACOTE SERVICOS
DEZEMBRO / 2023
TED RECEBIDA
TRANSFERENCIA ENTRE CONTA
PAGAMENTO CARTAO DE DEBITO
GETNET-VISA ELECTR
PAGAMENTO CARTAO DE DEBITO
GETNET-ELO DEBITO
DEBITO AUT. FAT.CARTAO MASTER CARD
FINAL 4202
JUROS SALDO UTILIZ ATE LIMITE
PERIODO: 01/12 A 31/12/23
IOF IMPOSTO OPERACOES FINANCEIRAS
PERIODO: 01/12 A 31/12/23
IOF ADICIONAL - AUTOMATICO
PERIODO: 01/12 A 31/12/23
Movimentos (R$)
Créditos
Débitos
-
Saldo (R$)
0,00
106,50-
-2.300,00
289884217,80
289884257,40
-2.320,83-
-5,58-
-0,08-
-2,71-
Extrato_PJ_A4_Inteligente 1.0
"""

    records = extract_statement(text, 1, "Santander")

    assert [(item.data, item.historico, item.valor, item.natureza) for item in records] == [
        (date(2024, 1, 2), "TARIFA MENSALIDADE PACOTE SERVICOS DEZEMBRO / 2023", Decimal("106.50"), "Débito"),
        (date(2024, 1, 2), "TED RECEBIDA TRANSFERENCIA ENTRE CONTA", Decimal("2300.00"), "Crédito"),
        (date(2024, 1, 2), "PAGAMENTO CARTAO DE DEBITO GETNET-VISA ELECTR", Decimal("217.80"), "Crédito"),
        (date(2024, 1, 2), "PAGAMENTO CARTAO DE DEBITO GETNET-ELO DEBITO", Decimal("257.40"), "Crédito"),
        (date(2024, 1, 2), "DEBITO AUT. FAT.CARTAO MASTER CARD FINAL 4202", Decimal("2320.83"), "Débito"),
        (date(2024, 1, 2), "JUROS SALDO UTILIZ ATE LIMITE PERIODO: 01/12 A 31/12/23", Decimal("5.58"), "Débito"),
        (date(2024, 1, 2), "IOF IMPOSTO OPERACOES FINANCEIRAS PERIODO: 01/12 A 31/12/23", Decimal("0.08"), "Débito"),
        (date(2024, 1, 2), "IOF ADICIONAL - AUTOMATICO PERIODO: 01/12 A 31/12/23", Decimal("2.71"), "Débito"),
    ]


def test_santander_does_not_guess_dates_when_column_text_loses_row_alignment():
    text = """Pagina:2/10EXTRATO CONSOLIDADO INTELIGENTE
janeiro/2024
Data
03/01
04/01
Descrição
APLICACAO CONTAMAX
ANTECIPACAO GETNET
Nº Documento
Movimentos (R$)
Créditos
DébitosSaldo (R$)
339,50-0,00
205,21-0,00
"""

    assert extract_statement(text, 2, "Santander") == []


def test_santander_does_not_shift_values_when_description_count_differs():
    text = """Resumo - janeiro/2024
Conta Corrente
Movimentação
Data
Descrição
Nº Documento
SALDO EM 31/12
02/01
PAGAMENTO CARTAO DE DEBITO
GETNET-ELO DEBITO
DEBITO AUT. FAT.CARTAO MASTER CARD
FINAL 4202
Movimentos (R$)
Créditos
Débitos
Saldo (R$)
0,00
-2.320,83-
Extrato_PJ_A4_Inteligente 1.0
"""

    records = extract_statement(text, 1, "Santander")

    assert [(item.historico, item.valor, item.natureza) for item in records] == [
        ("DEBITO AUT. FAT.CARTAO MASTER CARD FINAL 4202", Decimal("2320.83"), "Débito")
    ]


def test_santander_pdfplumber_layout_extracts_rows_dates_documents_and_totals():
    text = """EXTRATO CONSOLIDADO INTELIGENTE
Santander
janeiro/2024
Conta Corrente
Movimentação
Data Descrição Nº Documento Movimentos (R$) Créditos Débitos Saldo (R$)
SALDO EM 31/12 0,00
02/01 TARIFA MENSALIDADE PACOTE SERVICOS 106,50- 0,00
DEZEMBRO / 2023
02/01 TED RECEBIDA 2.300,00 2.300,00
TRANSFERENCIA ENTRE CONTA
03/01 PAGAMENTO CARTAO DE DEBITO 2898841.234,56 3.534,56
GETNET-VISA ELECTR
PAGAMENTO DE BOLETO OUTROS BANCOS 123456 1.000,00- 2.534,56
Pagina:2/10EXTRATO CONSOLIDADO INTELIGENTE
janeiro/2024
Data Descrição Nº Documento Movimentos (R$) Créditos Débitos Saldo (R$)
04/01 ANTECIPACAO GETNET 834435 43.690,17 46.224,73
PAGAMENTO DARF EM CANAIS 000015 46.011,73- 106,50
INTERNET DOCUMENTO DE ARR
31/01 IOF ADICIONAL - AUTOMATICO 106,50- 0,00
SALDO EM 31/01 0,00
Extrato_PJ_A4_Inteligente 1.0
"""

    records = extract_statement(text, 1, "Santander")

    assert [item.pagina_numero for item in records] == [1, 1, 1, 1, 2, 2, 2]
    assert records[0].historico == "TARIFA MENSALIDADE PACOTE SERVICOS DEZEMBRO / 2023"
    assert records[1].historico == "TED RECEBIDA TRANSFERENCIA ENTRE CONTA"
    assert records[3].data == date(2024, 1, 3)
    assert records[3].numero_documento == "123456"
    assert records[4].numero_documento == "834435"
    assert records[5].historico == "PAGAMENTO DARF EM CANAIS INTERNET DOCUMENTO DE ARR"
    assert records[5].valor == Decimal("46011.73")
    assert sum(item.valor for item in records if item.natureza == "Crédito") == Decimal("47224.73")
    assert sum(item.valor for item in records if item.natureza == "Débito") == Decimal("47224.73")


def test_santander_starts_new_movement_when_value_has_no_date_and_keeps_multiline_description():
    text = """EXTRATO CONSOLIDADO INTELIGENTE
Santander
janeiro/2024
Data Descrição Nº Documento Movimentos (R$) Créditos Débitos Saldo (R$)
04/01 PAGAMENTO CARTAO DE DEBITO 118,80 118,80
GETNET-ELO DEBITO
PAGAMENTO CARTAO DE DEBITO 257,27 376,07
GETNET-MAESTRO
"""

    records = extract_statement(text, 1, "Santander")

    assert [(item.data, item.historico, item.valor, item.natureza) for item in records] == [
        (date(2024, 1, 4), "PAGAMENTO CARTAO DE DEBITO GETNET-ELO DEBITO", Decimal("118.80"), "Crédito"),
        (date(2024, 1, 4), "PAGAMENTO CARTAO DE DEBITO GETNET-MAESTRO", Decimal("257.27"), "Crédito"),
    ]


def test_santander_inherits_current_date_across_pages():
    text = """EXTRATO CONSOLIDADO INTELIGENTE
Santander
janeiro/2024
Data Descrição Nº Documento Movimentos (R$) Créditos Débitos Saldo (R$)
04/01 PAGAMENTO CARTAO DE DEBITO 118,80 118,80
GETNET-ELO DEBITO
Pagina:2/10EXTRATO CONSOLIDADO INTELIGENTE
janeiro/2024
Data Descrição Nº Documento Movimentos (R$) Créditos Débitos Saldo (R$)
PAGAMENTO CARTAO DE DEBITO 257,27 376,07
GETNET-MAESTRO
05/01 TARIFA MENSALIDADE 106,50- 269,57
"""

    records = extract_statement(text, 1, "Santander")

    assert [(item.pagina_numero, item.data, item.historico, item.valor) for item in records] == [
        (1, date(2024, 1, 4), "PAGAMENTO CARTAO DE DEBITO GETNET-ELO DEBITO", Decimal("118.80")),
        (2, date(2024, 1, 4), "PAGAMENTO CARTAO DE DEBITO GETNET-MAESTRO", Decimal("257.27")),
        (2, date(2024, 1, 5), "TARIFA MENSALIDADE", Decimal("106.50")),
    ]


def test_santander_page_list_extracts_initial_column_page_and_keeps_date_between_pages():
    first_page = """Resumo - janeiro/2024
Movimentação
Data
Descrição
Nº Documento
SALDO EM 31/12
02/01
TARIFA MENSALIDADE PACOTE SERVICOS
DEZEMBRO / 2023
TED RECEBIDA
TRANSFERENCIA ENTRE CONTA
PAGAMENTO CARTAO DE DEBITO
GETNET-VISA ELECTR
PAGAMENTO CARTAO DE DEBITO
GETNET-ELO DEBITO
DEBITO AUT. FAT.CARTAO MASTER CARD
FINAL 4202
JUROS SALDO UTILIZ ATE LIMITE
PERIODO: 01/12 A 31/12/23
IOF IMPOSTO OPERACOES FINANCEIRAS
PERIODO: 01/12 A 31/12/23
IOF ADICIONAL - AUTOMATICO
PERIODO: 01/12 A 31/12/23
Movimentos (R$)
Créditos
Débitos
-
Saldo (R$)
0,00
106,50-
-2.300,00
289884217,80
289884257,40
-2.320,83-
-5,58-
-0,08-
-2,71-
"""
    second_page = """EXTRATO CONSOLIDADO INTELIGENTE
janeiro/2024
Data Descrição Nº Documento Movimentos (R$) Créditos Débitos Saldo (R$)
PAGAMENTO CARTAO DE DEBITO 118,80 118,80
GETNET-ELO DEBITO
"""

    records = extract_statement_pages([first_page, second_page], "Santander")

    assert len(records) == 9
    assert records[0].historico == "TARIFA MENSALIDADE PACOTE SERVICOS DEZEMBRO / 2023"
    assert records[1].historico == "TED RECEBIDA TRANSFERENCIA ENTRE CONTA"
    assert records[7].historico == "IOF ADICIONAL - AUTOMATICO PERIODO: 01/12 A 31/12/23"
    assert records[8].pagina_numero == 2
    assert records[8].data == date(2024, 1, 2)
    assert records[8].historico == "PAGAMENTO CARTAO DE DEBITO GETNET-ELO DEBITO"
    assert records[8].valor == Decimal("118.80")


def word(text: str, x0: float, top: float) -> dict[str, object]:
    return {"text": text, "x0": x0, "x1": x0 + max(8, len(text) * 4), "top": top, "bottom": top + 5}


def word_line(top: float, items: list[tuple[str, float]]) -> list[dict[str, object]]:
    words = []
    for text, x0 in items:
        cursor = x0
        for part in text.split():
            words.append(word(part, cursor, top))
            cursor += max(16, len(part) * 5)
    return words


def santander_header(top: float = 20) -> list[dict[str, object]]:
    return word_line(top, [
        ("Data", 20),
        ("Descrição", 80),
        ("Nº Documento", 320),
        ("Créditos", 430),
        ("Débitos", 520),
        ("Saldo", 610),
    ])


def santander_split_header(top: float = 20) -> list[dict[str, object]]:
    return [
        *word_line(top, [
            ("Data", 34),
            ("Descrição", 65),
            ("Nº Documento", 296),
            ("Movimentos (R$)", 387),
            ("Saldo (R$)", 508),
        ]),
        *word_line(top + 10, [
            ("Créditos", 384),
            ("Débitos", 435),
        ]),
    ]


def test_santander_words_ignore_summary_before_table_and_read_split_header():
    pages_words = [[
        *word_line(10, [("Resumo - janeiro/2024", 40)]),
        *word_line(20, [("Agência Conta Corrente", 40)]),
        *word_line(30, [("Saldo de Investimentos com Resgate Automático", 40), ("3.864,50", 508)]),
        *word_line(40, [("Conta Corrente", 40)]),
        *word_line(50, [("Movimentação", 40)]),
        *santander_split_header(60),
        *word_line(80, [("SALDO EM 31/12", 34), ("0,00", 508)]),
        *word_line(90, [("02/01", 34), ("IOF ADICIONAL - AUTOMATICO", 65), ("2,71-", 435)]),
        *word_line(100, [("PERIODO: 01/12 A 31/12/23", 65)]),
        *word_line(110, [("Extrato_PJ_A4_Inteligente 1.0", 65)]),
        *word_line(120, [("SALDO EM 31/01", 34), ("0,00", 508)]),
    ]]
    pages_text = ["EXTRATO CONSOLIDADO INTELIGENTE\nSantander\njaneiro/2024\nConta Corrente\nMovimentação\nMovimentos (R$)"]

    records = extract_santander_words_statement(pages_words, pages_text)

    assert [(item.data, item.historico, item.valor, item.natureza) for item in records] == [
        (date(2024, 1, 2), "IOF ADICIONAL AUTOMATICO PERIODO: 01/12 A 31/12/23", Decimal("2.71"), "Débito")
    ]


def test_santander_words_do_not_stop_on_previous_month_balance_for_february():
    pages_words = [[
        *word_line(10, [("Conta Corrente", 40)]),
        *word_line(20, [("Movimentação", 40)]),
        *santander_split_header(30),
        *word_line(50, [("SALDO EM 31/01", 34), ("0,00", 508)]),
        *word_line(60, [("PAGAMENTO CARTAO DE DEBITO", 65), ("289884", 296), ("415,80", 385)]),
        *word_line(70, [("ANTECIPACAO GETNET", 65), ("065118", 296), ("140,04", 385)]),
        *word_line(80, [("02/02", 34), ("PAGAMENTO CARTAO DE DEBITO", 65), ("289884", 296), ("39,60", 385)]),
        *word_line(90, [("SALDO EM 29/02", 34), ("0,00", 508)]),
        *word_line(100, [("TRANSFERENCIAS ENTRE CONTAS", 65), ("999,00", 385)]),
    ]]
    pages_text = ["EXTRATO CONSOLIDADO INTELIGENTE\nSantander\nfevereiro/2024\nConta Corrente\nMovimentação\nMovimentos (R$)"]

    records = extract_santander_words_statement(pages_words, pages_text)

    assert [(item.data, item.historico, item.valor, item.natureza, item.numero_documento) for item in records] == [
        (date(2024, 2, 1), "PAGAMENTO CARTAO DE DEBITO", Decimal("415.80"), "Crédito", "289884"),
        (date(2024, 2, 1), "ANTECIPACAO GETNET", Decimal("140.04"), "Crédito", "065118"),
        (date(2024, 2, 2), "PAGAMENTO CARTAO DE DEBITO", Decimal("39.60"), "Crédito", "289884"),
    ]


def test_santander_words_keep_first_description_word_with_float_coordinate_noise():
    pages_words = [[
        *word_line(10, [("Conta Corrente", 40)]),
        *word_line(20, [("Movimentação", 40)]),
        *santander_split_header(30),
        word("04/01", 34, 50),
        word("PAGAMENTO", 65.2, 50),
        word("CARTAO", 109.15, 50),
        word("DE", 138.48, 50),
        word("DEBITO", 149.53, 50),
        word("289884", 307.94, 50),
        word("118,80", 385.24, 50),
        word("GETNET-ELO", 65.2, 60),
        word("DEBITO", 109.15, 60),
        word("PAGAMENTO", 65.19999999999999, 70),
        word("CARTAO", 109.15, 70),
        word("DE", 138.48, 70),
        word("DEBITO", 149.53, 70),
        word("289884", 307.94, 70),
        word("257,27", 385.24, 70),
        word("GETNET-MAESTRO", 65.19999999999999, 80),
    ]]
    pages_text = ["EXTRATO CONSOLIDADO INTELIGENTE\nSantander\njaneiro/2024\nConta Corrente\nMovimentação\nMovimentos (R$)"]

    records = extract_santander_words_statement(pages_words, pages_text)

    assert [(item.historico, item.valor, item.numero_documento) for item in records] == [
        ("PAGAMENTO CARTAO DE DEBITO GETNET-ELO DEBITO", Decimal("118.80"), "289884"),
        ("PAGAMENTO CARTAO DE DEBITO GETNET-MAESTRO", Decimal("257.27"), "289884"),
    ]


def test_santander_words_remove_repeated_trailing_description_phrase():
    pages_words = [[
        *word_line(10, [("Conta Corrente", 40)]),
        *word_line(20, [("Movimentação", 40)]),
        *santander_split_header(30),
        *word_line(50, [("02/01", 34), ("TARIFA MENSALIDADE PACOTE SERVICOS DEZEMBRO / 2023", 65), ("106,50-", 435)]),
        *word_line(60, [("MENSALIDADE PACOTE SERVICOS DEZEMBRO / 2023", 65)]),
    ]]
    pages_text = ["EXTRATO CONSOLIDADO INTELIGENTE\nSantander\njaneiro/2024\nConta Corrente\nMovimentação\nMovimentos (R$)"]

    records = extract_santander_words_statement(pages_words, pages_text)

    assert len(records) == 1
    assert records[0].historico == "TARIFA MENSALIDADE PACOTE SERVICOS DEZEMBRO / 2023"
    assert records[0].nome == ""
    assert records[0].valor == Decimal("106.50")
    assert records[0].natureza == "Débito"


def test_santander_statement_name_does_not_repeat_tokens_from_history():
    pages_words = [[
        *word_line(10, [("Conta Corrente", 40)]),
        *word_line(20, [("Movimentação", 40)]),
        *santander_split_header(30),
        *word_line(50, [("02/01", 34), ("DEBITO AUT. FAT.CARTAO MASTER CARD FINAL 4202", 65), ("2.320,83-", 435)]),
    ]]
    pages_text = ["EXTRATO CONSOLIDADO INTELIGENTE\nSantander\njaneiro/2024\nConta Corrente\nMovimentação\nMovimentos (R$)"]

    records = extract_santander_words_statement(pages_words, pages_text)

    assert len(records) == 1
    assert records[0].historico == "DEBITO AUT. FAT.CARTAO MASTER CARD FINAL 4202"
    assert records[0].nome == ""


def test_santander_words_use_columns_not_description_words_for_nature_and_ignore_informational_sections():
    pages_words = [
        [
            *word_line(10, [("Conta Corrente", 40), ("Movimentação", 160)]),
            *santander_header(),
            *word_line(40, [("22/01", 20), ("PAGAMENTO CARTAO DE DEBITO", 80), ("574,20", 430), ("574,20", 610)]),
            *word_line(50, [("GETNET-MAESTRO", 80)]),
            *word_line(60, [("PAGAMENTO DE BOLETO OUTROS BANCOS", 80), ("123456", 320), ("100,00-", 520), ("474,20", 610)]),
            *word_line(70, [("GETNET-MAESTRO", 80)]),
            *word_line(80, [("GETNET-MAESTRO", 80)]),
            *word_line(90, [("SALDO EM 31/01", 20), ("0,00", 610)]),
        ],
        [
            *word_line(10, [("Transferências entre Contas, DOCs, TEDs e PIXs Enviados", 40)]),
            *santander_header(),
            *word_line(30, [("25/01", 20), ("TED", 80), ("RENATA FIGUEIRO", 140), ("0577", 320), ("6.000,00", 430)]),
        ],
    ]
    pages_text = ["Santander\njaneiro/2024\nConta Corrente\nMovimentação", "Transferências entre Contas, DOCs, TEDs e PIXs Enviados"]

    records = extract_santander_words_statement(pages_words, pages_text)

    assert [(item.data, item.historico, item.valor, item.natureza, item.numero_documento) for item in records] == [
        (date(2024, 1, 22), "PAGAMENTO CARTAO DE DEBITO GETNET-MAESTRO", Decimal("574.20"), "Crédito", ""),
        (date(2024, 1, 22), "PAGAMENTO DE BOLETO OUTROS BANCOS GETNET-MAESTRO", Decimal("100.00"), "Débito", "123456"),
    ]


def test_santander_words_keep_current_date_across_pdf_pages():
    pages_words = [
        [
            *word_line(10, [("Conta Corrente", 40), ("Movimentação", 160)]),
            *santander_header(),
            *word_line(40, [("02/01", 20), ("TED RECEBIDA", 80), ("2.300,00", 430), ("2.300,00", 610)]),
        ],
        [
            *santander_header(),
            *word_line(30, [("APLICACAO CONTAMAX", 80), ("339,50-", 520), ("1.960,50", 610)]),
            *word_line(40, [("03/01", 20), ("ANTECIPACAO GETNET", 80), ("205,21", 430), ("2.165,71", 610)]),
        ],
        [
            *santander_header(),
            *word_line(30, [("17/01", 20), ("TED ENVIADA", 80), ("400,52-", 520), ("1.765,19", 610)]),
        ],
        [
            *santander_header(),
            *word_line(30, [("ANTECIPACAO GETNET", 80), ("114,44", 430), ("1.879,63", 610)]),
            *word_line(40, [("APLICACAO CONTAMAX", 80), ("1.163,75-", 520), ("715,88", 610)]),
        ],
    ]
    pages_text = ["Santander\njaneiro/2024\nConta Corrente\nMovimentação"] * 4

    records = extract_santander_words_statement(pages_words, pages_text)

    assert [(item.pagina_numero, item.data, item.historico, item.valor, item.natureza) for item in records] == [
        (1, date(2024, 1, 2), "TED RECEBIDA", Decimal("2300.00"), "Crédito"),
        (2, date(2024, 1, 2), "APLICACAO CONTAMAX", Decimal("339.50"), "Débito"),
        (2, date(2024, 1, 3), "ANTECIPACAO GETNET", Decimal("205.21"), "Crédito"),
        (3, date(2024, 1, 17), "TED ENVIADA", Decimal("400.52"), "Débito"),
        (4, date(2024, 1, 17), "ANTECIPACAO GETNET", Decimal("114.44"), "Crédito"),
        (4, date(2024, 1, 17), "APLICACAO CONTAMAX", Decimal("1163.75"), "Débito"),
    ]


def test_santander_expected_file_validation_fails_when_count_or_totals_do_not_match():
    records = [
        ParsedStatement(date(2024, 1, 2), None, "TED RECEBIDA", "", Decimal("2300.00"), "Crédito", "", 1),
    ]

    with pytest.raises(ValueError, match="Falha de validação do extrato Santander"):
        _validate_santander_expected_statement(records, ["janeiro/2024\nTotal de Créditos 47.224,73\nSaldo de Conta Corrente em 31/12 0,00\nSaldo de Conta Corrente em 31/01 0,00"])


def test_santander_summary_validation_fails_for_any_month_when_totals_do_not_match():
    records: list[ParsedStatement] = []

    with pytest.raises(ValueError, match=r"créditos 0 != 42820.93"):
        _validate_santander_expected_statement(records, ["fevereiro/2024\nTotal de Créditos 42.820,93\nTotal de Débitos 42.820,93"])


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


def test_banco_do_brasil_keeps_ted_codes_and_full_counterparty_text():
    text = """01/01/2024
0000
438 TED
033 2478 008695575000188 CENTRO ODONTO
1.000,00 D
"""

    record = extract_statement(text, 1, "Banco do Brasil")[0]

    assert record.historico == "438 TED 033 2478 008695575000188 CENTRO ODONTO"
    assert record.nome == ""
    assert f"{record.historico} {record.nome}".strip() == "438 TED 033 2478 008695575000188 CENTRO ODONTO"


def test_banco_do_brasil_keeps_contract_operation_number_for_safe_rules():
    text = """15/01/2024
0000
13128 500 Cap Giro Dig Amortização
57.709.569.000.109
2.817,00 D
"""

    record = extract_statement(text, 1, "Banco do Brasil")[0]

    assert record.historico == "13128 500 Cap Giro Dig Amortização 57.709.569.000.109"
    assert record.numero_documento == "57.709.569.000.109"
    assert record.valor == Decimal("2817.00")
    assert record.natureza == "Débito"


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


def test_banco_do_brasil_receipt_keeps_document_number():
    text = """DOCUMENTO: 13.101
BENEFICIARIO FINAL:
QUANTITY SERVICOS E COMERCIO DE PRO
DATA DO PAGAMENTO                     02/01/2024
VALOR DO DOCUMENTO                    680,49
"""

    record = extract_receipts(text, 1)[0]

    assert record.numero_documento == "13.101"


def test_banco_do_brasil_payment_receipt_reads_charged_value_without_document_value():
    text = """COMPROVANTE DE PAGAMENTO DE TITULOS
BENEFICIARIO:
FORNECEDOR TESTE LTDA
CNPJ: 11.111.111/0001-11
BENEFICIARIO FINAL:
CLIENTE FINAL TESTE
CNPJ: 22.222.222/0001-22
DATA DO PAGAMENTO                     30/01/2024
VALOR COBRADO                           497,00
"""

    record = extract_receipts(text, 1)[0]

    assert record.favorecido == "FORNECEDOR TESTE LTDA"
    assert record.beneficiario_final == "CLIENTE FINAL TESTE"
    assert record.cnpj_beneficiario == "11.111.111/0001-11"
    assert record.cnpj_beneficiario_final == "22.222.222/0001-22"
    assert record.valor == Decimal("497.00")


def test_banco_do_brasil_payment_receipt_reads_values_on_next_lines():
    text = """22/02/2024
COMPROVANTE DE PAGAMENTO DE TITULOS
BENEFICIARIO:
BAMBUNO TECNOLOGIA LTDA
NOME FANTASIA:
BAMBUNO TECNOLOGIA - EIRELI
CNPJ: 27.012.243/0001-04
BENEFICIARIO FINAL:
SUCESSODONTO CURSOS E TREINAMENTOS
CNPJ: 24.416.738/0001-00
PAGADOR:
Renata kamile de Sousa FigueirO
NR. DOCUMENTO
13.002
DATA DE VENCIMENTO
31/01/2024
DATA DO PAGAMENTO
30/01/2024
VALOR DO DOCUMENTO
1.000,00
VALOR COBRADO
1.000,00
"""

    record = extract_receipts(text, 1)[0]

    assert record.data == date(2024, 1, 30)
    assert record.favorecido == "BAMBUNO TECNOLOGIA LTDA"
    assert record.nome_fantasia == "BAMBUNO TECNOLOGIA - EIRELI"
    assert record.cnpj_beneficiario == "27.012.243/0001-04"
    assert record.beneficiario_final == "SUCESSODONTO CURSOS E TREINAMENTOS"
    assert record.cnpj_beneficiario_final == "24.416.738/0001-00"
    assert record.pagador == "Renata kamile de Sousa FigueirO"
    assert record.numero_documento == "13.002"
    assert record.valor == Decimal("1000.00")


def test_receipt_document_number_matches_the_banco_do_brasil_statement_history():
    receipt = Comprovante(numero_documento="13.101", beneficiario="Outro favorecido")

    assert receipt_match_criterion("Pagamento de Boleto 13.101", receipt) == "número do documento"


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


def test_banco_do_brasil_transfer_receipt_reads_transferred_name_label():
    text = """DATA TRANSFERENCIA                    16/01/2024
VALOR TRANSFERIDO                    6.000,00
TRANSFERIDO PARA:
NOME: LEANDRO BARBOSA FIGUEIRO
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


def test_caixa_statement_extracts_movements_and_skips_daily_balances():
    text = """01/02/2024, 08:10
Ge:renCia:dor CAiXA
https://gerenciador.caixa.gov.br/SIIBC/imprime_ext_periodo.processa?hdnDataInicio=01/01/2024&hdnDataFinal=31/01/2024
Extrato por período
02/01/2024
291156
ENVIO TEV
1.000,00 D
1.000,00 D
02/01/2024
727220
RESG AUTOM
1.000,00 C
0,00 C
02/01/2024
000000
SALDO DIA
0,00 C
"""
    records = extract_statement(text, 1, "Caixa")
    assert [(item.numero_documento, item.historico, item.valor, item.natureza) for item in records] == [
        ("291156", "ENVIO TEV", Decimal("1000.00"), "Débito"),
        ("727220", "RESG AUTOM", Decimal("1000.00"), "Crédito"),
    ]
    assert [item.nome for item in records] == ["", ""]


def test_bradesco_statement_inherits_date_between_pages_and_skips_previous_balance():
    first_page = """Extrato Mensal / Por Período
01/01/2024 31/01/2024
Data
Lançamento
Dcto.
Crédito (R$)
Débito (R$)
Saldo (R$)
29/12/2023
SALDO ANTERIOR
25.151,62
02/01/2024
CARTAO VISA ELECTRON
CIELO S.A - INSTITUICAO DE PAG
3723000
672,74
25.824,36
"""
    second_page = """Extrato Mensal / Por Período
PAGTO ELETRON COBRANCA
DISTR DE MEDI SANTA CRUZ LTDA
4518
-3.034,57
1.958,09
"""
    records = extract_statement_pages([first_page, second_page], "Bradesco")
    assert [(item.data, item.historico, item.valor, item.natureza, item.pagina_numero) for item in records] == [
        (date(2024, 1, 2), "CARTAO VISA ELECTRON CIELO S.A - INSTITUICAO DE PAG", Decimal("672.74"), "Crédito", 1),
        (date(2024, 1, 2), "PAGTO ELETRON COBRANCA DISTR DE MEDI SANTA CRUZ LTDA", Decimal("3034.57"), "Débito", 2),
    ]


def test_caixa_boleto_receipt_extracts_fields_from_two_page_text():
    text = """2ª Via - Comprovante de Pagamento de Boleto
Via Internet Banking CAIXA
Beneficiário original / Cedente
Nome Fantasia:
MAPEMI BRASIL MATERIAIS MEDICOS E ODONTO
Nome/Razão Social:
MAPEMI BRASIL MATERIAIS MEDICOS E ODONTO
CPF/CNPJ:
84.487.131/0001-35
Valor Nominal do Boleto:
1.710,87
Valor Pago (R$):
1.710,87
Data/hora da operação:
25/01/2024 10:35:36
Código da operação:
025084072
"""
    record = extract_receipts(text, 1)[0]
    assert record.data == date(2024, 1, 25)
    assert record.hora == "10:35:36"
    assert record.favorecido == "MAPEMI BRASIL MATERIAIS MEDICOS E ODONTO"
    assert record.cnpj_beneficiario == "84.487.131/0001-35"
    assert record.numero_documento == "025084072"
    assert record.valor == Decimal("1710.87")


def test_bradesco_boleto_receipt_extracts_reversed_label_layout():
    text = """PGTO BOLETO STA CRUZ
Descrição:
R$ 105,17
Valor total:
R$ 104,65
Valor
11/01/2024
Data de débito:
061.940.292/0001-37
CPF/CNPJ Beneficiário:
DISTR DE MEDI SANTA CRUZ LTDA
Nome Fantasia
Beneficiário:
DISTR DE MEDI SANTA CRUZ LTDA
Razão Social
Beneficiário:
Comprovante de Transação Bancária
Boleto de Cobrança
Data da operação: 11/01/2024
0004519
Documento:
"""
    record = extract_receipts(text, 1)[0]
    assert record.data == date(2024, 1, 11)
    assert record.favorecido == "DISTR DE MEDI SANTA CRUZ LTDA"
    assert record.cnpj_beneficiario == "061.940.292/0001-37"
    assert record.numero_documento == "0004519"
    assert record.valor == Decimal("105.17")
    assert record.financeiros.valor_original == Decimal("104.65")
