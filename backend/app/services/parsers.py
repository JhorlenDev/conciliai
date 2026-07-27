import re
import logging
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

from app.services.normalization import normalize_name

logger = logging.getLogger(__name__)

DATE_RE = r"(\d{2}/\d{2}/\d{4})"
TIME_RE = r"(\d{2}:\d{2}(?::\d{2})?)"
NAME_LABELS = ("BENEFICIÁRIO FINAL", "BENEFICIARIO FINAL", "PAGO PARA", "FAVORECIDO", "BENEFICIÁRIO", "BENEFICIARIO", "CONVÊNIO", "CONVENIO")


@dataclass
class FinancialValues:
    valor_original: Decimal | None = None
    valor_desconto: Decimal | None = None
    valor_abatimento: Decimal | None = None
    valor_desconto_abatimento: Decimal | None = None
    valor_juros: Decimal | None = None
    valor_multa: Decimal | None = None
    valor_encargos: Decimal | None = None
    valor_pago: Decimal | None = None
    detalhes: dict[str, str] = field(default_factory=dict)
    composicao_divergente: bool = False


@dataclass
class ParsedReceipt:
    data: date | None
    hora: str | None
    favorecido: str
    valor: Decimal | None
    tipo_operacao: str
    texto_original: str
    pagina_numero: int
    origem_nome: str = ""
    financeiros: FinancialValues = field(default_factory=FinancialValues)


@dataclass
class ParsedStatement:
    data: date | None
    hora: str | None
    historico: str
    nome: str
    valor: Decimal | None
    natureza: str
    texto_original: str
    pagina_numero: int


def parse_brl(value: str) -> Decimal | None:
    cleaned = re.sub(r"[^0-9,.-]", "", value).replace(".", "").replace(",", ".")
    try:
        return Decimal(cleaned).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def parse_date_time(value: str) -> tuple[date | None, str | None]:
    date_match = re.search(DATE_RE, value)
    time_match = re.search(TIME_RE, value)
    parsed_date = date(*map(int, reversed(date_match.group(1).split("/")))) if date_match else None
    return parsed_date, time_match.group(1) if time_match else None


def extract_financial_values(text: str) -> FinancialValues:
    def amount_for(*labels: str) -> Decimal | None:
        for label in labels:
            match = re.search(rf"^\s*{re.escape(label)}\s*:?[ \t]+([^\n]+)", text, re.I | re.M)
            if match:
                amount = parse_brl(match.group(1))
                if amount is not None:
                    return amount
        return None

    values = FinancialValues(
        valor_original=amount_for("VALOR DO DOCUMENTO", "VALOR ORIGINAL"),
        valor_desconto=amount_for("DESCONTO"),
        valor_abatimento=amount_for("ABATIMENTO"),
        valor_desconto_abatimento=amount_for("DESCONTO/ABATIMENTO"),
        valor_juros=amount_for("JUROS/MORA", "JUROS"),
        valor_multa=amount_for("MULTA/MORA", "MULTA"),
        valor_encargos=amount_for("ENCARGOS"),
        valor_pago=amount_for("VALOR COBRADO", "VALOR PAGO", "VALOR TOTAL", "VALOR"),
    )
    if values.valor_original is None:
        values.valor_original = values.valor_pago
    for key in (
        "valor_original", "valor_desconto", "valor_abatimento", "valor_desconto_abatimento",
        "valor_juros", "valor_multa", "valor_encargos", "valor_pago",
    ):
        amount = getattr(values, key)
        if amount is not None:
            values.detalhes[key] = str(amount)
    adjustments = [
        values.valor_desconto, values.valor_abatimento, values.valor_desconto_abatimento,
        values.valor_juros, values.valor_multa, values.valor_encargos,
    ]
    if values.valor_original is not None and values.valor_pago is not None and any(value is not None for value in adjustments):
        expected = values.valor_original - (values.valor_desconto or Decimal()) - (values.valor_abatimento or Decimal()) - (values.valor_desconto_abatimento or Decimal()) + (values.valor_juros or Decimal()) + (values.valor_multa or Decimal()) + (values.valor_encargos or Decimal())
        values.composicao_divergente = abs(expected - values.valor_pago) > Decimal("0.01")
    return values


def find_receipt_name(text: str) -> str | None:
    found = find_receipt_name_with_origin(text)
    return found[0] if found else None


def find_receipt_name_with_origin(text: str) -> tuple[str, str] | None:
    """Returns the named counterparty and label using the required precedence."""
    for label in NAME_LABELS:
        match = re.search(rf"^\s*{re.escape(label)}\s*(?::\s*|\s+)([^\n]+)", text, re.I | re.M)
        if not match:
            continue
        name = match.group(1).strip()
        if name and name.upper() not in {"PIX", "TED", "DOCUMENTO", "BANCO", "PAGADOR"}:
            return name, label
    return None


def extract_receipts(text: str, page_number: int) -> list[ParsedReceipt]:
    """A record is emitted only from a self-contained block with required labels."""
    blocks = re.split(r"(?=^\s*VALOR\s*:)", text, flags=re.I | re.M)
    results = []
    for block in blocks:
        value_match = re.search(r"^\s*VALOR\s*:\s*([^\n]+)", block, re.I | re.M)
        name_info = find_receipt_name_with_origin(block)
        name = name_info[0] if name_info else None
        date_match = re.search(r"^\s*(?:DATA|DEBITO EM|DÉBITO EM)\s*:\s*([^\n]+)", block, re.I | re.M)
        if not (value_match and name and date_match):
            continue
        parsed_date, parsed_time = parse_date_time(date_match.group(1))
        financial = extract_financial_values(block)
        amount = financial.valor_pago
        if not parsed_date or amount is None or not name:
            continue
        operation = "PIX" if re.search(r"\bPIX\b", block, re.I) else "TED" if re.search(r"\bTED|TRANSFER[ÊE]NCIA\b", block, re.I) else ""
        results.append(ParsedReceipt(parsed_date, parsed_time, name, amount, operation, block.strip(), page_number, name_info[1], financial))
    if results:
        return results

    banco_do_brasil = _extract_banco_do_brasil_receipt(text, page_number)
    if banco_do_brasil:
        return banco_do_brasil

    # Payment receipts use a distinct layout, usually with one receipt per PDF page.
    value_match = re.search(r"^\s*(?:VALOR DO DOCUMENTO|VALOR TOTAL|VALOR RECEBIDO|VALOR)\s*:?[ \t]+([^\n]+)", text, re.I | re.M)
    name_info = find_receipt_name_with_origin(text)
    name = name_info[0] if name_info else None
    if not name:
        received_match = re.search(r"^\s*(?:RECEBIDO DE|RECEBIMENTO DE)\s*:?[ \t]+([^\n]+)", text, re.I | re.M)
        name = received_match.group(1).strip() if received_match else None
        name_info = (name, "RECEBIDO DE") if name else None
    date_match = re.search(r"^\s*(?:DATA|DATA DO PAGAMENTO|DATA DO RECEBIMENTO|DEBITO EM|DÉBITO EM)\s*:?[ \t]+([^\n]+)", text, re.I | re.M)
    if value_match and name and date_match:
        parsed_date, parsed_time = parse_date_time(date_match.group(1))
        financial = extract_financial_values(text)
        amount = financial.valor_pago
        if parsed_date and amount is not None and name and name.upper() not in {"PIX", "TED", "DOCUMENTO"}:
            operation = "PIX" if re.search(r"\bPIX\b", text, re.I) else "TED" if re.search(r"\bTED|TRANSFER[ÊE]NCIA\b", text, re.I) else "RECEBIMENTO" if re.search(r"RECEB", text, re.I) else "PAGAMENTO"
            return [ParsedReceipt(parsed_date, parsed_time, name, amount, operation, text.strip(), page_number, name_info[1], financial)]
    return results


def _extract_banco_do_brasil_receipt(text: str, page_number: int) -> list[ParsedReceipt]:
    """Handles BB payment and account-transfer receipts with values on following lines."""
    payment_name = re.search(r"^\s*BENEFICI[ÁA]RIO FINAL\s*:\s*\n\s*([^\n]+)", text, re.I | re.M)
    payment_date = re.search(r"^\s*DATA DO PAGAMENTO\s+(\d{2}/\d{2}/\d{4})", text, re.I | re.M)
    payment_value = re.search(r"^\s*VALOR DO DOCUMENTO\s+([^\n]+)", text, re.I | re.M)
    if payment_name and payment_date and payment_value:
        parsed_date, _ = parse_date_time(payment_date.group(1))
        financial = extract_financial_values(text)
        amount = financial.valor_pago
        if parsed_date and amount is not None:
            return [ParsedReceipt(parsed_date, None, payment_name.group(1).strip(), amount, "PAGAMENTO", text.strip(), page_number, "BENEFICIARIO FINAL", financial)]

    transfer_name = re.search(r"TRANSFERIDO PARA\s*:\s*\n\s*CLIENTE\s*:\s*([^\n]+)", text, re.I)
    transfer_date = re.search(r"^\s*DATA DA TRANSFER[ÊE]NCIA\s+(\d{2}/\d{2}/\d{4})", text, re.I | re.M)
    transfer_value = re.search(r"^\s*VALOR TOTAL\s+([^\n]+)", text, re.I | re.M)
    if transfer_name and transfer_date and transfer_value:
        parsed_date, _ = parse_date_time(transfer_date.group(1))
        financial = extract_financial_values(text)
        amount = financial.valor_pago
        if parsed_date and amount is not None:
            return [ParsedReceipt(parsed_date, None, transfer_name.group(1).strip(), amount, "TRANSFERÊNCIA", text.strip(), page_number, "TRANSFERIDO PARA", financial)]
    return []


def extract_statement(text: str, page_number: int, bank: str = "") -> list[ParsedStatement]:
    if bank == "Banco do Brasil":
        bb_records = _extract_banco_do_brasil_statement(text, page_number)
        if bb_records:
            return bb_records

    results = []
    for line in text.splitlines():
        columns = [item.strip() for item in line.split("|")]
        if len(columns) < 3:
            continue
        parsed_date, _ = parse_date_time(columns[0])
        amount = parse_brl(columns[-1])
        if not parsed_date or amount is None:
            continue
        history = " ".join(columns[1:-1])
        _, hour = parse_date_time(history)
        name = re.sub(r".*?\d{2}/\d{2}\s+(?:\d{2}:\d{2}(?::\d{2})?\s+)?", "", history).strip()
        nature = "saída" if re.search(r"enviado|debito|débito|pagamento", history, re.I) else "entrada"
        results.append(ParsedStatement(parsed_date, hour, history, name, amount, nature, line, page_number))
    return results


def _extract_banco_do_brasil_statement(text: str, page_number: int) -> list[ParsedStatement]:
    """Extracts the vertical text layout produced by Banco do Brasil statements."""
    pattern = re.compile(
        r"(?m)^(?P<data>\d{2}/\d{2}/\d{4})\n"
        r"\d{4}\n"
        r"(?P<historico>[^\n]+)\n"
        r"(?P<documento>[^\n]+?)(?:\n|[ \t]+)"
        r"(?P<valor>[\d.]+,\d{2})[ \t]+(?P<natureza>[CD])(?:[ \t]+[^\n]+)?"
        r"(?P<detalhe>(?:\n(?!\d{2}/\d{2}/\d{4}\n)[^\n]+)*)"
    )
    results = []
    for match in pattern.finditer(text):
        parsed_date, _ = parse_date_time(match.group("data"))
        amount = parse_brl(match.group("valor"))
        history = re.sub(r"^\d+\s+\d+\s+", "", match.group("historico")).strip()
        if re.search(r"\b(?:saldo anterior|saldo do dia|saldo final|limite|valor total devido|cheque especial)\b", history, re.I):
            continue
        detail = match.group("detalhe").strip()
        _, hour = parse_date_time(detail)
        name = re.sub(r"^\d{2}/\d{2}(?:\s+\d{2}:\d{2}(?::\d{2})?)?\s+", "", detail)
        name = re.sub(r"^(?:\d[\d. ]{6,}\s+)+", "", name).strip()
        results.append(ParsedStatement(
            data=parsed_date,
            hora=hour,
            historico=history,
            nome=name,
            valor=amount,
            natureza="saída" if match.group("natureza") == "C" else "entrada",
            texto_original=match.group(0).strip(),
            pagina_numero=page_number,
        ))
    return results


def deduplicate_statement_records(records: list[ParsedStatement]) -> list[ParsedStatement]:
    """Keeps a repeated transaction at a PDF page boundary only once."""
    seen_pages: dict[tuple[object, ...], int] = {}
    unique = []
    for record in records:
        key = (normalize_name(record.texto_original), record.data, record.valor, record.natureza)
        previous_page = seen_pages.get(key)
        if previous_page is not None and previous_page != record.pagina_numero:
            logger.info("Extrato BB duplicado entre páginas ignorado: data=%s historico=%s valor=%s natureza=%s", record.data, record.historico, record.valor, record.natureza)
            continue
        seen_pages[key] = record.pagina_numero
        unique.append(record)
    return unique
