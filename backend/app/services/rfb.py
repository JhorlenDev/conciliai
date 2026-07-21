import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.services.parsers import parse_brl, parse_date_time
from app.services.normalization import normalize_name


@dataclass
class ParsedRfbItem:
    codigo: str
    descricao: str
    valor_principal: Decimal | None
    valor_multa: Decimal | None
    valor_juros: Decimal | None
    valor_total: Decimal | None


@dataclass
class ParsedRfb:
    tipo: str
    cnpj: str
    razao_social: str
    competencia: str
    periodo_apuracao: str
    data_vencimento: date | None
    data_arrecadacao: date | None
    numero_documento: str
    codigo_banco: str
    nome_banco: str
    agencia: str
    valor_principal: Decimal | None
    valor_multa: Decimal | None
    valor_juros: Decimal | None
    valor_total: Decimal | None
    texto_original: str
    pagina_numero: int
    composicao_divergente: bool
    itens: list[ParsedRfbItem] = field(default_factory=list)


def parse_rfb_page(text: str, page_number: int) -> ParsedRfb | None:
    type_match = re.search(r"registro de arrecadação de (DARF|DAS)", text, re.I)
    if not type_match:
        return None
    tipo = type_match.group(1).upper()
    cnpj_match = re.search(r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\s+([^\n]+)", text)
    cnpj, razao = cnpj_match.groups() if cnpj_match else ("", "")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    cnpj_index = next((index for index, line in enumerate(lines) if line == "CNPJ"), -1)
    values = lines[cnpj_index - 3:cnpj_index] if cnpj_index >= 3 else []
    period = values[0] if len(values) == 3 else ""
    due_date, _ = parse_date_time(values[1]) if len(values) == 3 else (None, None)
    document = values[2] if len(values) == 3 else ""
    totals = re.search(r"Totais\s*\n\s*([\d.,-]+)\s*\n\s*([\d.,-]+)\s*\n\s*([\d.,-]+)\s*\n\s*([\d.,-]+)", text, re.I)
    principal, multa, juros, total = (map(parse_brl, totals.groups()) if totals else (None, None, None, None))
    items = []
    composition = text.split("Totais", 1)[0]
    item_pattern = re.compile(r"(?m)^(\d{4})\s*\n([^\n]+)\n([\d.,-]+)\n([\d.,-]+)\n([\d.,-]+)\n([\d.,-]+)")
    for match in item_pattern.finditer(composition):
        code, description, item_total, item_juros, item_multa, item_principal = match.groups()
        items.append(ParsedRfbItem(code, description.strip(), parse_brl(item_principal), parse_brl(item_multa), parse_brl(item_juros), parse_brl(item_total)))
    bank = re.search(r"Referência\s*\n\s*(\d{2}/\d{2}/\d{4})\s*\n\s*(\d{3})\s*-\s*([^\n]+)\s*\n\s*(\d+)", text, re.I)
    collected_date, bank_code, bank_name, agency = (None, "", "", "")
    if bank:
        collected_date, _ = parse_date_time(bank.group(1)); bank_code, bank_name, agency = bank.group(2), bank.group(3).strip(), bank.group(4)
    divergent = bool(total is not None and principal is not None and abs((principal or Decimal()) + (multa or Decimal()) + (juros or Decimal()) - total) > Decimal("0.01"))
    return ParsedRfb(tipo, cnpj, razao, "" if "Período Apuração" in text else period, period if "Período Apuração" in text else "", due_date, collected_date, document, bank_code, bank_name, agency, principal, multa, juros, total, text, page_number, divergent, items)


def belongs_to_selected_bank(receipt: ParsedRfb, selected_bank: str) -> bool:
    if selected_bank == "Banco do Brasil":
        return receipt.codigo_banco == "001" or "BANCO DO BRASIL" in normalize_name(receipt.nome_banco)
    return normalize_name(selected_bank) in normalize_name(receipt.nome_banco)
