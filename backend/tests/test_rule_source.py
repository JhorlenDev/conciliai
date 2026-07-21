from decimal import Decimal
from types import SimpleNamespace

from app.services.rule_source import choose_rule_source


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
