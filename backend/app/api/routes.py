import csv
import io
import shutil
import re
import zipfile
import logging
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
from xml.etree import ElementTree

import fitz
from openpyxl import load_workbook
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import UPLOAD_DIR
from app.core.database import get_db
from app.models import Arquivo, Cliente, Comprovante, ComprovanteRfb, ComprovanteRfbItem, Conciliacao, ContaBancaria, Correspondencia, DocumentoImportante, LancamentoContabil, MovimentoExtrato, NotaFiscal, ProcessoConciliacao, RegraContabil
from app.services.normalization import accounting_nature, is_statement_debit, normalize_name, normalize_rule_accounting_nature, normalize_statement_nature
from app.services.matching import names_similar
from app.services.parsers import deduplicate_statement_records, extract_receipts, extract_statement
from app.services.rfb import belongs_to_selected_bank, parse_rfb_page
from app.services.rule_source import choose_rule_source

router = APIRouter()
BANKS = ["Banco do Brasil", "Santander", "BASA", "Bradesco", "Conta Caixa", "Vendas com Cartão", "Comissões Getnet", "Apropriações", "Empréstimos/Financeiro"]
logger = logging.getLogger(__name__)


@router.get("/arquivos/{arquivo_id}/visualizar")
def view_file(arquivo_id: str, db: Session = Depends(get_db)):
    record = db.get(Arquivo, arquivo_id)
    if not record or not Path(record.caminho).is_file():
        raise HTTPException(404, "Documento original não encontrado")
    return FileResponse(Path(record.caminho), media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{record.nome_original}"'})


@router.delete("/arquivos/{arquivo_id}", status_code=204)
def delete_file(arquivo_id: str, db: Session = Depends(get_db)):
    record = db.get(Arquivo, arquivo_id)
    if not record:
        raise HTTPException(404, "Arquivo não encontrado")
    reset_reconciliation(record.conciliacao_id, db)
    if record.tipo_documento == "extrato":
        db.query(MovimentoExtrato).filter_by(arquivo_id=record.id).delete()
    elif record.tipo_documento == "comprovante":
        db.query(Comprovante).filter_by(arquivo_id=record.id).delete()
    else:
        receipts = db.query(ComprovanteRfb).filter_by(arquivo_id=record.id).all()
        for receipt in receipts:
            db.query(ComprovanteRfbItem).filter_by(comprovante_rfb_id=receipt.id).delete()
        db.query(ComprovanteRfb).filter_by(arquivo_id=record.id).delete()
    Path(record.caminho).unlink(missing_ok=True)
    db.delete(record)
    db.commit()


class ClienteInput(BaseModel):
    nome: str
    documento: str | None = None


class ClienteUpdate(BaseModel):
    nome: str
    documento: str | None = None


class ConciliacaoInput(BaseModel):
    cliente_id: str
    banco: str
    data_inicio: date
    data_fim: date


class ProcessoConciliacaoInput(BaseModel):
    cliente_id: str
    data_inicio: date
    data_fim: date
    banco: str | None = None


class ProcessoBancoInput(BaseModel):
    banco: str


class RegraContabilInput(BaseModel):
    gatilho: str
    natureza: str
    conta_debito: str
    conta_credito: str
    historico: str
    complemento: str = ""
    tipo_componente: str = ""


class ContaBancariaInput(BaseModel):
    conta_contabil: str


class LancamentoItemInput(BaseModel):
    id: str = ""
    componente: str
    valor: Decimal
    efeito_no_total: str = "SOMA"
    conta_debito: str
    conta_credito: str
    historico: str
    descricao: str = ""
    tributo: str = ""
    codigo_receita: str = ""


class LancamentosInput(BaseModel):
    itens: list[LancamentoItemInput]


@router.get("/bancos")
def banks():
    return BANKS


def important_document_payload(record: DocumentoImportante) -> dict:
    return {"id": record.id, "tipo": record.tipo, "nome": record.nome_original, "extensao": record.extensao, "criado_em": record.created_at.isoformat(), "itens_extraidos": len(record.catalogo.get("contas" if record.tipo == "plano_contas" else "historicos", []))}


def extract_important_catalog(path: Path, extension: str, tipo: str) -> dict:
    if extension == ".pdf":
        with fitz.open(path) as document:
            rows = [line.strip() for page in document for line in page.get_text().splitlines() if line.strip()]
    else:
        rows = []
        try:
            workbook = load_workbook(path, read_only=True, data_only=True)
            for sheet in workbook.worksheets:
                account_columns = (0, 1)
                for row in sheet.iter_rows(values_only=True):
                    raw_values = [str(value).strip() if value is not None else "" for value in row]
                    values = [value for value in raw_values if value]
                    if tipo == "plano_contas":
                        headers = [value.lower().replace("ó", "o") for value in raw_values]
                        if "codigo" in headers and "nome" in headers:
                            account_columns = (headers.index("codigo"), headers.index("nome"))
                            continue
                        values = [raw_values[index] for index in account_columns if index < len(raw_values) and raw_values[index]]
                    if values:
                        rows.append(" - ".join(values))
        except Exception:
            # Some exports contain invalid styles. Extract cell values directly.
            namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            with zipfile.ZipFile(path) as workbook:
                shared = []
                if "xl/sharedStrings.xml" in workbook.namelist():
                    root = ElementTree.fromstring(workbook.read("xl/sharedStrings.xml"))
                    shared = ["".join(item.itertext()) for item in root.findall("x:si", namespace)]
                sheets = sorted(item for item in workbook.namelist() if item.startswith("xl/worksheets/") and item.endswith(".xml"))
                for name in sheets:
                    root = ElementTree.fromstring(workbook.read(name))
                    account_columns = (0, 1)
                    for row in root.findall(".//x:row", namespace):
                        values = []
                        for cell in row.findall("x:c", namespace):
                            value = cell.findtext("x:v", default="", namespaces=namespace)
                            if cell.get("t") == "s" and value.isdigit():
                                value = shared[int(value)] if int(value) < len(shared) else ""
                            elif cell.get("t") == "inlineStr":
                                value = "".join(cell.itertext())
                            if value.strip():
                                values.append(value.strip())
                        if tipo == "plano_contas":
                            headers = [value.lower().replace("ó", "o") for value in values]
                            if "codigo" in headers and "nome" in headers:
                                account_columns = (headers.index("codigo"), headers.index("nome"))
                                continue
                            values = [values[index] for index in account_columns if index < len(values)]
                        if values:
                            rows.append(" - ".join(values))
    # Keep meaningful rows only; account plans commonly begin with a numeric code.
    values = []
    for row in rows:
        text = re.sub(r"\s+", " ", row).strip(" -")
        if len(text) < 2:
            continue
        if tipo == "plano_contas":
            match = re.match(r"^((?:\d+[.\-]?)+)\s*[-: ]\s*(.+)$", text)
            if not match:
                continue
            text = f"{match.group(1)} - {match.group(2)}"
        values.append(text)
    key = "contas" if tipo == "plano_contas" else "historicos"
    return {key: list(dict.fromkeys(values)), "formato": "catalogo_v3"}


@router.get("/documentos-importantes")
def list_important_documents(db: Session = Depends(get_db)):
    return [important_document_payload(item) for item in db.query(DocumentoImportante).order_by(DocumentoImportante.created_at.desc())]


@router.get("/documentos-importantes/catalogo")
def important_document_catalog(db: Session = Depends(get_db)):
    accounts, histories = [], []
    changed = False
    for item in db.query(DocumentoImportante).all():
        if item.catalogo.get("formato") != "catalogo_v3" and Path(item.caminho).is_file():
            try:
                item.catalogo = extract_important_catalog(Path(item.caminho), item.extensao, item.tipo)
                changed = True
            except Exception:
                pass
        for account in item.catalogo.get("contas", []):
            match = re.match(r"^((?:\d+[.\-]?)+)\s*[-: ]\s*(.+)$", re.sub(r"\s+", " ", account).strip(" -"))
            if match:
                accounts.append(f"{match.group(1)} - {match.group(2)}")
        histories.extend(item.catalogo.get("historicos", []))
    if changed:
        db.commit()
    return {"contas": list(dict.fromkeys(accounts)), "historicos": list(dict.fromkeys(histories))}


@router.post("/documentos-importantes")
def upload_important_document(tipo: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    extension = Path(file.filename or "").suffix.lower()
    if tipo not in {"plano_contas", "historicos"}:
        raise HTTPException(422, "Tipo de documento inválido")
    if extension == ".xls":
        raise HTTPException(422, "Arquivos .xls não são suportados. Salve o arquivo como .xlsx e tente novamente.")
    if extension not in {".pdf", ".xlsx"}:
        raise HTTPException(422, "Envie um PDF ou arquivo XLSX")
    destination = UPLOAD_DIR / "documentos_importantes"
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / f"{uuid4()}{extension}"
    with path.open("wb") as output:
        shutil.copyfileobj(file.file, output)
    try:
        catalog = extract_important_catalog(path, extension, tipo)
    except Exception as error:
        path.unlink(missing_ok=True)
        raise HTTPException(422, f"Não foi possível extrair o documento: {error}") from error
    record = DocumentoImportante(tipo=tipo, nome_original=file.filename, caminho=str(path), extensao=extension, catalogo=catalog)
    db.add(record); db.commit(); db.refresh(record)
    return important_document_payload(record)


@router.delete("/documentos-importantes/{documento_id}", status_code=204)
def delete_important_document(documento_id: str, db: Session = Depends(get_db)):
    record = db.get(DocumentoImportante, documento_id)
    if not record:
        raise HTTPException(404, "Documento não encontrado")
    Path(record.caminho).unlink(missing_ok=True)
    db.delete(record); db.commit()


@router.get("/clientes")
def list_clients(db: Session = Depends(get_db)):
    return [{"id": item.id, "nome": item.nome, "documento": item.documento} for item in db.query(Cliente).order_by(Cliente.nome)]


@router.post("/clientes")
def create_client(payload: ClienteInput, db: Session = Depends(get_db)):
    client = Cliente(**payload.model_dump())
    db.add(client); db.commit(); db.refresh(client)
    return {"id": client.id, "nome": client.nome, "documento": client.documento}


@router.patch("/clientes/{cliente_id}")
def update_client(cliente_id: str, payload: ClienteUpdate, db: Session = Depends(get_db)):
    client = db.get(Cliente, cliente_id)
    if not client:
        raise HTTPException(404, "Cliente não encontrado")
    client.nome = payload.nome
    client.documento = payload.documento
    db.commit(); db.refresh(client)
    return {"id": client.id, "nome": client.nome, "documento": client.documento}


@router.delete("/clientes/{cliente_id}", status_code=204)
def delete_client(cliente_id: str, db: Session = Depends(get_db)):
    client = db.get(Cliente, cliente_id)
    if not client:
        raise HTTPException(404, "Cliente não encontrado")
    if db.query(Conciliacao).filter_by(cliente_id=cliente_id).first():
        raise HTTPException(409, "Não é possível excluir cliente com conciliações vinculadas")
    db.delete(client); db.commit()


def reconciliation_payload(item: Conciliacao) -> dict:
    return {"id": item.id, "processo_id": item.processo_id, "banco": item.banco, "status": item.status, "data_inicio": item.data_inicio.isoformat(), "data_fim": item.data_fim.isoformat()}


def process_payload(item: ProcessoConciliacao, db: Session) -> dict:
    client = db.get(Cliente, item.cliente_id)
    reconciliations = db.query(Conciliacao).filter_by(processo_id=item.id).order_by(Conciliacao.created_at).all()
    return {"id": item.id, "cliente_id": item.cliente_id, "cliente_nome": client.nome if client else "Cliente removido", "data_inicio": item.data_inicio.isoformat(), "data_fim": item.data_fim.isoformat(), "criado_em": item.created_at.isoformat(), "status": item.status, "bancos": [reconciliation_payload(reconciliation) for reconciliation in reconciliations]}


@router.get("/processos-conciliacao")
def list_reconciliation_processes(cliente_id: str | None = None, db: Session = Depends(get_db)):
    query = db.query(ProcessoConciliacao)
    if cliente_id:
        query = query.filter_by(cliente_id=cliente_id)
    return [process_payload(item, db) for item in query.order_by(ProcessoConciliacao.updated_at.desc(), ProcessoConciliacao.created_at.desc())]


@router.post("/processos-conciliacao")
def create_reconciliation_process(payload: ProcessoConciliacaoInput, db: Session = Depends(get_db)):
    if not db.get(Cliente, payload.cliente_id) or payload.data_inicio > payload.data_fim:
        raise HTTPException(422, "Cliente ou período inválido")
    if payload.banco and payload.banco not in BANKS:
        raise HTTPException(422, "Banco inválido")
    process = ProcessoConciliacao(cliente_id=payload.cliente_id, data_inicio=payload.data_inicio, data_fim=payload.data_fim)
    db.add(process); db.flush()
    if payload.banco:
        db.add(Conciliacao(cliente_id=process.cliente_id, processo_id=process.id, banco=payload.banco, data_inicio=process.data_inicio, data_fim=process.data_fim))
    db.commit(); db.refresh(process)
    return process_payload(process, db)


@router.get("/processos-conciliacao/{processo_id}")
def get_reconciliation_process(processo_id: str, db: Session = Depends(get_db)):
    process = db.get(ProcessoConciliacao, processo_id)
    if not process:
        raise HTTPException(404, "Processo de conciliação não encontrado")
    return process_payload(process, db)


@router.delete("/processos-conciliacao/{processo_id}", status_code=204)
def delete_reconciliation_process(processo_id: str, db: Session = Depends(get_db)):
    process = db.get(ProcessoConciliacao, processo_id)
    if not process:
        raise HTTPException(404, "Processo de conciliação não encontrado")
    reconciliations = db.query(Conciliacao).filter_by(processo_id=process.id).all()
    for reconciliation in reconciliations:
        matches = db.query(Correspondencia).filter_by(conciliacao_id=reconciliation.id).all()
        for match in matches:
            db.query(LancamentoContabil).filter_by(correspondencia_id=match.id).delete()
        db.query(Correspondencia).filter_by(conciliacao_id=reconciliation.id).delete()
        receipts = db.query(ComprovanteRfb).filter_by(conciliacao_id=reconciliation.id).all()
        for receipt in receipts:
            db.query(ComprovanteRfbItem).filter_by(comprovante_rfb_id=receipt.id).delete()
        db.query(ComprovanteRfb).filter_by(conciliacao_id=reconciliation.id).delete()
        db.query(MovimentoExtrato).filter_by(conciliacao_id=reconciliation.id).delete()
        db.query(Comprovante).filter_by(conciliacao_id=reconciliation.id).delete()
        db.query(NotaFiscal).filter_by(conciliacao_id=reconciliation.id).delete()
        files = db.query(Arquivo).filter_by(conciliacao_id=reconciliation.id).all()
        for file in files:
            Path(file.caminho).unlink(missing_ok=True)
            db.delete(file)
        db.delete(reconciliation)
    db.delete(process)
    db.commit()


@router.post("/processos-conciliacao/{processo_id}/bancos")
def resume_process_bank(processo_id: str, payload: ProcessoBancoInput, db: Session = Depends(get_db)):
    process = db.get(ProcessoConciliacao, processo_id)
    if not process:
        raise HTTPException(404, "Processo de conciliação não encontrado")
    if payload.banco not in BANKS:
        raise HTTPException(422, "Banco inválido")
    reconciliation = db.query(Conciliacao).filter_by(processo_id=process.id, banco=payload.banco).first()
    if not reconciliation:
        reconciliation = Conciliacao(cliente_id=process.cliente_id, processo_id=process.id, banco=payload.banco, data_inicio=process.data_inicio, data_fim=process.data_fim)
        process.status = "em_andamento"
        db.add(reconciliation); db.commit(); db.refresh(reconciliation)
    return reconciliation_payload(reconciliation)


@router.post("/conciliacoes")
def create_reconciliation(payload: ConciliacaoInput, db: Session = Depends(get_db)):
    if payload.banco not in BANKS or not db.get(Cliente, payload.cliente_id):
        raise HTTPException(422, "Cliente ou banco inválido")
    process = ProcessoConciliacao(cliente_id=payload.cliente_id, data_inicio=payload.data_inicio, data_fim=payload.data_fim)
    db.add(process); db.flush()
    item = Conciliacao(**payload.model_dump(), processo_id=process.id)
    db.add(item); db.commit(); db.refresh(item)
    return reconciliation_payload(item)


def rule_matches_movement(rule: RegraContabil, movement: MovimentoExtrato, counterparty: str = "", component: str = "") -> bool:
    trigger = normalize_name(rule.favorecido_normalizado)
    history = normalize_name(" ".join(item for item in [movement.historico, movement.nome_encontrado, counterparty] if item))
    component_matches = not component or (rule.tipo_componente == component if rule.tipo_componente else component in {"PRINCIPAL", "VALOR_COBRADO"})
    return bool(trigger and trigger in history and (not rule.tipo_operacao or normalize_rule_accounting_nature(rule.tipo_operacao) == accounting_nature(movement.natureza)) and component_matches)


def in_reconciliation_period(reconciliation: Conciliacao, movement: MovimentoExtrato) -> bool:
    return bool(movement.data and reconciliation.data_inicio <= movement.data <= reconciliation.data_fim)


def receipt_matches_movement(movement_text: str, beneficiary: str) -> bool:
    text_tokens = normalize_name(movement_text).split()
    beneficiary_tokens = normalize_name(beneficiary).split()
    if not text_tokens or not beneficiary_tokens:
        return False
    if names_similar(movement_text, beneficiary, allow_truncated_terminal=True):
        return True
    # A statement history begins with the operation name, while the beneficiary appears later.
    return len(beneficiary_tokens) >= 2 and all(any(token.startswith(candidate) or candidate.startswith(token) for token in text_tokens) for candidate in beneficiary_tokens)


def receipt_match_criterion(movement_text: str, receipt: Comprovante) -> str:
    for field, label in ((receipt.beneficiario or receipt.favorecido, "beneficiário"), (receipt.beneficiario_final, "beneficiário final"), (receipt.nome_fantasia, "nome fantasia")):
        if field and receipt_matches_movement(movement_text, field):
            return label
    return ""


def receipt_operation_matches(movement: MovimentoExtrato, receipt: Comprovante) -> bool:
    history, operation = normalize_name(movement.historico), normalize_name(receipt.tipo_operacao)
    if "PIX" in history:
        return "PIX" in operation
    if any(term in history for term in ("TRANSFERENCIA", "TED", "DOC")):
        return any(term in operation for term in ("TRANSFERENCIA", "TED", "DOC"))
    return True


def receipt_time_matches(movement: MovimentoExtrato, receipt: Comprovante) -> bool:
    return not movement.hora or not receipt.hora or movement.hora[:5] == receipt.hora[:5]


def receipt_tariff_date_matches(movement: MovimentoExtrato, receipt: Comprovante) -> bool:
    occurrence = re.search(r"ocorr[êe]ncia\s+(\d{2}/\d{2}/\d{4})", movement.nome_encontrado, re.I)
    if occurrence:
        return bool(receipt.data and receipt.data.strftime("%d/%m/%Y") == occurrence.group(1))
    return movement.data == receipt.data


def is_transfer_without_counterparty(movement: MovimentoExtrato) -> bool:
    history = normalize_name(movement.historico)
    name = normalize_name(movement.nome_encontrado)
    return bool(any(term in history for term in ("TRANSFERENCIA", "TED", "DOC")) and (not name or re.fullmatch(r"\d{2} \d{2}", name)))


def rule_payload(rule: RegraContabil, movements: list[MovimentoExtrato]) -> dict:
    covered = [item for item in movements if rule_matches_movement(rule, item)]
    return {"id": rule.id, "gatilho": rule.favorecido_normalizado, "natureza": normalize_rule_accounting_nature(rule.tipo_operacao), "tipo_componente": rule.tipo_componente, "conta_debito": rule.conta_debito, "conta_credito": rule.conta_credito, "historico": rule.historico, "complemento": rule.complemento, "banco_origem": rule.banco, "cobertos": len(covered), "movimentos": [{"data": item.data.strftime("%d/%m/%Y") if item.data else "—", "historico": " ".join(part for part in [item.historico, item.nome_encontrado] if part), "valor": str(item.valor or 0), "natureza": normalize_statement_nature(item.natureza), "natureza_contabil": accounting_nature(item.natureza)} for item in covered]}


def scoped_rules(reconciliation: Conciliacao, db: Session) -> list[RegraContabil]:
    return db.query(RegraContabil).filter_by(cliente_id=reconciliation.cliente_id, tipo_fonte="extrato", ativo=True).order_by(RegraContabil.created_at.desc()).all()


def scoped_reconciliations(reconciliation: Conciliacao, db: Session) -> list[Conciliacao]:
    return db.query(Conciliacao).filter_by(cliente_id=reconciliation.cliente_id).all()


def apply_accounting_rules(reconciliation: Conciliacao, db: Session) -> int:
    """Create or update accounting entries without changing document matching links."""
    rules = scoped_rules(reconciliation, db)
    applied = 0
    movements = [item for item in db.query(MovimentoExtrato).filter_by(conciliacao_id=reconciliation.id, ativo=True) if in_reconciliation_period(reconciliation, item)]
    for movement in movements:
        match = db.query(Correspondencia).filter_by(conciliacao_id=reconciliation.id, movimento_extrato_id=movement.id).first()
        receipt = db.get(Comprovante, match.comprovante_id) if match and match.comprovante_id else None
        counterparty = receipt.beneficiario_final or receipt.beneficiario or receipt.favorecido if receipt else ""
        if not match:
            match = Correspondencia(conciliacao_id=reconciliation.id, movimento_extrato_id=movement.id)
            db.add(match)
            db.flush()
        entries = db.query(LancamentoContabil).filter_by(correspondencia_id=match.id).all()
        # A document can have distinct rules for principal, discount, and taxes.
        # Manual entries are deliberately never overwritten by a rule refresh.
        source_entries = [entry for entry in entries if entry.status != "editado_manual"]
        if not source_entries:
            source_entries = [LancamentoContabil(correspondencia_id=match.id, componente="PRINCIPAL", categoria="PRINCIPAL", valor=movement.valor or 0, origem="extrato", ordem=1)]
            db.add(source_entries[0])
        applied_rule = None
        for entry in source_entries:
            rule = next((item for item in rules if rule_matches_movement(item, movement, counterparty, entry.componente)), None)
            if not rule:
                continue
            entry.regra_contabil_id = rule.id
            entry.conta_debito = rule.conta_debito
            entry.conta_credito = rule.conta_credito
            entry.historico = rule.historico
            entry.status = "aplicado_por_regra"
            applied_rule = rule
            applied += 1
        match.regra_contabil_id = applied_rule.id if applied_rule else None
    return applied


def reconciliation_or_404(conciliacao_id: str, db: Session) -> Conciliacao:
    reconciliation = db.get(Conciliacao, conciliacao_id)
    if not reconciliation:
        raise HTTPException(404, "Conciliação não encontrada")
    return reconciliation


@router.get("/conciliacoes/{conciliacao_id}/conta-bancaria")
def bank_account(conciliacao_id: str, db: Session = Depends(get_db)):
    reconciliation = reconciliation_or_404(conciliacao_id, db)
    account = db.query(ContaBancaria).filter_by(cliente_id=reconciliation.cliente_id, banco=reconciliation.banco).first()
    return {"conta_contabil": account.conta_contabil if account else ""}


@router.put("/conciliacoes/{conciliacao_id}/conta-bancaria")
def save_bank_account(conciliacao_id: str, payload: ContaBancariaInput, db: Session = Depends(get_db)):
    reconciliation = reconciliation_or_404(conciliacao_id, db)
    account = db.query(ContaBancaria).filter_by(cliente_id=reconciliation.cliente_id, banco=reconciliation.banco).first()
    if not account:
        account = ContaBancaria(cliente_id=reconciliation.cliente_id, banco=reconciliation.banco)
        db.add(account)
    account.conta_contabil = payload.conta_contabil.strip()
    db.commit()
    return {"conta_contabil": account.conta_contabil}


@router.get("/conciliacoes/{conciliacao_id}/regras-contabeis")
def accounting_rules(conciliacao_id: str, db: Session = Depends(get_db)):
    reconciliation = reconciliation_or_404(conciliacao_id, db)
    movements = [item for item in db.query(MovimentoExtrato).filter_by(conciliacao_id=conciliacao_id, ativo=True).order_by(MovimentoExtrato.data, MovimentoExtrato.hora) if in_reconciliation_period(reconciliation, item)]
    if reconciliation.banco == "Banco do Brasil":
        for movement in movements:
            logger.info("Total do extrato BB: data=%s historico=%s valor=%s natureza=%s", movement.data, movement.historico, movement.valor, movement.natureza)
    rules = scoped_rules(reconciliation, db)
    same_bank_rules = [rule for rule in rules if rule.banco == reconciliation.banco]
    applied_movements = [item for item in movements if any(rule_matches_movement(rule, item) for rule in rules)]
    matches = {item.movimento_extrato_id: item for item in db.query(Correspondencia).filter_by(conciliacao_id=conciliacao_id).all()}
    def pending_payload(item: MovimentoExtrato, component: str = "PRINCIPAL", value: Decimal | None = None):
        match = matches.get(item.id)
        receipt = db.get(Comprovante, match.comprovante_id) if match and match.comprovante_id else None
        rfb = db.get(ComprovanteRfb, match.comprovante_rfb_id) if match and match.comprovante_rfb_id else None
        history = " ".join(part for part in [item.historico, item.nome_encontrado] if part)
        if receipt and receipt.beneficiario_final:
            if receipt.beneficiario and receipt.beneficiario.lower() in history.lower():
                history = re.sub(re.escape(receipt.beneficiario), receipt.beneficiario_final, history, flags=re.I)
            else:
                history = f"{item.historico} {receipt.beneficiario_final}".strip()
        shared_rule = next((rule for rule in rules if rule.banco != reconciliation.banco and rule_matches_movement(rule, item, component=component)), None)
        tariff_in_statement = bool(receipt and receipt.valor_tarifa and "TARIFA PIX" not in normalize_name(item.historico) and any(other.comprovante_id == receipt.id and other.movimento_extrato_id != item.id and "TARIFA PIX" in normalize_name(db.get(MovimentoExtrato, other.movimento_extrato_id).historico) for other in matches.values()))
        tariff_reference = bool(receipt and "TARIFA PIX" in normalize_name(item.historico))
        composition = ""
        if rfb and (rfb.tipo.upper() == "DAS" or any("SIMPLES NACIONAL" in tax.descricao.upper() for tax in db.query(ComprovanteRfbItem).filter_by(comprovante_rfb_id=rfb.id))):
            taxes = db.query(ComprovanteRfbItem).filter_by(comprovante_rfb_id=rfb.id).all()
            money = lambda amount: f"R$ {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            lines = [f"{tax.descricao.split(' - ')[0]}: {money(tax.valor_principal or 0)}" for tax in taxes if tax.valor_principal]
            if rfb.valor_multa: lines.append(f"Multa: {money(rfb.valor_multa)}")
            if rfb.valor_juros: lines.append(f"Juros: {money(rfb.valor_juros)}")
            composition = "Composição:\n- " + "\n- ".join(lines) + f"\nTotal do documento: {money(rfb.valor_total or 0)}"
        return {"id": f"{item.id}:{component}", "data": item.data.strftime("%d/%m/%y") if item.data else "—", "historico": history, "valor": str(value if value is not None else item.valor or 0), "natureza": normalize_statement_nature(item.natureza), "natureza_contabil": accounting_nature(item.natureza), "tipo_componente": component, "valor_documento": str(receipt.valor_original) if receipt and receipt.valor_original else "", "composicao_simples": composition, "tarifa_no_extrato": tariff_in_statement, "tarifa_referente_ao_comprovante": tariff_reference, "tarifa_referencia_nome": (receipt.beneficiario or receipt.favorecido) if tariff_reference else "", "tarifa_referencia_valor": str(receipt.valor_pago or 0) if tariff_reference else "", "tarifa_referencia_data": receipt.data.strftime("%d/%m/%Y") if tariff_reference and receipt.data else "", "pagina": item.pagina_numero, "arquivo_id": item.arquivo_id, "comprovante_arquivo_id": receipt.arquivo_id if receipt else None, "comprovante_pagina": receipt.pagina_numero if receipt else None, "comprovante_confere": bool(receipt and match and match.status.startswith("Conciliado")), "regra_compartilhada": {"id": shared_rule.id, "banco_origem": shared_rule.banco, "gatilho": shared_rule.favorecido_normalizado} if shared_rule else None}
    pending = []
    for movement in movements:
        match = matches.get(movement.id)
        items = db.query(LancamentoContabil).filter_by(correspondencia_id=match.id).all() if match else []
        candidates = [(entry.componente, entry.valor) for entry in items] or [("PRINCIPAL", movement.valor)]
        pending.extend(pending_payload(movement, component, value) for component, value in candidates if not any(rule_matches_movement(rule, movement, component=component) for rule in same_bank_rules))
    reason_debit = sum((item.valor or 0 for item in applied_movements if accounting_nature(item.natureza) == "Débito"), 0)
    reason_credit = sum((item.valor or 0 for item in applied_movements if accounting_nature(item.natureza) == "Crédito"), 0)
    return {"pendentes": pending, "salvas": [rule_payload(rule, movements) for rule in same_bank_rules], "resumo": {"extrato": {"debito": str(sum((item.valor or 0 for item in movements if is_statement_debit(item.natureza)), 0)), "credito": str(sum((item.valor or 0 for item in movements if not is_statement_debit(item.natureza)), 0))}, "razao": {"debito": str(reason_debit), "credito": str(reason_credit)}}}


@router.post("/conciliacoes/{conciliacao_id}/regras-contabeis")
def create_accounting_rule(conciliacao_id: str, payload: RegraContabilInput, db: Session = Depends(get_db)):
    reconciliation = reconciliation_or_404(conciliacao_id, db)
    if not all([payload.gatilho.strip(), payload.conta_debito.strip(), payload.conta_credito.strip(), payload.historico.strip()]):
        raise HTTPException(422, "Preencha gatilho, débito, crédito e histórico")
    shared_rule = next((item for item in scoped_rules(reconciliation, db) if item.banco != reconciliation.banco and item.tipo_operacao == payload.natureza and item.tipo_componente == payload.tipo_componente.strip().upper() and normalize_name(item.favorecido_normalizado) == normalize_name(payload.gatilho)), None)
    if shared_rule:
        raise HTTPException(409, f"Já existe uma regra deste cliente criada no banco {shared_rule.banco}")
    rule = RegraContabil(cliente_id=reconciliation.cliente_id, banco=reconciliation.banco, tipo_fonte="extrato", tipo_operacao=payload.natureza, tipo_componente=payload.tipo_componente.strip().upper(), favorecido_normalizado=normalize_name(payload.gatilho), conta_debito=payload.conta_debito.strip(), conta_credito=payload.conta_credito.strip(), historico=payload.historico.strip(), complemento=payload.complemento.strip())
    db.add(rule); db.flush()
    applied = sum(apply_accounting_rules(item, db) for item in scoped_reconciliations(reconciliation, db))
    db.commit(); db.refresh(rule)
    return {"id": rule.id, "movimentos_aplicados": applied}


@router.patch("/conciliacoes/{conciliacao_id}/regras-contabeis/{regra_id}")
def update_accounting_rule(conciliacao_id: str, regra_id: str, payload: RegraContabilInput, db: Session = Depends(get_db)):
    reconciliation = reconciliation_or_404(conciliacao_id, db)
    rule = db.get(RegraContabil, regra_id)
    if not rule or rule.cliente_id != reconciliation.cliente_id or rule.banco != reconciliation.banco or not rule.ativo:
        raise HTTPException(404, "Regra não encontrada")
    if not all([payload.gatilho.strip(), payload.conta_debito.strip(), payload.conta_credito.strip(), payload.historico.strip()]):
        raise HTTPException(422, "Preencha gatilho, débito, crédito e histórico")
    rule.tipo_operacao = payload.natureza
    rule.tipo_componente = payload.tipo_componente.strip().upper()
    rule.favorecido_normalizado = normalize_name(payload.gatilho)
    rule.conta_debito = payload.conta_debito.strip()
    rule.conta_credito = payload.conta_credito.strip()
    rule.historico = payload.historico.strip()
    rule.complemento = payload.complemento.strip()
    db.query(LancamentoContabil).filter_by(regra_contabil_id=rule.id).delete()
    apply_accounting_rules(reconciliation, db)
    for item in scoped_reconciliations(reconciliation, db):
        if item.id != reconciliation.id:
            apply_accounting_rules(item, db)
    db.commit()
    return {"id": rule.id}


@router.delete("/regras-contabeis/{regra_id}", status_code=204)
def delete_accounting_rule(regra_id: str, db: Session = Depends(get_db)):
    rule = db.get(RegraContabil, regra_id)
    if not rule:
        raise HTTPException(404, "Regra não encontrada")
    rule.ativo = False
    db.query(LancamentoContabil).filter_by(regra_contabil_id=rule.id).delete()
    for match in db.query(Correspondencia).filter_by(regra_contabil_id=rule.id):
        match.regra_contabil_id = None
    for reconciliation in db.query(Conciliacao).filter_by(cliente_id=rule.cliente_id):
        apply_accounting_rules(reconciliation, db)
    db.commit()


@router.get("/conciliacoes/{conciliacao_id}/lancamentos-contabeis.csv")
def accounting_csv(conciliacao_id: str, db: Session = Depends(get_db)):
    reconciliation = reconciliation_or_404(conciliacao_id, db)
    account = db.query(ContaBancaria).filter_by(cliente_id=reconciliation.cliente_id, banco=reconciliation.banco).first()
    if not account or not account.conta_contabil.strip():
        raise HTTPException(422, "Informe a conta deste banco no plano de contas antes de gerar o CSV")
    rules = scoped_rules(reconciliation, db)
    movements = [item for item in db.query(MovimentoExtrato).filter_by(conciliacao_id=conciliacao_id, ativo=True).order_by(MovimentoExtrato.data, MovimentoExtrato.hora) if in_reconciliation_period(reconciliation, item)]
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter=";", lineterminator="\n")
    writer.writerow(["data", "debito", "credito", "historico", "complemento", "valor"])
    for movement in movements:
        rule = next((item for item in rules if rule_matches_movement(item, movement)), None)
        if rule:
            writer.writerow([movement.data.strftime("%d/%m/%Y") if movement.data else "", rule.conta_debito, rule.conta_credito, rule.historico, rule.complemento, f"{movement.valor or 0:.2f}".replace(".", ",")])
    return Response(output.getvalue().encode("utf-8-sig"), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="lancamentos-contabeis.csv"'})


@router.post("/conciliacoes/{conciliacao_id}/arquivos")
def upload(conciliacao_id: str, tipo_documento: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    if tipo_documento not in {"extrato", "comprovante", "rfb"} or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(422, "Envie um PDF com tipo de documento válido")
    reconciliation = db.get(Conciliacao, conciliacao_id)
    if not reconciliation:
        raise HTTPException(404, "Conciliação não encontrada")
    reset_reconciliation(conciliacao_id, db)
    destination = UPLOAD_DIR / conciliacao_id
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / f"{uuid4()}.pdf"
    with path.open("wb") as output:
        shutil.copyfileobj(file.file, output)
    record = Arquivo(conciliacao_id=conciliacao_id, tipo_documento=tipo_documento, banco_selecionado=reconciliation.banco, nome_original=file.filename, caminho=str(path))
    db.add(record); db.commit(); db.refresh(record)
    try:
        document = fitz.open(path)
        pages = [page.get_text() for page in document]
        record.texto_bruto = "\n\f\n".join(pages); record.paginas = len(pages)
        extracted = []
        for number, page_text in enumerate(pages, 1):
            parsed_rfb = parse_rfb_page(page_text, number) if tipo_documento == "rfb" else None
            extracted.extend([parsed_rfb] if parsed_rfb else [] if tipo_documento == "rfb" else extract_receipts(page_text, number) if tipo_documento == "comprovante" else extract_statement(page_text, number, reconciliation.banco))
        if tipo_documento == "extrato" and reconciliation.banco == "Banco do Brasil":
            extracted = deduplicate_statement_records(extracted)
        for item in extracted:
            if tipo_documento == "rfb":
                receipt = ComprovanteRfb(conciliacao_id=conciliacao_id, arquivo_id=record.id, pagina_numero=item.pagina_numero, tipo=item.tipo, cnpj=item.cnpj, razao_social=item.razao_social, competencia=item.competencia, periodo_apuracao=item.periodo_apuracao, data_vencimento=item.data_vencimento, data_arrecadacao=item.data_arrecadacao, numero_documento=item.numero_documento, codigo_banco=item.codigo_banco, nome_banco=item.nome_banco, agencia=item.agencia, valor_principal=item.valor_principal, valor_multa=item.valor_multa, valor_juros=item.valor_juros, valor_total=item.valor_total, texto_original=item.texto_original, status="composição divergente" if item.composicao_divergente else "pronto")
                db.add(receipt); db.flush()
                for tax in item.itens:
                    db.add(ComprovanteRfbItem(comprovante_rfb_id=receipt.id, codigo=tax.codigo, descricao=tax.descricao, valor_principal=tax.valor_principal, valor_multa=tax.valor_multa, valor_juros=tax.valor_juros, valor_total=tax.valor_total))
                continue
            common = dict(conciliacao_id=conciliacao_id, arquivo_id=record.id, pagina_numero=item.pagina_numero, texto_original=item.texto_original, dados_originais={"origem_nome": item.origem_nome} if tipo_documento == "comprovante" else {}, dados_normalizados={"nome": normalize_name(item.favorecido if tipo_documento == "comprovante" else item.nome)})
            if tipo_documento == "comprovante":
                common.update(beneficiario=item.beneficiario or item.favorecido, nome_fantasia=item.nome_fantasia, beneficiario_final=item.beneficiario_final, pagador=item.pagador, cnpj_beneficiario=item.cnpj_beneficiario, cnpj_beneficiario_final=item.cnpj_beneficiario_final)
            db.add(Comprovante(**common, data=item.data, hora=item.hora, favorecido=item.favorecido, valor=item.financeiros.valor_pago, valor_original=item.financeiros.valor_original, valor_desconto=item.financeiros.valor_desconto, valor_abatimento=item.financeiros.valor_abatimento, valor_desconto_abatimento=item.financeiros.valor_desconto_abatimento, valor_juros=item.financeiros.valor_juros, valor_multa=item.financeiros.valor_multa, valor_encargos=item.financeiros.valor_encargos, valor_tarifa=item.financeiros.valor_tarifa, valor_pago=item.financeiros.valor_pago, detalhes_financeiros=item.financeiros.detalhes, status_revisao="revisao" if item.financeiros.composicao_divergente else "valido", tipo_operacao=item.tipo_operacao) if tipo_documento == "comprovante" else MovimentoExtrato(**common, data=item.data, hora=item.hora, historico=item.historico, nome_encontrado=item.nome, valor=item.valor, natureza=item.natureza, data_origem=item.data_origem))
        record.status_processamento = "concluido"
    except Exception as error:
        record.status_processamento = "erro"; record.mensagem_erro = str(error)
    db.commit()
    return {"id": record.id, "status": record.status_processamento}


def clear_reconciliation_results(conciliacao_id: str, db: Session) -> None:
    matches = db.query(Correspondencia).filter_by(conciliacao_id=conciliacao_id).all()
    for match in matches:
        db.query(LancamentoContabil).filter_by(correspondencia_id=match.id).delete()
    db.query(Correspondencia).filter_by(conciliacao_id=conciliacao_id).delete()


def sync_document_items(match: Correspondencia, lines, db: Session) -> None:
    """Refresh source-derived components without replacing user edits."""
    existing = db.query(LancamentoContabil).filter_by(correspondencia_id=match.id).all()
    if any(item.status == "editado_manual" for item in existing):
        return
    automatic = [item for item in existing if item.status != "editado_manual"]
    by_key = {(item.origem, item.componente, item.codigo_receita, item.descricao): item for item in automatic}
    expected = set()
    for order, line in enumerate(lines, 1):
        key = (line.origem, line.componente, line.codigo_receita, line.descricao)
        expected.add(key)
        item = by_key.get(key)
        if not item:
            item = LancamentoContabil(correspondencia_id=match.id, origem=line.origem)
            db.add(item)
        item.componente = line.componente
        item.categoria = line.componente
        item.codigo_receita = line.codigo_receita
        item.descricao = line.descricao
        item.tributo = line.descricao if line.origem == "rfb" else ""
        item.valor = line.valor
        item.efeito_no_total = line.efeito_no_total
        item.ordem = order
        item.historico = item.historico or line.descricao
        item.status = "pendente_regra"
    for item in automatic:
        key = (item.origem, item.componente, item.codigo_receita, item.descricao)
        if key not in expected:
            db.delete(item)


def reset_reconciliation(conciliacao_id: str, db: Session) -> None:
    clear_reconciliation_results(conciliacao_id, db)
    reconciliation = db.get(Conciliacao, conciliacao_id)
    if not reconciliation:
        return
    reconciliation.status = "rascunho"
    if reconciliation.processo_id:
        process = db.get(ProcessoConciliacao, reconciliation.processo_id)
        if process:
            process.status = "em_andamento"


@router.post("/arquivos/{arquivo_id}/reprocessar")
def reprocess_document(arquivo_id: str, db: Session = Depends(get_db)):
    record = db.get(Arquivo, arquivo_id)
    if not record or record.tipo_documento not in {"extrato", "comprovante", "rfb"}:
        raise HTTPException(404, "Documento reprocessável não encontrado")
    reset_reconciliation(record.conciliacao_id, db)
    model = MovimentoExtrato if record.tipo_documento == "extrato" else Comprovante if record.tipo_documento == "comprovante" else ComprovanteRfb
    db.query(model).filter_by(arquivo_id=record.id).delete()
    extracted = []
    for number, page_text in enumerate((record.texto_bruto or "").split("\n\f\n"), 1):
        parsed_rfb = parse_rfb_page(page_text, number) if record.tipo_documento == "rfb" else None
        extracted.extend([parsed_rfb] if parsed_rfb else [] if record.tipo_documento == "rfb" else extract_statement(page_text, number, record.banco_selecionado) if record.tipo_documento == "extrato" else extract_receipts(page_text, number))
    if record.tipo_documento == "extrato" and record.banco_selecionado == "Banco do Brasil":
        extracted = deduplicate_statement_records(extracted)
    for item in extracted:
        if record.tipo_documento == "rfb":
            receipt = ComprovanteRfb(conciliacao_id=record.conciliacao_id, arquivo_id=record.id, pagina_numero=item.pagina_numero, tipo=item.tipo, cnpj=item.cnpj, razao_social=item.razao_social, competencia=item.competencia, periodo_apuracao=item.periodo_apuracao, data_vencimento=item.data_vencimento, data_arrecadacao=item.data_arrecadacao, numero_documento=item.numero_documento, codigo_banco=item.codigo_banco, nome_banco=item.nome_banco, agencia=item.agencia, valor_principal=item.valor_principal, valor_multa=item.valor_multa, valor_juros=item.valor_juros, valor_total=item.valor_total, texto_original=item.texto_original, status="composição divergente" if item.composicao_divergente else "pronto")
            db.add(receipt); db.flush()
            for tax in item.itens:
                db.add(ComprovanteRfbItem(comprovante_rfb_id=receipt.id, codigo=tax.codigo, descricao=tax.descricao, valor_principal=tax.valor_principal, valor_multa=tax.valor_multa, valor_juros=tax.valor_juros, valor_total=tax.valor_total))
            continue
        common = dict(conciliacao_id=record.conciliacao_id, arquivo_id=record.id, pagina_numero=item.pagina_numero, texto_original=item.texto_original, dados_originais={"origem_nome": item.origem_nome} if record.tipo_documento == "comprovante" else {}, dados_normalizados={"nome": normalize_name(item.nome if record.tipo_documento == "extrato" else item.favorecido)})
        if record.tipo_documento == "comprovante":
            common.update(beneficiario=item.beneficiario or item.favorecido, nome_fantasia=item.nome_fantasia, beneficiario_final=item.beneficiario_final, pagador=item.pagador, cnpj_beneficiario=item.cnpj_beneficiario, cnpj_beneficiario_final=item.cnpj_beneficiario_final)
        db.add(MovimentoExtrato(**common, data=item.data, hora=item.hora, historico=item.historico, nome_encontrado=item.nome, valor=item.valor, natureza=item.natureza, data_origem=item.data_origem) if record.tipo_documento == "extrato" else Comprovante(**common, data=item.data, hora=item.hora, favorecido=item.favorecido, valor=item.financeiros.valor_pago, valor_original=item.financeiros.valor_original, valor_desconto=item.financeiros.valor_desconto, valor_abatimento=item.financeiros.valor_abatimento, valor_desconto_abatimento=item.financeiros.valor_desconto_abatimento, valor_juros=item.financeiros.valor_juros, valor_multa=item.financeiros.valor_multa, valor_encargos=item.financeiros.valor_encargos, valor_tarifa=item.financeiros.valor_tarifa, valor_pago=item.financeiros.valor_pago, detalhes_financeiros=item.financeiros.detalhes, status_revisao="revisao" if item.financeiros.composicao_divergente else "valido", tipo_operacao=item.tipo_operacao))
    record.status_processamento = "concluido"
    record.mensagem_erro = None
    db.commit()
    return {"registros_extraidos": len(extracted), "status": record.status_processamento}


@router.post("/conciliacoes/{conciliacao_id}/conciliar")
def reconcile(conciliacao_id: str, db: Session = Depends(get_db)):
    reconciliation = db.get(Conciliacao, conciliacao_id)
    if not reconciliation:
        raise HTTPException(404, "Conciliação não encontrada")
    receipts = db.query(Comprovante).filter_by(conciliacao_id=conciliacao_id, ativo=True).all()
    rfb_receipts = [item for item in db.query(ComprovanteRfb).filter_by(conciliacao_id=conciliacao_id) if belongs_to_selected_bank(item, reconciliation.banco)]
    existing_matches = {item.movimento_extrato_id: item for item in db.query(Correspondencia).filter_by(conciliacao_id=conciliacao_id).all()}
    used_receipts, used_rfb = set(), set()
    movements = [item for item in db.query(MovimentoExtrato).filter_by(conciliacao_id=conciliacao_id, ativo=True).order_by(MovimentoExtrato.data, MovimentoExtrato.hora) if is_statement_debit(item.natureza) and in_reconciliation_period(reconciliation, item)]
    for movement in movements:
        # The extracted counterparty is more precise than the operation history.
        movement_text = movement.nome_encontrado or movement.historico
        tariff = "TARIFA PIX" in normalize_name(movement.historico)
        receipt_candidates = [(item, "tarifa do comprovante") for item in receipts if tariff and item.valor_tarifa == movement.valor and receipt_tariff_date_matches(movement, item)]
        if not tariff:
            receipt_candidates = [(item, receipt_match_criterion(movement_text, item)) for item in receipts if item.id not in used_receipts and item.valor_pago == movement.valor and item.data == movement.data and receipt_operation_matches(movement, item) and receipt_time_matches(movement, item)]
        receipt_candidates = [(item, criterion) for item, criterion in receipt_candidates if criterion]
        if not receipt_candidates and is_transfer_without_counterparty(movement):
            transfer_candidates = [item for item in receipts if item.id not in used_receipts and item.valor_pago == movement.valor and item.data == movement.data and "TRANSFER" in normalize_name(item.tipo_operacao)]
            if len(transfer_candidates) == 1:
                receipt_candidates = [(transfer_candidates[0], "data, valor e tipo transferência")]
        receipt, criterion = receipt_candidates[0] if receipt_candidates else (None, "")
        rfb = next((item for item in rfb_receipts if item.id not in used_rfb and item.valor_total == movement.valor and item.data_arrecadacao == movement.data), None)
        source_rfb = None
        if rfb:
            items = db.query(ComprovanteRfbItem).filter_by(comprovante_rfb_id=rfb.id).all()
            source_rfb = SimpleNamespace(tipo=rfb.tipo, valor_principal=rfb.valor_principal, valor_multa=rfb.valor_multa, valor_juros=rfb.valor_juros, valor_total=rfb.valor_total, itens=items)
        decision = choose_rule_source(movement.valor, receipt, source_rfb, tariff=tariff)
        match = existing_matches.get(movement.id)
        if not match:
            match = Correspondencia(conciliacao_id=conciliacao_id, movimento_extrato_id=movement.id)
            db.add(match); db.flush()
        match.comprovante_id = receipt.id if receipt else None
        match.comprovante_rfb_id = rfb.id if rfb else None
        match.fonte_regra = decision.fonte_regra
        match.confianca = "alta" if not decision.exige_revisao else "média"
        match.criterio_correspondencia = f"Correspondência pelo {criterion}" if criterion else ""
        match.status = decision.status
        sync_document_items(match, decision.linhas, db)
        if receipt and not tariff: used_receipts.add(receipt.id)
        if rfb: used_rfb.add(rfb.id)
    apply_accounting_rules(reconciliation, db)
    reconciliation.status = "concluido"
    if reconciliation.processo_id:
        process = db.get(ProcessoConciliacao, reconciliation.processo_id)
        if process:
            process.status = "concluido" if all(item.status == "concluido" for item in db.query(Conciliacao).filter_by(processo_id=process.id)) else "em_andamento"
    db.commit()
    return {"conciliacoes_geradas": len(movements), "resultados": result(conciliacao_id, db)}


@router.get("/conciliacoes/{conciliacao_id}/resultado")
def result(conciliacao_id: str, db: Session = Depends(get_db)):
    matches = db.query(Correspondencia).filter_by(conciliacao_id=conciliacao_id).all()
    rows = []
    def money(value):
        if value is None: return "—"
        integer, decimal = f"{value:.2f}".split(".")
        return f"R$ {int(integer):,}".replace(",", ".") + f",{decimal}"
    def payment_type(history):
        text = history.upper()
        if "TARIFA" in text: return "Tarifa"
        if "COBRANÇA" in text: return "Cobrança"
        if "SEG CRÉD" in text or "SEGURO" in text: return "Seguro"
        if "RENDE FÁCIL" in text or "RENDIMENTO" in text: return "Rendimento"
        if "PIX" in text: return "PIX"
        if "TED" in text or "TRANSFERÊNCIA" in text: return "Transferência"
        if "BOLETO" in text: return "Boleto"
        if "IMPOSTO" in text or "DAS" in text: return "Imposto"
        if "CARTÃO" in text: return "Cartão"
        return "Outro"
    for match in matches:
        movement, receipt, rfb = db.get(MovimentoExtrato, match.movimento_extrato_id), db.get(Comprovante, match.comprovante_id) if match.comprovante_id else None, db.get(ComprovanteRfb, match.comprovante_rfb_id) if match.comprovante_rfb_id else None
        total_lines = sum((line.valor for line in db.query(LancamentoContabil).filter_by(correspondencia_id=match.id)), 0)
        movement_date = movement.data.strftime("%d/%m/%Y")
        receipt_detail = "—" if not receipt else f"Data: {receipt.data.strftime('%d/%m/%Y')}\nTipo: {receipt.tipo_operacao or '—'}\nFavorecido: {receipt.favorecido}\nValor pago: {money(receipt.valor_pago)}"
        rfb_detail = "—" if not rfb else f"Data: {rfb.data_arrecadacao.strftime('%d/%m/%Y') if rfb.data_arrecadacao else '—'}\nTipo: {rfb.tipo}\nCompetência: {rfb.competencia or rfb.periodo_apuracao or '—'}\nBanco: {rfb.nome_banco}\nTotal: {money(rfb.valor_total)}"
        receipt_composition = None
        if receipt:
            discount = (receipt.valor_desconto or 0) + (receipt.valor_abatimento or 0) + (receipt.valor_desconto_abatimento or 0)
            additions = (receipt.valor_juros or 0) + (receipt.valor_multa or 0) + (receipt.valor_encargos or 0)
            expected = (receipt.valor_original or receipt.valor_pago or 0) - discount + additions
            receipt_composition = {"valor_documento": money(receipt.valor_original), "valor_cobrado": money(receipt.valor_pago), "desconto": money(discount), "juros": money(receipt.valor_juros), "multa": money(receipt.valor_multa), "encargos": money(receipt.valor_encargos), "valor_calculado": money(expected), "diferenca": money((receipt.valor_pago or 0) - expected), "confere": abs((receipt.valor_pago or 0) - expected) <= Decimal("0.01")}
        rows.append({"id": match.id, "data": movement_date, "tipo_pagamento": payment_type(movement.historico), "natureza": normalize_statement_nature(movement.natureza), "natureza_contabil": accounting_nature(movement.natureza), "extrato": f"Data: {movement_date}\nTexto: {' '.join(item for item in [movement.historico, movement.nome_encontrado] if item)}\nValor: {money(movement.valor)}", "comprovante_bancario": receipt_detail, "comprovante_rfb": rfb_detail, "comprovante_composicao": receipt_composition, "extrato_arquivo_id": movement.arquivo_id, "extrato_pagina": movement.pagina_numero, "comprovante_arquivo_id": receipt.arquivo_id if receipt else None, "comprovante_pagina": receipt.pagina_numero if receipt else None, "rfb_arquivo_id": rfb.arquivo_id if rfb else None, "rfb_pagina": rfb.pagina_numero if rfb else None, "valor": money(movement.valor), "fonte_regra": match.fonte_regra or "—", "total_lancamentos": money(total_lines), "diferenca": money(movement.valor - total_lines), "confianca": match.confianca, "situacao": match.status})
    for row in rows:
        items = db.query(LancamentoContabil).filter_by(correspondencia_id=row["id"]).order_by(LancamentoContabil.ordem, LancamentoContabil.id).all()
        row["lancamentos"] = [{"id": item.id, "componente": item.componente, "categoria": item.categoria, "tributo": item.tributo, "codigo_receita": item.codigo_receita, "descricao": item.descricao, "efeito_no_total": item.efeito_no_total, "valor": money(item.valor), "conta_debito": item.conta_debito, "conta_credito": item.conta_credito, "historico": item.historico, "origem": item.origem, "status": item.status, "regra_contabil_id": item.regra_contabil_id} for item in items]
    return rows


@router.put("/conciliacoes/{conciliacao_id}/correspondencias/{correspondencia_id}/lancamentos")
def save_accounting_items(conciliacao_id: str, correspondencia_id: str, payload: LancamentosInput, db: Session = Depends(get_db)):
    match = db.get(Correspondencia, correspondencia_id)
    if not match or match.conciliacao_id != conciliacao_id:
        raise HTTPException(404, "Conciliação não encontrada")
    movement = db.get(MovimentoExtrato, match.movimento_extrato_id)
    if not movement or not payload.itens or any(item.valor <= 0 or not all((item.conta_debito.strip(), item.conta_credito.strip(), item.historico.strip())) for item in payload.itens):
        raise HTTPException(422, "Todos os itens precisam de valor positivo, débito, crédito e histórico")
    total = sum((item.valor if item.efeito_no_total == "SOMA" else -item.valor for item in payload.itens), Decimal("0.00"))
    existing = {item.id: item for item in db.query(LancamentoContabil).filter_by(correspondencia_id=match.id).all()}
    for order, item in enumerate(payload.itens, 1):
        entry = existing.get(item.id)
        if not entry:
            entry = LancamentoContabil(correspondencia_id=match.id)
            db.add(entry)
        entry.componente = item.componente.strip().upper()
        entry.categoria = entry.componente
        entry.tributo = item.tributo
        entry.codigo_receita = item.codigo_receita
        entry.descricao = item.descricao
        entry.valor = item.valor
        entry.efeito_no_total = item.efeito_no_total
        entry.conta_debito = item.conta_debito.strip()
        entry.conta_credito = item.conta_credito.strip()
        entry.historico = item.historico.strip()
        entry.origem = "manual"
        entry.ordem = order
        entry.status = "editado_manual"
    db.flush()
    total = sum((entry.valor if entry.efeito_no_total == "SOMA" else -entry.valor for entry in db.query(LancamentoContabil).filter_by(correspondencia_id=match.id)), Decimal("0.00"))
    difference = (movement.valor or Decimal("0.00")) - total
    match.status = "Conciliado manualmente" if abs(difference) <= Decimal("0.01") else "Lançamentos pendentes de conferência"
    db.commit()
    return {"id": match.id, "itens": len(payload.itens), "total_contabil": str(total), "valor_extrato": str(movement.valor or 0), "diferenca": str(difference), "status": match.status}


@router.get("/conciliacoes/{conciliacao_id}/documentos-nao-utilizados")
def unused_documents(conciliacao_id: str, db: Session = Depends(get_db)):
    reconciliation = db.get(Conciliacao, conciliacao_id)
    matches = db.query(Correspondencia).filter_by(conciliacao_id=conciliacao_id).all()
    used_receipts = {item.comprovante_id for item in matches if item.comprovante_id}
    used_rfb = {item.comprovante_rfb_id for item in matches if item.comprovante_rfb_id}
    def display_date(value): return value.strftime("%d/%m/%Y") if value else "—"
    def in_period(value): return bool(value and reconciliation.data_inicio <= value <= reconciliation.data_fim)
    receipts = db.query(Comprovante).filter_by(conciliacao_id=conciliacao_id, ativo=True).all()
    rfb_receipts = [item for item in db.query(ComprovanteRfb).filter_by(conciliacao_id=conciliacao_id) if belongs_to_selected_bank(item, reconciliation.banco)]
    unused_receipts = [{"id": item.id, "data": display_date(item.data), "hora": item.hora or "—", "favorecido": item.beneficiario_final or item.beneficiario or item.favorecido, "valor_pago": str(item.valor_pago), "tipo": item.tipo_operacao, "situacao": "Sem movimento no extrato" if in_period(item.data) else "Fora do período"} for item in receipts if item.id not in used_receipts]
    unused_rfb = [{"id": item.id, "tipo": item.tipo, "data_arrecadacao": display_date(item.data_arrecadacao), "documento": item.numero_documento, "banco": item.nome_banco, "total": str(item.valor_total), "situacao": "Sem movimento no extrato" if in_period(item.data_arrecadacao) else "Fora do período"} for item in rfb_receipts if item.id not in used_rfb]
    def summary(items, used, date_field): return {"total": len(items), "utilizados": sum(item.id in used for item in items), "nao_utilizados": sum(item.id not in used for item in items), "fora_periodo": sum(not in_period(getattr(item, date_field)) for item in items)}
    return {"comprovantes": unused_receipts, "rfb": unused_rfb, "resumo": {"comprovantes": summary(receipts, used_receipts, "data"), "rfb": summary(rfb_receipts, used_rfb, "data_arrecadacao")}}


@router.get("/conciliacoes/{conciliacao_id}/revisao")
def review(conciliacao_id: str, db: Session = Depends(get_db)):
    def base(record, fields):
        return {"id": record.id, "arquivo_id": record.arquivo_id, "pagina": record.pagina_numero, "revisao": getattr(record, "status_revisao", record.status if hasattr(record, "status") else ""), **fields}

    def display_date(value):
        return value.strftime("%d/%m/%Y") if value else ""
    def money(value):
        if value is None:
            return "—"
        integer, decimal = f"{value:.2f}".split(".")
        return f"R$ {int(integer):,}".replace(",", ".") + f",{decimal}"

    def adjustments(item):
        fields = (("Desconto", item.valor_desconto), ("Abatimento", item.valor_abatimento), ("Desconto/abatimento", item.valor_desconto_abatimento), ("Juros", item.valor_juros), ("Multa", item.valor_multa), ("Encargos", item.valor_encargos))
        values = [f"{label}: {money(value)}" for label, value in fields if value is not None and value > 0]
        suffix = " Composição de valor divergente." if item.status_revisao == "revisao" else ""
        return (" + ".join(values) if values else "Sem ajustes") + suffix

    def receipt_counterparty(item):
        beneficiary = item.beneficiario or item.favorecido
        if item.beneficiario_final and item.beneficiario_final != beneficiary:
            return f"Beneficiário: {beneficiary}\nBeneficiário final: {item.beneficiario_final}"
        return f"Beneficiário: {beneficiary}"

    reconciliation = db.get(Conciliacao, conciliacao_id)
    rfb_records = [item for item in db.query(ComprovanteRfb).filter_by(conciliacao_id=conciliacao_id).order_by(ComprovanteRfb.data_arrecadacao.asc(), ComprovanteRfb.id.asc()) if reconciliation and belongs_to_selected_bank(item, reconciliation.banco)]

    return {
        "extratos": [base(x, {"data": display_date(x.data), "hora": x.hora, "historico": " ".join(item for item in [x.historico, x.nome_encontrado] if item), "valor": str(x.valor), "natureza": normalize_statement_nature(x.natureza), "natureza_contabil": accounting_nature(x.natureza)}) for x in db.query(MovimentoExtrato).filter_by(conciliacao_id=conciliacao_id, ativo=True).order_by(MovimentoExtrato.data.asc(), MovimentoExtrato.hora.asc().nulls_last(), MovimentoExtrato.id.asc())],
        "comprovantes": [base(x, {"data": display_date(x.data), "hora": x.hora, "favorecido": receipt_counterparty(x), "valor_original": money(x.valor_original), "ajustes": adjustments(x), "valor_pago": money(x.valor_pago), "tipo": x.tipo_operacao}) for x in db.query(Comprovante).filter_by(conciliacao_id=conciliacao_id, ativo=True).order_by(Comprovante.data.asc(), Comprovante.hora.asc().nulls_last(), Comprovante.id.asc())],
        "rfb": [base(x, {"tipo": x.tipo, "competencia_apuracao": x.competencia or x.periodo_apuracao or "—", "data_arrecadacao": display_date(x.data_arrecadacao), "documento": x.numero_documento, "banco": x.nome_banco, "principal": money(x.valor_principal), "multa_juros": "Sem acréscimos" if not ((x.valor_multa or 0) + (x.valor_juros or 0)) else f"Multa: {money(x.valor_multa)} + Juros: {money(x.valor_juros)}", "total": money(x.valor_total), "situacao": x.status}) for x in rfb_records],
        "arquivos": [{"id": x.id, "nome": x.nome_original, "tipo": x.tipo_documento, "status": x.status_processamento, "erro": x.mensagem_erro} for x in db.query(Arquivo).filter_by(conciliacao_id=conciliacao_id, ativo=True)],
    }
