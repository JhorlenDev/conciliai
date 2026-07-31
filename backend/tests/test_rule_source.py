from decimal import Decimal
from types import SimpleNamespace

from app.services.rule_source import choose_rule_source
from app.services.parsers import FinancialValues


def test_rfb_has_priority_and_generates_one_composed_financial_total():
    rfb = SimpleNamespace(valor_principal=Decimal("974.71"), valor_multa=Decimal("54.68"), valor_juros=Decimal("9.74"), itens=[])
    result = choose_rule_source(Decimal("1039.13"), True, rfb)
    assert result.status == "Conciliado completo"
    assert result.fonte_regra == "RFB"
    assert sum(line.valor for line in result.linhas) == Decimal("1039.13")


def test_bank_receipt_is_used_when_rfb_does_not_exist():
    result = choose_rule_source(Decimal("520.52"), True)
    assert result.status == "Conciliado bancário"
    assert result.fonte_regra == "comprovante bancário"


def test_rfb_without_bank_receipt_requires_manual_confirmation():
    rfb = SimpleNamespace(valor_principal=Decimal("100.00"), valor_multa=Decimal("0"), valor_juros=Decimal("0"), itens=[])
    assert choose_rule_source(Decimal("100.00"), False, rfb).exige_revisao


def test_unbalanced_rfb_never_concludes_automatically():
    rfb = SimpleNamespace(valor_principal=Decimal("100.00"), valor_multa=Decimal("0"), valor_juros=Decimal("0"), itens=[])
    result = choose_rule_source(Decimal("110.00"), True, rfb)
    assert result.status == "Lançamentos não fecham com o extrato"
    assert result.exige_revisao


def test_receipt_discount_creates_principal_and_discount_items():
    receipt = SimpleNamespace(financeiros=FinancialValues(valor_original=Decimal("547.93"), valor_desconto=Decimal("54.79"), valor_pago=Decimal("493.14")))
    result = choose_rule_source(Decimal("493.14"), receipt)

    assert [(line.componente, line.valor, line.efeito_no_total) for line in result.linhas] == [("VALOR_COBRADO", Decimal("493.14"), "SOMA"), ("DESCONTO", Decimal("54.79"), "OUTROS")]
    assert not result.exige_revisao


def test_rfb_multiple_taxes_keep_each_tax_item():
    irrf = SimpleNamespace(codigo="0561", descricao="IRRF", valor_principal=Decimal("974.71"), valor_multa=Decimal("0"), valor_juros=Decimal("0"))
    inss = SimpleNamespace(codigo="2100", descricao="INSS", valor_principal=Decimal("1638.39"), valor_multa=Decimal("0"), valor_juros=Decimal("0"))
    rfb = SimpleNamespace(valor_principal=None, valor_multa=None, valor_juros=None, itens=[irrf, inss])
    result = choose_rule_source(Decimal("2613.10"), True, rfb)

    assert [(line.codigo_receita, line.descricao, line.valor) for line in result.linhas] == [("0561", "IRRF", Decimal("974.71")), ("2100", "INSS", Decimal("1638.39"))]
    assert [line.componente for line in result.linhas] == ["IRRF", "INSS"]


def test_das_consolidates_internal_taxes_into_one_tax_entry():
    irpj = SimpleNamespace(codigo="1001", descricao="IRPJ - SIMPLES NACIONAL", valor_principal=Decimal("256.91"), valor_multa=Decimal("0"), valor_juros=Decimal("0"))
    inss = SimpleNamespace(codigo="1006", descricao="INSS - SIMPLES NACIONAL", valor_principal=Decimal("2787.45"), valor_multa=Decimal("0"), valor_juros=Decimal("0"))
    rfb = SimpleNamespace(tipo="DAS", valor_principal=Decimal("3044.36"), valor_multa=Decimal("0"), valor_juros=Decimal("0"), itens=[irpj, inss])

    result = choose_rule_source(Decimal("3044.36"), True, rfb)

    assert [(line.componente, line.descricao, line.valor) for line in result.linhas] == [("SIMPLES_NACIONAL", "SIMPLES NACIONAL", Decimal("3044.36"))]


def test_simples_nacional_with_inss_code_remains_one_entry_at_total_paid():
    irpj = SimpleNamespace(codigo="1001", descricao="IRPJ - SIMPLES NACIONAL", valor_principal=Decimal("256.91"), valor_multa=Decimal("0"), valor_juros=Decimal("0"))
    inss = SimpleNamespace(codigo="1006", descricao="INSS - SIMPLES NACIONAL", valor_principal=Decimal("2787.45"), valor_multa=Decimal("0"), valor_juros=Decimal("0"))
    rfb = SimpleNamespace(tipo="DAS", valor_principal=Decimal("3044.36"), valor_multa=Decimal("25.00"), valor_juros=Decimal("12.50"), valor_total=Decimal("3081.86"), itens=[irpj, inss])

    result = choose_rule_source(Decimal("3081.86"), True, rfb)

    assert [(line.componente, line.valor) for line in result.linhas] == [("SIMPLES_NACIONAL", Decimal("3081.86"))]


def test_darf_consolidates_irrf_and_remaining_codes_as_inss_with_penalties():
    irrf = SimpleNamespace(codigo="0561", descricao="IRRF", valor_principal=Decimal("974.71"), valor_multa=Decimal("0"), valor_juros=Decimal("0"))
    contributor = SimpleNamespace(codigo="1082", descricao="CONTRIBUIÇÃO PREVIDENCIÁRIA", valor_principal=Decimal("405.51"), valor_multa=Decimal("0"), valor_juros=Decimal("0"))
    individual = SimpleNamespace(codigo="1099", descricao="CONTRIBUIÇÃO INDIVIDUAL", valor_principal=Decimal("1232.88"), valor_multa=Decimal("0"), valor_juros=Decimal("0"))
    rfb = SimpleNamespace(tipo="DARF", valor_principal=Decimal("2613.10"), valor_multa=Decimal("25.00"), valor_juros=Decimal("12.50"), itens=[irrf, contributor, individual])

    result = choose_rule_source(Decimal("2650.60"), True, rfb)

    assert [(line.componente, line.valor) for line in result.linhas] == [("IRRF", Decimal("974.71")), ("INSS", Decimal("1638.39")), ("MULTA", Decimal("25.00")), ("JUROS", Decimal("12.50"))]
    assert not result.exige_revisao


def test_receipt_interest_and_fine_create_separate_components():
    receipt = SimpleNamespace(financeiros=FinancialValues(valor_original=Decimal("100.00"), valor_juros=Decimal("2.00"), valor_multa=Decimal("3.00"), valor_pago=Decimal("105.00")))

    result = choose_rule_source(Decimal("105.00"), receipt)

    assert [(line.componente, line.valor) for line in result.linhas] == [("VALOR_COBRADO", Decimal("100.00")), ("JUROS", Decimal("2.00")), ("MULTA", Decimal("3.00"))]
