import shutil
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import fitz
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import UPLOAD_DIR
from app.core.database import get_db
from app.models import Arquivo, Cliente, Comprovante, ComprovanteRfb, ComprovanteRfbItem, Conciliacao, Correspondencia, LancamentoContabil, MovimentoExtrato
from app.services.normalization import normalize_name
from app.services.parsers import extract_receipts, extract_statement
from app.services.rfb import belongs_to_selected_bank, parse_rfb_page
from app.services.rule_source import choose_rule_source

router = APIRouter()
BANKS = ["Banco do Brasil", "Bradesco", "Caixa Econômica Federal", "Itaú", "Santander", "Nubank", "Outro"]


@router.get("/arquivos/{arquivo_id}/visualizar")
def view_file(arquivo_id: str, db: Session = Depends(get_db)):
    record = db.get(Arquivo, arquivo_id)
    if not record or not Path(record.caminho).is_file():
        raise HTTPException(404, "Documento original não encontrado")
    return FileResponse(Path(record.caminho), media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{record.nome_original}"'})


class ClienteInput(BaseModel):
    nome: str
    documento: str | None = None


class ConciliacaoInput(BaseModel):
    cliente_id: str
    banco: str
    data_inicio: date
    data_fim: date


@router.get("/bancos")
def banks():
    return BANKS


@router.get("/clientes")
def list_clients(db: Session = Depends(get_db)):
    return [{"id": item.id, "nome": item.nome, "documento": item.documento} for item in db.query(Cliente).order_by(Cliente.nome)]


@router.post("/clientes")
def create_client(payload: ClienteInput, db: Session = Depends(get_db)):
    client = Cliente(**payload.model_dump())
    db.add(client); db.commit(); db.refresh(client)
    return {"id": client.id, "nome": client.nome, "documento": client.documento}


@router.post("/conciliacoes")
def create_reconciliation(payload: ConciliacaoInput, db: Session = Depends(get_db)):
    if payload.banco not in BANKS or not db.get(Cliente, payload.cliente_id):
        raise HTTPException(422, "Cliente ou banco inválido")
    item = Conciliacao(**payload.model_dump())
    db.add(item); db.commit(); db.refresh(item)
    return {"id": item.id, "status": item.status}


@router.post("/conciliacoes/{conciliacao_id}/arquivos")
def upload(conciliacao_id: str, tipo_documento: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    if tipo_documento not in {"extrato", "comprovante", "rfb"} or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(422, "Envie um PDF com tipo de documento válido")
    reconciliation = db.get(Conciliacao, conciliacao_id)
    if not reconciliation:
        raise HTTPException(404, "Conciliação não encontrada")
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
            extracted.extend([parsed_rfb] if parsed_rfb else [] if tipo_documento == "rfb" else extract_receipts(page_text, number) if tipo_documento == "comprovante" else extract_statement(page_text, number))
        for item in extracted:
            if tipo_documento == "rfb":
                receipt = ComprovanteRfb(conciliacao_id=conciliacao_id, arquivo_id=record.id, pagina_numero=item.pagina_numero, tipo=item.tipo, cnpj=item.cnpj, razao_social=item.razao_social, competencia=item.competencia, periodo_apuracao=item.periodo_apuracao, data_vencimento=item.data_vencimento, data_arrecadacao=item.data_arrecadacao, numero_documento=item.numero_documento, codigo_banco=item.codigo_banco, nome_banco=item.nome_banco, agencia=item.agencia, valor_principal=item.valor_principal, valor_multa=item.valor_multa, valor_juros=item.valor_juros, valor_total=item.valor_total, texto_original=item.texto_original, status="composição divergente" if item.composicao_divergente else "pronto")
                db.add(receipt); db.flush()
                for tax in item.itens:
                    db.add(ComprovanteRfbItem(comprovante_rfb_id=receipt.id, codigo=tax.codigo, descricao=tax.descricao, valor_principal=tax.valor_principal, valor_multa=tax.valor_multa, valor_juros=tax.valor_juros, valor_total=tax.valor_total))
                continue
            common = dict(conciliacao_id=conciliacao_id, arquivo_id=record.id, pagina_numero=item.pagina_numero, texto_original=item.texto_original, dados_originais={"origem_nome": item.origem_nome} if tipo_documento == "comprovante" else {}, dados_normalizados={"nome": normalize_name(item.favorecido if tipo_documento == "comprovante" else item.nome)})
            db.add(Comprovante(**common, data=item.data, hora=item.hora, favorecido=item.favorecido, valor=item.financeiros.valor_pago, valor_original=item.financeiros.valor_original, valor_desconto=item.financeiros.valor_desconto, valor_abatimento=item.financeiros.valor_abatimento, valor_desconto_abatimento=item.financeiros.valor_desconto_abatimento, valor_juros=item.financeiros.valor_juros, valor_multa=item.financeiros.valor_multa, valor_encargos=item.financeiros.valor_encargos, valor_pago=item.financeiros.valor_pago, detalhes_financeiros=item.financeiros.detalhes, status_revisao="revisao" if item.financeiros.composicao_divergente else "valido", tipo_operacao=item.tipo_operacao) if tipo_documento == "comprovante" else MovimentoExtrato(**common, data=item.data, hora=item.hora, historico=item.historico, nome_encontrado=item.nome, valor=item.valor, natureza=item.natureza))
        record.status_processamento = "concluido"
    except Exception as error:
        record.status_processamento = "erro"; record.mensagem_erro = str(error)
    db.commit()
    return {"id": record.id, "status": record.status_processamento}


@router.post("/arquivos/{arquivo_id}/reprocessar")
def reprocess_document(arquivo_id: str, db: Session = Depends(get_db)):
    record = db.get(Arquivo, arquivo_id)
    if not record or record.tipo_documento not in {"extrato", "comprovante", "rfb"}:
        raise HTTPException(404, "Documento reprocessável não encontrado")
    model = MovimentoExtrato if record.tipo_documento == "extrato" else Comprovante if record.tipo_documento == "comprovante" else ComprovanteRfb
    db.query(model).filter_by(arquivo_id=record.id).delete()
    extracted = []
    for number, page_text in enumerate((record.texto_bruto or "").split("\n\f\n"), 1):
        parsed_rfb = parse_rfb_page(page_text, number) if record.tipo_documento == "rfb" else None
        extracted.extend([parsed_rfb] if parsed_rfb else [] if record.tipo_documento == "rfb" else extract_statement(page_text, number) if record.tipo_documento == "extrato" else extract_receipts(page_text, number))
    for item in extracted:
        if record.tipo_documento == "rfb":
            receipt = ComprovanteRfb(conciliacao_id=record.conciliacao_id, arquivo_id=record.id, pagina_numero=item.pagina_numero, tipo=item.tipo, cnpj=item.cnpj, razao_social=item.razao_social, competencia=item.competencia, periodo_apuracao=item.periodo_apuracao, data_vencimento=item.data_vencimento, data_arrecadacao=item.data_arrecadacao, numero_documento=item.numero_documento, codigo_banco=item.codigo_banco, nome_banco=item.nome_banco, agencia=item.agencia, valor_principal=item.valor_principal, valor_multa=item.valor_multa, valor_juros=item.valor_juros, valor_total=item.valor_total, texto_original=item.texto_original, status="composição divergente" if item.composicao_divergente else "pronto")
            db.add(receipt); db.flush()
            for tax in item.itens:
                db.add(ComprovanteRfbItem(comprovante_rfb_id=receipt.id, codigo=tax.codigo, descricao=tax.descricao, valor_principal=tax.valor_principal, valor_multa=tax.valor_multa, valor_juros=tax.valor_juros, valor_total=tax.valor_total))
            continue
        common = dict(conciliacao_id=record.conciliacao_id, arquivo_id=record.id, pagina_numero=item.pagina_numero, texto_original=item.texto_original, dados_originais={"origem_nome": item.origem_nome} if record.tipo_documento == "comprovante" else {}, dados_normalizados={"nome": normalize_name(item.nome if record.tipo_documento == "extrato" else item.favorecido)})
        db.add(MovimentoExtrato(**common, data=item.data, hora=item.hora, historico=item.historico, nome_encontrado=item.nome, valor=item.valor, natureza=item.natureza) if record.tipo_documento == "extrato" else Comprovante(**common, data=item.data, hora=item.hora, favorecido=item.favorecido, valor=item.financeiros.valor_pago, valor_original=item.financeiros.valor_original, valor_desconto=item.financeiros.valor_desconto, valor_abatimento=item.financeiros.valor_abatimento, valor_desconto_abatimento=item.financeiros.valor_desconto_abatimento, valor_juros=item.financeiros.valor_juros, valor_multa=item.financeiros.valor_multa, valor_encargos=item.financeiros.valor_encargos, valor_pago=item.financeiros.valor_pago, detalhes_financeiros=item.financeiros.detalhes, status_revisao="revisao" if item.financeiros.composicao_divergente else "valido", tipo_operacao=item.tipo_operacao))
    record.status_processamento = "concluido"
    record.mensagem_erro = None
    db.commit()
    return {"registros_extraidos": len(extracted), "status": record.status_processamento}


@router.post("/conciliacoes/{conciliacao_id}/conciliar")
def reconcile(conciliacao_id: str, db: Session = Depends(get_db)):
    reconciliation = db.get(Conciliacao, conciliacao_id)
    if not reconciliation:
        raise HTTPException(404, "Conciliação não encontrada")
    existing = db.query(Correspondencia).filter_by(conciliacao_id=conciliacao_id).all()
    for match in existing:
        db.query(LancamentoContabil).filter_by(correspondencia_id=match.id).delete()
    db.query(Correspondencia).filter_by(conciliacao_id=conciliacao_id).delete()
    receipts = db.query(Comprovante).filter_by(conciliacao_id=conciliacao_id, ativo=True).all()
    rfb_receipts = [item for item in db.query(ComprovanteRfb).filter_by(conciliacao_id=conciliacao_id) if belongs_to_selected_bank(item, reconciliation.banco)]
    used_receipts, used_rfb = set(), set()
    movements = db.query(MovimentoExtrato).filter_by(conciliacao_id=conciliacao_id, ativo=True, natureza="saída").order_by(MovimentoExtrato.data, MovimentoExtrato.hora).all()
    for movement in movements:
        receipt = next((item for item in receipts if item.id not in used_receipts and item.valor_pago == movement.valor and item.data == movement.data), None)
        rfb = next((item for item in rfb_receipts if item.id not in used_rfb and item.valor_total == movement.valor and item.data_arrecadacao == movement.data), None)
        source_rfb = None
        if rfb:
            items = db.query(ComprovanteRfbItem).filter_by(comprovante_rfb_id=rfb.id).all()
            source_rfb = SimpleNamespace(valor_principal=rfb.valor_principal, valor_multa=rfb.valor_multa, valor_juros=rfb.valor_juros, itens=items)
        decision = choose_rule_source(movement.valor, receipt is not None, source_rfb)
        match = Correspondencia(conciliacao_id=conciliacao_id, movimento_extrato_id=movement.id, comprovante_id=receipt.id if receipt else None, comprovante_rfb_id=rfb.id if rfb else None, fonte_regra=decision.fonte_regra, confianca="alta" if not decision.exige_revisao else "média", status=decision.status)
        db.add(match); db.flush()
        for line in decision.linhas:
            db.add(LancamentoContabil(correspondencia_id=match.id, componente=line.componente, valor=line.valor, historico=line.descricao, status="pendente_regra"))
        if receipt: used_receipts.add(receipt.id)
        if rfb: used_rfb.add(rfb.id)
    db.commit()
    return {"conciliacoes_geradas": len(movements)}


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
        movement, receipt, rfb = db.get(MovimentoExtrato, match.movimento_extrato_id), db.get(Comprovante, match.comprovante_id), db.get(ComprovanteRfb, match.comprovante_rfb_id)
        total_lines = sum((line.valor for line in db.query(LancamentoContabil).filter_by(correspondencia_id=match.id)), 0)
        movement_date = movement.data.strftime("%d/%m/%Y")
        receipt_detail = "—" if not receipt else f"Data: {receipt.data.strftime('%d/%m/%Y')}\nTipo: {receipt.tipo_operacao or '—'}\nFavorecido: {receipt.favorecido}\nValor pago: {money(receipt.valor_pago)}"
        rfb_detail = "—" if not rfb else f"Data: {rfb.data_arrecadacao.strftime('%d/%m/%Y') if rfb.data_arrecadacao else '—'}\nTipo: {rfb.tipo}\nCompetência: {rfb.competencia or rfb.periodo_apuracao or '—'}\nBanco: {rfb.nome_banco}\nTotal: {money(rfb.valor_total)}"
        rows.append({"id": match.id, "data": movement_date, "tipo_pagamento": payment_type(movement.historico), "extrato": f"Data: {movement_date}\nTexto: {' '.join(item for item in [movement.historico, movement.nome_encontrado] if item)}\nValor: {money(movement.valor)}", "comprovante_bancario": receipt_detail, "comprovante_rfb": rfb_detail, "extrato_arquivo_id": movement.arquivo_id, "extrato_pagina": movement.pagina_numero, "comprovante_arquivo_id": receipt.arquivo_id if receipt else None, "comprovante_pagina": receipt.pagina_numero if receipt else None, "rfb_arquivo_id": rfb.arquivo_id if rfb else None, "rfb_pagina": rfb.pagina_numero if rfb else None, "valor": money(movement.valor), "fonte_regra": match.fonte_regra or "—", "total_lancamentos": money(total_lines), "diferenca": money(movement.valor - total_lines), "confianca": match.confianca, "situacao": match.status})
    return rows


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
    unused_receipts = [{"id": item.id, "data": display_date(item.data), "hora": item.hora or "—", "favorecido": item.favorecido, "valor_pago": str(item.valor_pago), "tipo": item.tipo_operacao, "situacao": "Sem movimento no extrato" if in_period(item.data) else "Fora do período"} for item in receipts if item.id not in used_receipts]
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

    reconciliation = db.get(Conciliacao, conciliacao_id)
    rfb_records = [item for item in db.query(ComprovanteRfb).filter_by(conciliacao_id=conciliacao_id).order_by(ComprovanteRfb.data_arrecadacao.asc(), ComprovanteRfb.id.asc()) if reconciliation and belongs_to_selected_bank(item, reconciliation.banco)]

    return {
        "extratos": [base(x, {"data": display_date(x.data), "hora": x.hora, "historico": " ".join(item for item in [x.historico, x.nome_encontrado] if item), "valor": str(x.valor), "natureza": x.natureza}) for x in db.query(MovimentoExtrato).filter_by(conciliacao_id=conciliacao_id, ativo=True).order_by(MovimentoExtrato.data.asc(), MovimentoExtrato.hora.asc().nulls_last(), MovimentoExtrato.id.asc())],
        "comprovantes": [base(x, {"data": display_date(x.data), "hora": x.hora, "favorecido": x.favorecido, "valor_original": money(x.valor_original), "ajustes": adjustments(x), "valor_pago": money(x.valor_pago), "tipo": x.tipo_operacao}) for x in db.query(Comprovante).filter_by(conciliacao_id=conciliacao_id, ativo=True).order_by(Comprovante.data.asc(), Comprovante.hora.asc().nulls_last(), Comprovante.id.asc())],
        "rfb": [base(x, {"tipo": x.tipo, "competencia_apuracao": x.competencia or x.periodo_apuracao or "—", "data_arrecadacao": display_date(x.data_arrecadacao), "documento": x.numero_documento, "banco": x.nome_banco, "principal": money(x.valor_principal), "multa_juros": "Sem acréscimos" if not ((x.valor_multa or 0) + (x.valor_juros or 0)) else f"Multa: {money(x.valor_multa)} + Juros: {money(x.valor_juros)}", "total": money(x.valor_total), "situacao": x.status}) for x in rfb_records],
        "arquivos": [{"id": x.id, "nome": x.nome_original, "tipo": x.tipo_documento, "status": x.status_processamento, "erro": x.mensagem_erro} for x in db.query(Arquivo).filter_by(conciliacao_id=conciliacao_id, ativo=True)],
    }
