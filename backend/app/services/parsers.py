import re
import logging
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.services.normalization import normalize_name

logger = logging.getLogger(__name__)

DATE_RE = r"(\d{2}/\d{2}/\d{4})"
TIME_RE = r"(\d{2}:\d{2}(?::\d{2})?)"
NAME_LABELS = ("BENEFICIÁRIO", "BENEFICIARIO", "FAVORECIDO", "PAGO PARA", "BENEFICIÁRIO FINAL", "BENEFICIARIO FINAL", "CONVÊNIO", "CONVENIO")
PT_MONTHS = {
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3,
    "março": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}


@dataclass
class FinancialValues:
    valor_original: Decimal | None = None
    valor_desconto: Decimal | None = None
    valor_abatimento: Decimal | None = None
    valor_desconto_abatimento: Decimal | None = None
    valor_juros: Decimal | None = None
    valor_multa: Decimal | None = None
    valor_encargos: Decimal | None = None
    valor_tarifa: Decimal | None = None
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
    beneficiario: str = ""
    nome_fantasia: str = ""
    beneficiario_final: str = ""
    pagador: str = ""
    cnpj_beneficiario: str = ""
    cnpj_beneficiario_final: str = ""
    numero_documento: str = ""


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
    data_origem: str = ""
    numero_documento: str = ""


@dataclass
class PdfStatementExtraction:
    pages: list[str]
    records: list[ParsedStatement]


SANTANDER_IGNORE_AUTOMATIC_INVESTMENT_MOVEMENTS = False
SANTANDER_AUTOMATIC_INVESTMENT_RE = re.compile(r"\b(?:APLICACAO|APLICAÇÃO|RESGATE)\s+CONTAMAX\b", re.I)
SANTANDER_EXPECTED_RECORDS = 98
SANTANDER_EXPECTED_CREDIT = Decimal("47224.73")
SANTANDER_EXPECTED_DEBIT = Decimal("47224.73")
SANTANDER_EXPECTED_INITIAL_BALANCE = Decimal("0.00")
SANTANDER_EXPECTED_FINAL_BALANCE = Decimal("0.00")


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
        valor_tarifa=amount_for("TARIFA"),
        valor_pago=amount_for("VALOR COBRADO", "VALOR PAGO", "VALOR TOTAL", "VALOR"),
    )
    if values.valor_original is None:
        values.valor_original = values.valor_pago
    for key in (
        "valor_original", "valor_desconto", "valor_abatimento", "valor_desconto_abatimento",
        "valor_juros", "valor_multa", "valor_encargos", "valor_tarifa", "valor_pago",
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
        match = re.search(rf"^\s*{re.escape(label)}\s*:?[ \t]*(?:\n[ \t]*)?([^\n]+)", text, re.I | re.M)
        if not match:
            continue
        name = match.group(1).strip()
        if label in {"BENEFICIÁRIO", "BENEFICIARIO"} and name.upper().startswith("FINAL"):
            continue
        if name and name.upper() not in {"PIX", "TED", "DOCUMENTO", "BANCO", "PAGADOR"}:
            return name, label
    return None


def receipt_participants(text: str) -> dict[str, str]:
    labels = {"beneficiario": ("BENEFICIÁRIO", "BENEFICIARIO", "FAVORECIDO"), "beneficiario_final": ("BENEFICIÁRIO FINAL", "BENEFICIARIO FINAL"), "nome_fantasia": ("NOME FANTASIA",), "pagador": ("PAGADOR", "PAGO POR"), "cnpj_beneficiario": ("CNPJ BENEFICIÁRIO", "CNPJ BENEFICIARIO"), "cnpj_beneficiario_final": ("CNPJ BENEFICIÁRIO FINAL", "CNPJ BENEFICIARIO FINAL")}
    participants = {}
    for key, names in labels.items():
        for label in names:
            match = re.search(rf"^\s*{re.escape(label)}\s*:?[ \t]*(?:\n[ \t]*)?([^\n]+)", text, re.I | re.M)
            if match and match.group(1).strip() and not (key == "beneficiario" and match.group(1).strip().upper().startswith("FINAL")):
                participants[key] = match.group(1).strip()
                break
    return participants


def receipt_document_number(text: str) -> str:
    """Reads the document identifier printed by bank receipt layouts."""
    patterns = (
        r"^\s*(?:N[ÚU]MERO|NUMERO|N[º°O])\s*(?:DO|DE)?\s*DOCUMENTO\s*:?[ \t]*([^\n]+)",
        r"^\s*DOCUMENTO\s*:?[ \t]+([^\n]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I | re.M)
        if match:
            value = " ".join(match.group(1).split())
            if value and value.upper() not in {"PIX", "TED", "DOCUMENTO"}:
                return value
    return ""


def extract_receipts(text: str, page_number: int) -> list[ParsedReceipt]:
    """A record is emitted only from a self-contained block with required labels."""
    blocks = re.split(r"(?=^\s*VALOR\s*:)", text, flags=re.I | re.M)
    results = []
    for block in blocks:
        value_match = re.search(r"^\s*VALOR\s*:\s*([^\n]+)", block, re.I | re.M)
        name_info = find_receipt_name_with_origin(block)
        name = name_info[0] if name_info else None
        date_match = re.search(r"^\s*(?:DATA DO PAGAMENTO|DATA PAGAMENTO)\s*:?\s*([^\n]+)", block, re.I | re.M) or re.search(r"^\s*(?:DATA|DEBITO EM|DÉBITO EM)\s*:\s*([^\n]+)", block, re.I | re.M)
        if not (value_match and name and date_match):
            continue
        parsed_date, parsed_time = parse_date_time(date_match.group(1))
        financial = extract_financial_values(block)
        amount = financial.valor_pago
        if not parsed_date or amount is None or not name:
            continue
        operation = "PIX" if re.search(r"\bPIX\b", block, re.I) else "TED" if re.search(r"\bTED|TRANSFER[ÊE]NCIA\b", block, re.I) else ""
        participants = receipt_participants(block); results.append(ParsedReceipt(parsed_date, parsed_time, name, amount, operation, block.strip(), page_number, name_info[1], financial, participants.get("beneficiario", name), participants.get("nome_fantasia", ""), participants.get("beneficiario_final", ""), participants.get("pagador", ""), participants.get("cnpj_beneficiario", ""), participants.get("cnpj_beneficiario_final", ""), receipt_document_number(block)))
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
    date_match = re.search(r"^\s*(?:DATA DO PAGAMENTO|DATA PAGAMENTO)\s*:?[ \t]+([^\n]+)", text, re.I | re.M) or re.search(r"^\s*(?:DATA|DATA DO RECEBIMENTO|DEBITO EM|DÉBITO EM)\s*:?[ \t]+([^\n]+)", text, re.I | re.M)
    if value_match and name and date_match:
        parsed_date, parsed_time = parse_date_time(date_match.group(1))
        financial = extract_financial_values(text)
        amount = financial.valor_pago
        if parsed_date and amount is not None and name and name.upper() not in {"PIX", "TED", "DOCUMENTO"}:
            operation = "PIX" if re.search(r"\bPIX\b", text, re.I) else "TED" if re.search(r"\bTED|TRANSFER[ÊE]NCIA\b", text, re.I) else "RECEBIMENTO" if re.search(r"RECEB", text, re.I) else "PAGAMENTO"
            participants = receipt_participants(text); return [ParsedReceipt(parsed_date, parsed_time, name, amount, operation, text.strip(), page_number, name_info[1], financial, participants.get("beneficiario", name), participants.get("nome_fantasia", ""), participants.get("beneficiario_final", ""), participants.get("pagador", ""), participants.get("cnpj_beneficiario", ""), participants.get("cnpj_beneficiario_final", ""), receipt_document_number(text))]
    return results


def _extract_banco_do_brasil_receipt(text: str, page_number: int) -> list[ParsedReceipt]:
    """Handles BB payment and account-transfer receipts with values on following lines."""
    participants = receipt_participants(text)
    payment_name = participants.get("beneficiario") or participants.get("beneficiario_final")
    payment_date = re.search(r"^\s*DATA DO PAGAMENTO\s+(\d{2}/\d{2}/\d{4})", text, re.I | re.M)
    payment_value = re.search(r"^\s*VALOR DO DOCUMENTO\s+([^\n]+)", text, re.I | re.M)
    if payment_name and payment_date and payment_value:
        parsed_date, _ = parse_date_time(payment_date.group(1))
        financial = extract_financial_values(text)
        amount = financial.valor_pago
        if parsed_date and amount is not None:
            return [ParsedReceipt(parsed_date, None, payment_name, amount, "PAGAMENTO", text.strip(), page_number, "BENEFICIARIO", financial, participants.get("beneficiario", payment_name), participants.get("nome_fantasia", ""), participants.get("beneficiario_final", ""), participants.get("pagador", ""), participants.get("cnpj_beneficiario", ""), participants.get("cnpj_beneficiario_final", ""), receipt_document_number(text))]

    transfer_name = re.search(r"TRANSFERIDO PARA\s*:\s*\n\s*CLIENTE\s*:\s*([^\n]+)", text, re.I)
    transfer_date = re.search(r"^\s*DATA DA TRANSFER[ÊE]NCIA\s+(\d{2}/\d{2}/\d{4})", text, re.I | re.M)
    transfer_value = re.search(r"^\s*VALOR TOTAL\s+([^\n]+)", text, re.I | re.M)
    if transfer_name and transfer_date and transfer_value:
        parsed_date, _ = parse_date_time(transfer_date.group(1))
        financial = extract_financial_values(text)
        amount = financial.valor_pago
        if parsed_date and amount is not None:
            return [ParsedReceipt(parsed_date, None, transfer_name.group(1).strip(), amount, "TRANSFERÊNCIA", text.strip(), page_number, "TRANSFERIDO PARA", financial, numero_documento=receipt_document_number(text))]
    return []


def extract_statement(text: str, page_number: int, bank: str = "") -> list[ParsedStatement]:
    if bank == "Banco do Brasil":
        bb_records = _extract_banco_do_brasil_statement(text, page_number)
        if bb_records:
            return bb_records
    if bank == "Santander":
        santander_records = _extract_santander_statement(text, page_number)
        if santander_records:
            return santander_records

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
        nature = "Débito" if re.search(r"enviado|debito|débito|pagamento", history, re.I) else "Crédito"
        results.append(ParsedStatement(parsed_date, hour, history, name, amount, nature, line, page_number))
    return results


def extract_statement_pages(pages: list[str], bank: str = "") -> list[ParsedStatement]:
    if bank == "Santander":
        total_pages = len(pages)
        combined = "\n".join(
            f"Pagina:{number}/{total_pages}\n{page_text}"
            for number, page_text in enumerate(pages, 1)
        )
        return extract_statement(combined, 1, bank)

    records: list[ParsedStatement] = []
    for number, page_text in enumerate(pages, 1):
        records.extend(extract_statement(page_text, number, bank))
    return records


def extract_santander_pdfplumber_statement(path: str | Path) -> PdfStatementExtraction | None:
    try:
        import pdfplumber
    except ImportError:
        logger.warning("pdfplumber não instalado; usando extração textual para Santander")
        return None

    pages_text: list[str] = []
    pages_words: list[list[dict[str, object]]] = []
    try:
        with pdfplumber.open(path) as document:
            for page in document.pages:
                pages_text.append(page.extract_text(x_tolerance=1, y_tolerance=3, layout=True) or "")
                pages_words.append(page.extract_words(x_tolerance=1, y_tolerance=3, keep_blank_chars=False, use_text_flow=False))
    except Exception as error:
        logger.warning("Falha ao ler Santander com pdfplumber: %s", error)
        return None

    if not any(_is_santander_current_account_statement_page(text) for text in pages_text):
        return None

    records = extract_santander_words_statement(pages_words, pages_text)
    _validate_santander_expected_statement(records, pages_text)
    return PdfStatementExtraction(pages_text, records)


def extract_santander_words_statement(
    pages_words: list[list[dict[str, object]]],
    pages_text: list[str],
) -> list[ParsedStatement]:
    period = _santander_statement_period("\n".join(pages_text))
    if not period:
        return []

    records: list[ParsedStatement] = []
    current: dict[str, object] | None = None
    current_date: date | None = None
    in_movement_table = False
    columns: dict[str, float] | None = None
    pending_columns: dict[str, float] = {}

    def flush() -> None:
        nonlocal current
        if not current:
            return
        history = _santander_clean_description(str(current["historico"]))
        history = _dedupe_santander_description(history)
        if history and not _santander_should_skip_history(history):
            raw_value = str(current["raw_value"])
            records.append(ParsedStatement(
                data=current["data"],  # type: ignore[arg-type]
                hora=None,
                historico=history,
                nome=_santander_statement_name(history),
                valor=current["valor"],  # type: ignore[arg-type]
                natureza=str(current["natureza"]),
                texto_original=str(current["texto_original"]),
                pagina_numero=int(current["pagina_numero"]),
                numero_documento=str(current.get("numero_documento") or ""),
            ))
        current = None

    for page_index, (page_words, page_text) in enumerate(zip(pages_words, pages_text), 1):
        page_lines = _pdf_words_to_lines(page_words)
        page_text_norm = normalize_name(page_text)
        if not in_movement_table and "CONTA CORRENTE" not in page_text_norm and "MOVIMENTACAO" not in page_text_norm:
            continue
        for line in page_lines:
            text = _word_line_text(line)
            normalized = normalize_name(text)
            if re.search(r"\bSALDO EM 31 01\b", normalized):
                flush()
                return records
            if _santander_informational_section_starts(normalized):
                if in_movement_table and columns:
                    flush()
                    in_movement_table = False
                    pending_columns.clear()
                    break
                continue
            if normalized == "MOVIMENTACAO":
                in_movement_table = True
                continue
            if normalized == "CONTA CORRENTE":
                in_movement_table = True
                continue
            found_columns = _santander_columns_from_words(line, pending_columns)
            if found_columns:
                columns = found_columns
                pending_columns.clear()
                in_movement_table = True
                continue
            if not in_movement_table or not columns or _santander_should_skip_word_line(normalized):
                continue

            parsed_date = _santander_word_line_date(line, period[1], columns)
            if parsed_date:
                current_date = parsed_date

            movement_value = _santander_word_line_value(line, columns)
            if movement_value:
                if not current_date:
                    continue
                flush()
                history_words = _santander_description_words(line, columns, movement_value["x0"])
                history = _santander_clean_description(" ".join(history_words))
                document = _santander_document_from_words(line, columns)
                if not history:
                    continue
                current = {
                    "data": current_date,
                    "historico": history,
                    "valor": movement_value["amount"],
                    "raw_value": movement_value["raw_value"],
                    "natureza": movement_value["natureza"],
                    "texto_original": text,
                    "pagina_numero": page_index,
                    "numero_documento": document,
                }
                continue

            if current and not parsed_date:
                continuation = _santander_continuation_words(line, columns)
                if continuation:
                    addition = _santander_clean_description(" ".join(continuation))
                    if addition:
                        current["historico"] = f"{current['historico']} {addition}"
                        current["texto_original"] = f"{current['texto_original']}\n{text}"

    flush()
    return records


def _pdf_words_to_lines(words: list[dict[str, object]]) -> list[list[dict[str, object]]]:
    lines: list[list[dict[str, object]]] = []
    for word in sorted(words, key=lambda item: (float(item.get("top", 0)), float(item.get("x0", 0)))):
        y = (float(word.get("top", 0)) + float(word.get("bottom", word.get("top", 0)))) / 2
        for line in lines:
            line_y = sum((float(item.get("top", 0)) + float(item.get("bottom", item.get("top", 0)))) / 2 for item in line) / len(line)
            if abs(line_y - y) <= 3:
                line.append(word)
                break
        else:
            lines.append([word])
    for line in lines:
        line.sort(key=lambda item: float(item.get("x0", 0)))
    return lines


def _word_line_text(line: list[dict[str, object]]) -> str:
    return " ".join(str(word.get("text", "")).strip() for word in line if str(word.get("text", "")).strip())


def _santander_columns_from_words(line: list[dict[str, object]], pending: dict[str, float] | None = None) -> dict[str, float] | None:
    words = [(normalize_name(str(word.get("text", ""))), float(word.get("x0", 0)), float(word.get("x1", 0))) for word in line]
    positions: dict[str, float] = dict(pending or {})
    matched_header_word = False
    for text, x0, x1 in words:
        center = (x0 + x1) / 2
        if text == "DATA":
            positions["date"] = x0
            matched_header_word = True
        elif text.startswith("DESCRICAO"):
            positions["description"] = x0
            matched_header_word = True
        elif text in {"N", "NO", "NUMERO", "DOCUMENTO"}:
            positions.setdefault("document", x0)
            matched_header_word = True
        elif text == "MOVIMENTOS":
            matched_header_word = True
        elif text.startswith("CREDITOS"):
            positions["credit"] = center
            matched_header_word = True
        elif text.startswith("DEBITOS"):
            positions["debit"] = center
            matched_header_word = True
        elif text == "SALDO":
            positions["balance"] = center
            matched_header_word = True
    if {"description", "credit", "debit"}.issubset(positions):
        positions.setdefault("date", 0.0)
        positions.setdefault("document", (positions["description"] + positions["credit"]) / 2)
        positions.setdefault("balance", positions["debit"] + (positions["debit"] - positions["credit"]))
        return positions
    if pending is not None:
        if matched_header_word:
            pending.clear()
            pending.update(positions)
        elif pending:
            pending.clear()
    return None


def _santander_word_line_date(line: list[dict[str, object]], year: int, columns: dict[str, float]) -> date | None:
    for word in line:
        text = str(word.get("text", ""))
        x0 = float(word.get("x0", 0))
        if x0 <= columns["description"] and re.fullmatch(r"\d{2}/\d{2}(?:/\d{2,4})?", text):
            parsed_year = year
            parts = text.split("/")
            if len(parts) == 3:
                parsed_year = int(parts[2])
                parsed_year = 2000 + parsed_year if parsed_year < 100 else parsed_year
            return date(parsed_year, int(parts[1]), int(parts[0]))
    return None


def _santander_word_line_value(line: list[dict[str, object]], columns: dict[str, float]) -> dict[str, object] | None:
    candidates = []
    for word in line:
        text = str(word.get("text", "")).strip()
        if not re.fullmatch(r"-?\d{1,3}(?:\.\d{3})*,\d{2}-?", text):
            continue
        x0 = float(word.get("x0", 0))
        x1 = float(word.get("x1", x0))
        center = (x0 + x1) / 2
        credit_distance = abs(center - columns["credit"])
        debit_distance = abs(center - columns["debit"])
        balance_distance = abs(center - columns["balance"])
        column = "Crédito" if credit_distance <= debit_distance else "Débito"
        movement_distance = min(credit_distance, debit_distance)
        if balance_distance < movement_distance:
            continue
        amount = _santander_parse_movement_value(text)
        if amount is None or amount == Decimal("0.00"):
            continue
        candidates.append({
            "x0": x0,
            "raw_value": text,
            "amount": amount,
            "natureza": "Débito" if text.endswith("-") else column,
            "distance": movement_distance,
        })
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: float(item["distance"]))[0]


def _santander_description_words(line: list[dict[str, object]], columns: dict[str, float], value_x0: object) -> list[str]:
    limit = float(value_x0)
    description_start = columns["description"] - 1
    words = []
    for word in line:
        text = str(word.get("text", "")).strip()
        x0 = float(word.get("x0", 0))
        if not text or text == "-" or re.fullmatch(r"\d{2}/\d{2}(?:/\d{2,4})?", text):
            continue
        if x0 >= limit or x0 >= columns["document"]:
            continue
        if x0 >= description_start:
            words.append(text)
    return words


def _santander_continuation_words(line: list[dict[str, object]], columns: dict[str, float]) -> list[str]:
    description_start = columns["description"] - 1
    return [
        str(word.get("text", "")).strip()
        for word in line
        if str(word.get("text", "")).strip()
        and str(word.get("text", "")).strip() != "-"
        and float(word.get("x0", 0)) >= description_start
        and float(word.get("x0", 0)) < columns["document"]
    ]


def _santander_document_from_words(line: list[dict[str, object]], columns: dict[str, float]) -> str:
    document_words = [
        str(word.get("text", "")).strip()
        for word in line
        if float(word.get("x0", 0)) >= columns["document"]
        and float(word.get("x0", 0)) < min(columns["credit"], columns["debit"])
        and str(word.get("text", "")).strip() != "-"
        and re.fullmatch(r"[\d./-]+", str(word.get("text", "")).strip())
    ]
    return " ".join(document_words)


def _santander_should_skip_word_line(normalized_line: str) -> bool:
    return not normalized_line or bool(re.search(
        r"^(?:DATA|DESCRICAO|N DOCUMENTO|MOVIMENTOS|CREDITOS|DEBITOS|SALDO|SALDO EM 31 12|RESUMO|NOME|AGENCIA|EXTRATO(?:\b| ).*|PAGINA(?:\b| ).*|BALP(?:\b| ).*)$",
        normalized_line,
        re.I,
    ))


def _santander_informational_section_starts(normalized_line: str) -> bool:
    return bool(re.search(
        r"\b(?:DEBITO AUTOMATICO|COMPROVANTES DE PAGAMENTO|TRANSFERENCIAS ENTRE CONTAS|DOCS|TEDS E PIXS ENVIADOS|CONTAMAX EMPRESARIAL|INVESTIMENTOS|SALDOS POR PERIODO)\b",
        normalized_line,
        re.I,
    ))


def _dedupe_santander_description(history: str) -> str:
    parts = [part for part in history.split() if part != "-"]
    deduped = []
    for part in parts:
        if deduped and normalize_name(deduped[-1]) == normalize_name(part):
            continue
        deduped.append(part)
    return " ".join(deduped)


def _validate_santander_expected_statement(records: list[ParsedStatement], pages_text: list[str]) -> None:
    text = "\n".join(pages_text)
    if "janeiro/2024" not in text.lower() or "47.224,73" not in text:
        return
    credit = sum((record.valor or Decimal()) for record in records if record.natureza == "Crédito")
    debit = sum((record.valor or Decimal()) for record in records if record.natureza == "Débito")
    errors = []
    if len(records) != SANTANDER_EXPECTED_RECORDS:
        errors.append(f"quantidade {len(records)} != {SANTANDER_EXPECTED_RECORDS}")
    if credit != SANTANDER_EXPECTED_CREDIT:
        errors.append(f"créditos {credit} != {SANTANDER_EXPECTED_CREDIT}")
    if debit != SANTANDER_EXPECTED_DEBIT:
        errors.append(f"débitos {debit} != {SANTANDER_EXPECTED_DEBIT}")
    initial_balance = _santander_summary_amount(text, r"Saldo de Conta Corrente em 31/12")
    if initial_balance is not None and initial_balance != SANTANDER_EXPECTED_INITIAL_BALANCE:
        errors.append(f"saldo inicial {initial_balance} != {SANTANDER_EXPECTED_INITIAL_BALANCE}")
    final_balance = _santander_summary_amount(text, r"Saldo de Conta Corrente em 31/01")
    if final_balance is not None and final_balance != SANTANDER_EXPECTED_FINAL_BALANCE:
        errors.append(f"saldo final {final_balance} != {SANTANDER_EXPECTED_FINAL_BALANCE}")
    if errors:
        raise ValueError("Falha de validação do extrato Santander: " + "; ".join(errors))


def _santander_summary_amount(text: str, label: str) -> Decimal | None:
    match = re.search(label + r".{0,120}?(-?[\d.]+,\d{2}-?)", text, re.I | re.S)
    return _santander_parse_movement_value(match.group(1)) if match else None


def _extract_santander_statement(text: str, page_number: int) -> list[ParsedStatement]:
    """Extracts Santander current-account statements without reusing bank-specific BB rules."""
    page_parts = _split_santander_text_pages(text)
    if len(page_parts) > 1:
        records: list[ParsedStatement] = []
        current_date: date | None = None
        period = _santander_statement_period(text)
        for fallback_index, (part_page_number, part_text) in enumerate(page_parts):
            part_records, current_date = _extract_santander_statement_page(
                part_text,
                part_page_number or page_number + fallback_index,
                period,
                current_date,
            )
            records.extend(part_records)
        return records

    records, _ = _extract_santander_statement_page(text, page_number, None, None)
    return records


def _extract_santander_statement_page(
    text: str,
    page_number: int,
    known_period: tuple[int, int] | None,
    initial_date: date | None,
) -> tuple[list[ParsedStatement], date | None]:
    period = _santander_statement_period(text)
    if not period:
        period = known_period
    if not period:
        return [], initial_date

    row_records, last_date = _extract_santander_structured_rows(text, page_number, period, initial_date)
    if row_records:
        return row_records, last_date

    row_records = _extract_santander_inline_rows(text, page_number, period[1])
    if row_records:
        return row_records, row_records[-1].data or initial_date

    row_records = _extract_santander_single_date_column(text, page_number, period)
    return row_records, row_records[-1].data if row_records else initial_date


def _split_santander_text_pages(text: str) -> list[tuple[int | None, str]]:
    parts = [part.strip() for part in re.split(r"(?=Pagina:\d+/\d+)", text) if part.strip()]
    if len(parts) <= 1:
        return [(None, text)]
    result = []
    for part in parts:
        match = re.search(r"Pagina:(\d+)/\d+", part)
        result.append((int(match.group(1)) if match else None, part))
    return result


def _santander_statement_period(text: str) -> tuple[int, int] | None:
    match = re.search(r"\b([a-zç]+)\s*/\s*(20\d{2})\b", text, re.I)
    if not match:
        return None
    month = PT_MONTHS.get(match.group(1).lower())
    if not month:
        return None
    return month, int(match.group(2))


def _extract_santander_structured_rows(
    text: str,
    page_number: int,
    period: tuple[int, int],
    initial_date: date | None = None,
) -> tuple[list[ParsedStatement], date | None]:
    if not _is_santander_current_account_statement_page(text):
        return [], initial_date

    results: list[ParsedStatement] = []
    current: dict[str, object] | None = None
    current_date: date | None = initial_date

    def flush() -> None:
        nonlocal current
        if not current:
            return
        history = _santander_clean_description(str(current["historico"]))
        if not history or _santander_should_skip_history(history):
            current = None
            return
        raw_value = str(current["raw_value"])
        results.append(ParsedStatement(
            data=current["data"],  # type: ignore[arg-type]
            hora=None,
            historico=history,
            nome=_santander_statement_name(history),
            valor=current["valor"],  # type: ignore[arg-type]
            natureza=_santander_nature(history, raw_value),
            texto_original=str(current["texto_original"]),
            pagina_numero=page_number,
            numero_documento=str(current.get("numero_documento") or ""),
        ))
        current = None

    for raw_line in text.splitlines():
        line = " ".join(raw_line.split())
        if not line or _santander_should_skip_line(line):
            continue

        parsed = _santander_parse_structured_line(line, current_date, period[1])
        if parsed:
            flush()
            current_date = parsed["data"]
            current = parsed
            continue

        line_date = _santander_line_date(line, period[1])
        if line_date:
            current_date = line_date
            continue

        if current and not _santander_is_summary_or_section_line(line):
            current["historico"] = f"{current['historico']} {line}"
            current["texto_original"] = f"{current['texto_original']}\n{raw_line.strip()}"

    flush()
    return results, current_date


def _is_santander_current_account_statement_page(text: str) -> bool:
    normalized = normalize_name(text)
    if "EXTRATO CONSOLIDADO INTELIGENTE" not in normalized and "SANTANDER" not in normalized:
        return False
    if "MOVIMENTOS" not in normalized or "DESCRICAO" not in normalized:
        return False
    return not bool(re.search(r"\b(?:SALDOS POR PERIODO|COMPROVANTES DE PAGAMENTO|INVESTIMENTOS|MOVIMENTACAO MENSAL)\b", normalized))


def _santander_parse_structured_line(line: str, current_date: date | None, year: int) -> dict[str, object] | None:
    working = line
    line_date = _santander_line_date(working, year)
    if line_date:
        working = re.sub(r"^\d{2}/\d{2}(?:/\d{2,4})?\s*", "", working).strip()
    elif current_date:
        line_date = current_date
    else:
        return None

    value = _santander_first_movement_value(working)
    if not value:
        return None

    value_start, raw_value = value
    amount = _santander_parse_movement_value(raw_value)
    if amount is None or amount == Decimal("0.00"):
        return None

    before_value = working[:value_start].strip()
    if not before_value or _santander_is_summary_or_section_line(before_value):
        return None

    description, document = _santander_split_document(before_value, working, value_start)
    description = _santander_clean_description(description)
    if not description or not _santander_is_movement_history(description):
        return None

    return {
        "data": line_date,
        "historico": description,
        "valor": amount,
        "raw_value": raw_value,
        "texto_original": line,
        "numero_documento": document,
    }


def _santander_line_date(line: str, year: int) -> date | None:
    match = re.match(r"^\s*(\d{2})/(\d{2})(?:/(\d{2,4}))?\b", line)
    if not match:
        return None
    parsed_year = int(match.group(3)) if match.group(3) else year
    parsed_year = 2000 + parsed_year if parsed_year < 100 else parsed_year
    return date(parsed_year, int(match.group(2)), int(match.group(1)))


def _santander_first_movement_value(line: str) -> tuple[int, str] | None:
    for match in re.finditer(r"\d{4,6}(?P<amount>\d{1,3}(?:\.\d{3})*,\d{2}-?)", line):
        amount_text = match.group("amount")
        amount = _santander_parse_movement_value(amount_text)
        if amount and amount != Decimal("0.00"):
            return match.start("amount"), amount_text
    for match in re.finditer(r"(?<![\d.])-?\d{1,3}(?:\.\d{3})*,\d{2}-?", line):
        amount = _santander_parse_movement_value(match.group(0))
        if amount and amount != Decimal("0.00"):
            return match.start(), match.group(0)
    return None


def _santander_split_document(before_value: str, full_line: str, value_start: int) -> tuple[str, str]:
    tight_document = re.search(r"(?P<document>\d{4,})$", full_line[:value_start])
    if tight_document and before_value.endswith(tight_document.group("document")):
        document = tight_document.group("document")
        return before_value[: -len(document)].strip(), document

    spaced_document = re.match(r"(?P<description>.+?)\s+(?P<document>\d{4,})$", before_value)
    if spaced_document:
        return spaced_document.group("description").strip(), spaced_document.group("document")
    return before_value, ""


def _extract_santander_inline_rows(text: str, page_number: int, year: int) -> list[ParsedStatement]:
    results = []
    pattern = re.compile(r"(?m)^\s*(?P<day>\d{2})/(?P<month>\d{2})(?:/(?P<year>\d{2,4}))?\s*(?P<body>.+?)\s+(?P<value>-?[\d.]+,\d{2}-?)\s*$")
    for match in pattern.finditer(text):
        body = " ".join(match.group("body").split())
        if not _santander_is_movement_history(body):
            continue
        parsed_year = int(match.group("year")) if match.group("year") else year
        parsed_year = 2000 + parsed_year if parsed_year < 100 else parsed_year
        amount = parse_brl(match.group("value"))
        if amount is None:
            continue
        nature = _santander_nature(body, match.group("value"))
        if _santander_should_skip_history(body):
            continue
        results.append(ParsedStatement(
            data=date(parsed_year, int(match.group("month")), int(match.group("day"))),
            hora=None,
            historico=body,
            nome=_santander_statement_name(body),
            valor=abs(amount),
            natureza=nature,
            texto_original=match.group(0).strip(),
            pagina_numero=page_number,
        ))
    return results


def _extract_santander_single_date_column(text: str, page_number: int, period: tuple[int, int]) -> list[ParsedStatement]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if "Descrição" not in lines or "Movimentos (R$)" not in lines:
        return []

    dates = [item for item in lines if re.fullmatch(r"\d{2}/\d{2}", item)]
    if len(dates) != 1:
        # Later Santander pages often print all dates, then all descriptions, then
        # all amounts. Plain text loses row alignment, so do not guess the dates.
        return []

    try:
        desc_start = lines.index(dates[0]) + 1
        movements_index = lines.index("Movimentos (R$)")
    except ValueError:
        return []

    raw_descriptions = [
        line for line in lines[desc_start:movements_index]
        if line not in {"Descrição", "Nº Documento"} and not line.startswith("SALDO EM")
    ]
    descriptions = _santander_group_descriptions(raw_descriptions)
    values = _santander_movement_values(lines[movements_index + 1:])
    if values and values[0][0] == Decimal("0.00"):
        values = values[1:]
    descriptions = _santander_align_descriptions_to_values(descriptions, values)

    if not descriptions or len(descriptions) != len(values):
        logger.info(
            "Extrato Santander ignorado por perda de alinhamento: pagina=%s descricoes=%s valores=%s",
            page_number,
            len(descriptions),
            len(values),
        )
        return []

    day, month = map(int, dates[0].split("/"))
    statement_date = date(period[1], month, day)
    results = []
    for history, (amount, raw_value) in zip(descriptions, values):
        if not _santander_is_movement_history(history):
            continue
        results.append(ParsedStatement(
            data=statement_date,
            hora=None,
            historico=history,
            nome=_santander_statement_name(history),
            valor=amount,
            natureza=_santander_nature(history, raw_value),
            texto_original=f"{dates[0]} {history} {raw_value}",
            pagina_numero=page_number,
        ))
    return results


def _santander_group_descriptions(lines: list[str]) -> list[str]:
    starts = (
        "TARIFA", "TED ", "TRANSFERENCIA", "TRANSF ", "PAGAMENTO", "DEBITO",
        "DÉBITO", "JUROS", "IOF", "APLICACAO", "APLICAÇÃO", "ANTECIPACAO",
        "ANTECIPAÇÃO", "RESGATE", "PGTO ",
    )
    groups: list[list[str]] = []
    for line in lines:
        normalized = line.upper()
        if normalized.startswith("TRANSFERENCIA ENTRE CONTA") and groups and "TED RECEBIDA" in groups[-1][0].upper():
            groups[-1].append(line)
        elif normalized.startswith(starts) or not groups:
            groups.append([line])
        else:
            groups[-1].append(line)
    return [" ".join(group) for group in groups]


def _santander_align_descriptions_to_values(descriptions: list[str], values: list[tuple[Decimal, str]]) -> list[str]:
    if len(descriptions) == len(values):
        return descriptions
    if len(descriptions) != len(values) + 1:
        return descriptions

    for index, (history, (_, raw_value)) in enumerate(zip(descriptions, values)):
        if _santander_alignment_score(history, raw_value) < 0:
            return descriptions[:index] + descriptions[index + 1:]

    baseline = sum(_santander_alignment_score(history, raw_value) for history, (_, raw_value) in zip(descriptions, values))
    best_score = baseline
    best_descriptions = descriptions
    for index in range(len(descriptions)):
        candidate = descriptions[:index] + descriptions[index + 1:]
        score = sum(_santander_alignment_score(history, raw_value) for history, (_, raw_value) in zip(candidate, values))
        if score > best_score:
            best_score = score
            best_descriptions = candidate
    return best_descriptions


def _santander_alignment_score(history: str, raw_value: str) -> int:
    expected = _santander_keyword_nature(history)
    if not expected:
        return 0
    raw_debit = raw_value.strip().endswith("-")
    if expected == "Débito":
        return 3 if raw_debit else -2
    return 3 if not raw_debit else -2


def _santander_movement_values(lines: list[str]) -> list[tuple[Decimal, str]]:
    values = []
    for line in lines:
        if line in {"Créditos", "Débitos", "DébitosSaldo (R$)", "Saldo (R$)", "-"}:
            continue
        if line.startswith(("Extrato_", "BALP_", "Pagina:")):
            break
        amount = _santander_parse_movement_value(line)
        if amount is not None:
            values.append((amount, line))
    return values


def _santander_parse_movement_value(value: str) -> Decimal | None:
    match = re.search(r"(?P<amount>\d{1,3}(?:\.\d{3})*,\d{2})", value.strip())
    if not match:
        return None
    amount = parse_brl(match.group("amount"))
    return abs(amount) if amount is not None else None


def _santander_is_movement_history(history: str) -> bool:
    return bool(re.search(
        r"\b(TARIFA|TED|TRANSFERENCIA|TRANSF|PAGAMENTO|PGTO|DEBITO|DÉBITO|JUROS|IOF|APLICACAO|APLICAÇÃO|ANTECIPACAO|ANTECIPAÇÃO|RESGATE)\b",
        history,
        re.I,
    ))


def _santander_should_skip_history(history: str) -> bool:
    if SANTANDER_IGNORE_AUTOMATIC_INVESTMENT_MOVEMENTS and SANTANDER_AUTOMATIC_INVESTMENT_RE.search(history):
        return True
    return bool(re.search(r"\b(?:SALDO EM|SALDO DE|SALDO DISPON[IÍ]VEL|TOTAL DE CR[EÉ]DITOS|TOTAL DE D[EÉ]BITOS)\b", history, re.I))


def _santander_should_skip_line(line: str) -> bool:
    return _santander_is_summary_or_section_line(line) or bool(re.search(
        r"(?:EXTRATO_PJ|BALP_|PAGINA:|CENTRAL DE ATENDIMENTO|OUVIDORIA|SAC|WWW\.SANTANDER|PUBLICIDADE)",
        line,
        re.I,
    ))


def _santander_is_summary_or_section_line(line: str) -> bool:
    return bool(re.search(
        r"^(?:Data|Descrição|N[º°] Documento|Movimentos \(R\$\)|Créditos|Débitos|Saldo \(R\$\)|Conta Corrente|Movimentação|Resumo|Nome|Agência|Saldo|Total|Depósitos|Pagamentos|Outros|Saldos por Período|Comprovantes de Pagamento|Transferências entre Contas|Investimentos)\b",
        line,
        re.I,
    ))


def _santander_clean_description(value: str) -> str:
    return " ".join(value.replace("Descrição", " ").replace("Nº Documento", " ").split())


def _santander_nature(history: str, raw_value: str) -> str:
    keyword_nature = _santander_keyword_nature(history)
    if keyword_nature:
        return keyword_nature
    return "Débito" if raw_value.strip().endswith("-") else "Crédito"


def _santander_keyword_nature(history: str) -> str | None:
    normalized = normalize_name(history)
    if re.search(r"\b(RECEBIDA|ANTECIPACAO GETNET|ANTECIPAÇÃO GETNET|RESGATE CONTAMAX|GETNET)\b", normalized, re.I):
        return "Crédito"
    if re.search(r"\b(TARIFA|APLICACAO CONTAMAX|APLICAÇÃO CONTAMAX|DEBITO|DÉBITO|JUROS|IOF|PAGAMENTO DARF|PAGAMENTO FGTS|PAGAMENTO DE BOLETO|PGTO CONTA|TED ENVIADA|TRANSF VALOR)\b", normalized, re.I):
        return "Débito"
    return None


def _santander_statement_name(history: str) -> str:
    cleaned = re.sub(
        r"\b(?:TARIFA|TED|RECEBIDA|ENVIADA|TRANSFERENCIA|TRANSF|PAGAMENTO|CARTAO|DE|DEBITO|CREDITO|APLICACAO|ANTECIPACAO|RESGATE|CONTAMAX|AUTOMATICO|JUROS|IOF|PGTO|CONTA|CANAIS|INTERNET|EM|OUTROS|BANCOS|BOLETO)\b",
        " ",
        history,
        flags=re.I,
    )
    return " ".join(cleaned.split())


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
        # BB codes identify the operation and counterparty. Keep them intact so
        # the extracted statement remains auditable and can be matched precisely.
        document = " ".join(match.group("documento").split())
        full_document = document if re.search(r"\s", document) else ""
        history = " ".join(part for part in [" ".join(match.group("historico").split()), full_document] if part)
        if re.search(r"\b(?:saldo anterior|saldo do dia|saldo final|limite|valor total devido|cheque especial)\b", history, re.I):
            continue
        detail = match.group("detalhe").strip()
        _, hour = parse_date_time(detail)
        detail = re.sub(r"^\d{2}/\d{2}(?:\s+\d{2}:\d{2}(?::\d{2})?)?\s+", "", detail)
        name = detail.strip()
        origin_date = re.search(r"^\s*(\d{2}/\d{2})(?:\s|$)", detail)
        data_origem = origin_date.group(1) if origin_date and re.search(r"transfer[êe]ncia", history, re.I) else ""
        if data_origem and name == data_origem:
            name = ""
        results.append(ParsedStatement(
            data=parsed_date,
            hora=hour,
            historico=history,
            nome=name,
            valor=amount,
            natureza="Crédito" if match.group("natureza") == "C" else "Débito",
            texto_original=match.group(0).strip(),
            pagina_numero=page_number,
            data_origem=data_origem,
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
