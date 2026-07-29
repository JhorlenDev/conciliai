from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class RuleLine:
    componente: str
    valor: Decimal
    codigo_receita: str = ""
    descricao: str = ""
    efeito_no_total: str = "SOMA"
    origem: str = ""


@dataclass
class RuleDecision:
    status: str
    fonte_regra: str | None
    exige_revisao: bool
    linhas: list[RuleLine] = field(default_factory=list)
    diferenca: Decimal = Decimal("0.00")


def choose_rule_source(extrato_valor: Decimal | None, receipt=None, rfb=None, tariff: bool = False) -> RuleDecision:
    if extrato_valor is None:
        return RuleDecision("Documento sem movimento no extrato", None, True)
    has_receipt = bool(receipt)
    if tariff and has_receipt:
        return RuleDecision("Conciliado bancário", "comprovante bancário", False, [RuleLine("TARIFA", extrato_valor, origem="comprovante")])
    if rfb is not None and has_receipt:
        decision = RuleDecision("Conciliado completo", "RFB", False, _rfb_lines(rfb))
    elif rfb is not None:
        decision = RuleDecision("Extrato + RFB", "RFB", True, _rfb_lines(rfb))
    elif has_receipt:
        lines = _receipt_lines(receipt) if not isinstance(receipt, bool) else []
        return RuleDecision("Conciliado bancário", "comprovante bancário", False, lines)
    else:
        return RuleDecision("Somente extrato", "extrato", True)
    total = sum((line.valor if line.efeito_no_total == "SOMA" else -line.valor for line in decision.linhas), Decimal("0.00"))
    decision.diferenca = extrato_valor - total
    if abs(decision.diferenca) > Decimal("0.01"):
        decision.status = "Lançamentos não fecham com o extrato"
        decision.exige_revisao = True
    return decision


def _rfb_lines(rfb) -> list[RuleLine]:
    items = getattr(rfb, "itens", [])
    is_simples = getattr(rfb, "tipo", "").upper() == "DAS" or any("SIMPLES NACIONAL" in (item.descricao or "").upper() for item in items)
    if is_simples:
        principal = rfb.valor_principal or sum((item.valor_principal or Decimal("0.00") for item in items), Decimal("0.00"))
        multa = rfb.valor_multa or sum((item.valor_multa or Decimal("0.00") for item in items), Decimal("0.00"))
        juros = rfb.valor_juros or sum((item.valor_juros or Decimal("0.00") for item in items), Decimal("0.00"))
        total = getattr(rfb, "valor_total", None) or principal + multa + juros
        return [RuleLine("SIMPLES_NACIONAL", total, descricao="SIMPLES NACIONAL", origem="rfb")] if total > 0 else []
    if getattr(rfb, "tipo", "").upper() == "DARF":
        items = getattr(rfb, "itens", [])
        irrf_items = [item for item in items if item.codigo.lstrip("0") in {"156", "561"}]
        irrf = sum((item.valor_principal or Decimal("0.00") for item in irrf_items), Decimal("0.00"))
        inss = sum((item.valor_principal or Decimal("0.00") for item in items if item not in irrf_items), Decimal("0.00"))
        lines = []
        if irrf > 0:
            lines.append(RuleLine("IRRF", irrf, irrf_items[0].codigo, "IRRF", origem="rfb"))
        if inss > 0:
            lines.append(RuleLine("INSS", inss, descricao="INSS", origem="rfb"))
        multa = rfb.valor_multa or sum((item.valor_multa or Decimal("0.00") for item in items), Decimal("0.00"))
        juros = rfb.valor_juros or sum((item.valor_juros or Decimal("0.00") for item in items), Decimal("0.00"))
        for component, value in (("MULTA", multa), ("JUROS", juros)):
            if value and value > 0:
                lines.append(RuleLine(component, value, descricao=component, origem="rfb"))
        return lines
    lines = []
    for item in items:
        for component, value in (("principal", item.valor_principal), ("multa", item.valor_multa), ("juros", item.valor_juros)):
            if value and value > 0:
                label = item.descricao if component == "principal" else component
                lines.append(RuleLine(label.upper(), value, item.codigo, item.descricao, origem="rfb"))
    if lines:
        return lines
    for component, value in (("principal", rfb.valor_principal), ("multa", rfb.valor_multa), ("juros", rfb.valor_juros)):
        if value and value > 0:
            lines.append(RuleLine(component.upper(), value, origem="rfb"))
    return lines


def _receipt_lines(receipt) -> list[RuleLine]:
    values = getattr(receipt, "financeiros", receipt)
    additions = (("JUROS", values.valor_juros), ("MULTA", values.valor_multa), ("ENCARGOS", values.valor_encargos))
    reductions = (("DESCONTO", values.valor_desconto), ("ABATIMENTO", values.valor_abatimento), ("DESCONTO_ABATIMENTO", values.valor_desconto_abatimento))
    has_reductions = any(value and value > 0 for _, value in reductions)
    additions_total = sum((value or Decimal("0.00") for _, value in additions), Decimal("0.00"))
    principal = (values.valor_pago or Decimal("0.00")) - additions_total if has_reductions else values.valor_original or values.valor_pago
    lines = [RuleLine("VALOR_COBRADO", principal, origem="comprovante")] if principal and principal > 0 else []
    lines.extend(RuleLine(component, value, origem="comprovante") for component, value in reductions if value and value > 0)
    lines.extend(RuleLine(component, value, origem="comprovante") for component, value in additions if value and value > 0)
    return lines
