from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class RuleLine:
    componente: str
    valor: Decimal
    codigo_receita: str = ""
    descricao: str = ""


@dataclass
class RuleDecision:
    status: str
    fonte_regra: str | None
    exige_revisao: bool
    linhas: list[RuleLine] = field(default_factory=list)
    diferenca: Decimal = Decimal("0.00")


def choose_rule_source(extrato_valor: Decimal | None, has_comprovante: bool, rfb=None) -> RuleDecision:
    if extrato_valor is None:
        return RuleDecision("Documento sem movimento no extrato", None, True)
    if rfb is not None and has_comprovante:
        decision = RuleDecision("Conciliado completo", "RFB", False, _rfb_lines(rfb))
    elif rfb is not None:
        decision = RuleDecision("Extrato + RFB", "RFB", True, _rfb_lines(rfb))
    elif has_comprovante:
        return RuleDecision("Conciliado bancário", "comprovante bancário", False)
    else:
        return RuleDecision("Somente extrato", "extrato", True)
    total = sum((line.valor for line in decision.linhas), Decimal("0.00"))
    decision.diferenca = extrato_valor - total
    if abs(decision.diferenca) > Decimal("0.01"):
        decision.status = "Lançamentos não fecham com o extrato"
        decision.exige_revisao = True
    return decision


def _rfb_lines(rfb) -> list[RuleLine]:
    lines = []
    for item in getattr(rfb, "itens", []):
        for component, value in (("principal", item.valor_principal), ("multa", item.valor_multa), ("juros", item.valor_juros)):
            if value and value > 0:
                lines.append(RuleLine(component, value, item.codigo, item.descricao))
    if lines:
        return lines
    for component, value in (("principal", rfb.valor_principal), ("multa", rfb.valor_multa), ("juros", rfb.valor_juros)):
        if value and value > 0:
            lines.append(RuleLine(component, value))
    return lines
