from datetime import date
from decimal import Decimal

from app.services.rfb import belongs_to_selected_bank, parse_rfb_page


def rfb_page(kind="DAS", bank="001 - BANCO DO BRASIL S A", total="1.039,13", multa="54,68", juros="9,74", principal="974,71"):
    return f"""Data de Vencimento
08.695.575/0001-88 CENTRO ODONTOLOGICO FIGUEIRO LTDA
12/2023
22/01/2024
07202400681734283
CNPJ
Competência
Comprovamos que consta nos sistemas da Receita Federal registro de arrecadação de {kind} com os dados a seguir:
Razão Social
Número do Documento
Comprovante de Arrecadação
Totais
{principal}
{multa}
{juros}
{total}
Referência
22/01/2024
{bank}
0577
"""


def test_each_rfb_page_creates_one_das_with_collection_date_and_total():
    record = parse_rfb_page(rfb_page(), 1)
    assert record and record.tipo == "DAS"
    assert record.data_arrecadacao == date(2024, 1, 22)
    assert record.data_vencimento == date(2024, 1, 22)
    assert record.valor_total == Decimal("1039.13")
    assert record.valor_principal + record.valor_multa + record.valor_juros == record.valor_total


def test_darf_and_bank_filtering_keep_other_banks_for_review():
    darf = parse_rfb_page(rfb_page(kind="DARF", bank="033 - BANCO SANTANDER MERIDIONAL S/A"), 1)
    assert darf and darf.tipo == "DARF"
    assert not belongs_to_selected_bank(darf, "Banco do Brasil")
    assert belongs_to_selected_bank(parse_rfb_page(rfb_page(), 1), "Banco do Brasil")


def test_divergent_composition_is_preserved_and_marked():
    record = parse_rfb_page(rfb_page(total="1.040,00"), 1)
    assert record and record.composicao_divergente
    assert record.valor_total == Decimal("1040.00")


def test_darf_item_columns_keep_fine_separate_from_zero_interest():
    text = """Comprovamos que consta nos sistemas da Receita Federal registro de arrecadação de DARF com os dados a seguir:
Comprovante de Arrecadação
1082
CONTRIBUIÇÃO PREVIDENCIÁRIA
483,29
1,59
-
484,88
Totais
483,29
1,59
0,00
484,88
"""

    record = parse_rfb_page(text, 1)

    assert record is not None
    assert [(item.valor_principal, item.valor_multa, item.valor_juros, item.valor_total) for item in record.itens] == [(Decimal("483.29"), Decimal("1.59"), None, Decimal("484.88"))]
