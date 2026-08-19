from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from app.models import Arquivo, Comprovante, Conciliacao, ContaBancaria, Correspondencia, LancamentoContabil, MovimentoExtrato
from app.services.normalization import normalize_name, normalize_statement_nature


GETNET_ADJUSTMENT_ORIGIN = "ajuste_getnet"
GETNET_ADJUSTMENT_DESCRIPTION = "JUROS SOBRE ANTECIPAÇÕES GETNET"
GETNET_ADJUSTMENT_COMPLEMENT = "DIFERENÇA ENTRE GETNET E RECEBIMENTOS NO SANTANDER"
GETNET_ADJUSTMENT_COMPONENT = "JUROS_ANTECIPACAO_GETNET"
GETNET_ADJUSTMENT_STATUS = "pendente_regra"
GETNET_STATEMENT_DOCUMENT_TYPES = {"maquininha_extrato", "getnet_extrato", "getnet_vendas", "getnet_comissoes"}


def money(value: Decimal | int | None) -> Decimal:
    return (Decimal(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def competence(value: date) -> str:
    return f"{value.year:04d}-{value.month:02d}"


def competence_label(key: str) -> str:
    year, month = key.split("-")
    return f"{month}/{year}"


def month_end(key: str) -> date:
    year, month = (int(part) for part in key.split("-"))
    return date(year, month, monthrange(year, month)[1])


def in_period(reconciliation: Conciliacao, value: date | None) -> bool:
    return bool(value and reconciliation.data_inicio <= value <= reconciliation.data_fim)


def is_getnet_sales_receipt(receipt: Comprovante, file_by_id: dict[str, Arquivo]) -> bool:
    file = file_by_id.get(receipt.arquivo_id)
    return bool(file and file.ativo and file.tipo_documento in GETNET_STATEMENT_DOCUMENT_TYPES and receipt.ativo and receipt.valor_pago is not None)


def is_santander_getnet_credit(movement: MovimentoExtrato) -> bool:
    if not movement.ativo or movement.valor is None or normalize_statement_nature(movement.natureza) != "Crédito":
        return False
    text = normalize_name(" ".join(part for part in [movement.historico, movement.nome_encontrado] if part))
    if not text or "GETNET" not in text:
        return False
    return "ANTECIPACAO GETNET" in text or ("PAGAMENTO CARTAO DEBITO" in text and "GETNET" in text)


def adjustment_marker(competence_key: str, total_getnet: str = "", total_santander: str = "", difference: str = "") -> dict:
    return {
        "origem": GETNET_ADJUSTMENT_ORIGIN,
        "competencia": competence_key,
        "banco": "Santander",
        "fonte": "Getnet",
        "total_getnet": total_getnet,
        "total_santander": total_santander,
        "diferenca": difference,
    }


def is_getnet_adjustment_movement(movement: MovimentoExtrato) -> bool:
    original = movement.dados_originais if isinstance(movement.dados_originais, dict) else {}
    return original.get("origem") == GETNET_ADJUSTMENT_ORIGIN


def existing_adjustments(reconciliation: Conciliacao, db: Session) -> dict[str, tuple[MovimentoExtrato, Correspondencia | None, list[LancamentoContabil]]]:
    result = {}
    movements = [
        item
        for item in db.query(MovimentoExtrato).filter_by(conciliacao_id=reconciliation.id).all()
        if is_getnet_adjustment_movement(item)
    ]
    if not movements:
        return result
    movement_ids = [item.id for item in movements]
    matches = {item.movimento_extrato_id: item for item in db.query(Correspondencia).filter(Correspondencia.movimento_extrato_id.in_(movement_ids)).all()}
    match_ids = [item.id for item in matches.values()]
    entries_by_match: dict[str, list[LancamentoContabil]] = defaultdict(list)
    if match_ids:
        for entry in db.query(LancamentoContabil).filter(LancamentoContabil.correspondencia_id.in_(match_ids)).all():
            entries_by_match[entry.correspondencia_id].append(entry)
    for movement in movements:
        original = movement.dados_originais if isinstance(movement.dados_originais, dict) else {}
        key = original.get("competencia")
        if key:
            match = matches.get(movement.id)
            result[key] = (movement, match, entries_by_match.get(match.id, []) if match else [])
    return result


def calculate_getnet_anticipation_adjustments(reconciliation: Conciliacao, db: Session) -> list[dict]:
    if reconciliation.banco != "Santander":
        return []
    files = {item.id: item for item in db.query(Arquivo).filter_by(conciliacao_id=reconciliation.id).all()}
    getnet_totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    santander_totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    for receipt in db.query(Comprovante).filter_by(conciliacao_id=reconciliation.id).all():
        if is_getnet_sales_receipt(receipt, files) and in_period(reconciliation, receipt.data):
            getnet_totals[competence(receipt.data)] += Decimal(receipt.valor_pago or 0)
    for movement in db.query(MovimentoExtrato).filter_by(conciliacao_id=reconciliation.id).all():
        if is_santander_getnet_credit(movement) and in_period(reconciliation, movement.data):
            santander_totals[competence(movement.data)] += Decimal(movement.valor or 0)
    existing = existing_adjustments(reconciliation, db)
    items = []
    for key in sorted(set(getnet_totals) | set(santander_totals) | set(existing)):
        total_getnet = money(getnet_totals.get(key))
        total_santander = money(santander_totals.get(key))
        difference = money(total_getnet - total_santander)
        existing_entry = next((entry for entry in existing.get(key, (None, None, []))[2] if entry.origem == GETNET_ADJUSTMENT_ORIGIN), None)
        has_getnet = total_getnet > 0
        has_santander = total_santander > 0
        if not has_getnet or not has_santander:
            status = "Dados insuficientes"
        elif difference > Decimal("0.00"):
            status = "Ajuste lançado" if existing_entry and existing_entry.status in {"aplicado_por_regra", "editado_manual"} else "Pendente em regras"
        elif difference < Decimal("0.00"):
            status = "Divergência para revisão"
        else:
            status = "Sem diferença"
        items.append({
            "competencia": key,
            "competencia_label": competence_label(key),
            "total_getnet": str(total_getnet),
            "total_santander": str(total_santander),
            "diferenca": str(abs(difference) if difference < 0 else difference),
            "situacao": status,
            "lancamento": {
                "id": existing_entry.id,
                "data": month_end(key).strftime("%d/%m/%Y"),
                "historico": existing_entry.historico or GETNET_ADJUSTMENT_DESCRIPTION,
                "complemento": existing_entry.complemento or GETNET_ADJUSTMENT_COMPLEMENT,
                "valor": str(existing_entry.valor),
                "origem": "Ajuste Getnet/Santander",
                "status": existing_entry.status,
            } if existing_entry else None,
        })
    return items


def remove_adjustment(movement: MovimentoExtrato, match: Correspondencia | None, entries: list[LancamentoContabil], db: Session) -> None:
    if any(entry.status == "editado_manual" for entry in entries):
        return
    for entry in entries:
        db.delete(entry)
    if match:
        db.delete(match)
    db.delete(movement)


def sync_getnet_anticipation_adjustments(reconciliation: Conciliacao, db: Session) -> list[dict]:
    if reconciliation.banco != "Santander":
        return []
    summary = calculate_getnet_anticipation_adjustments(reconciliation, db)
    existing = existing_adjustments(reconciliation, db)
    statement_file = (
        db.query(Arquivo)
        .filter_by(conciliacao_id=reconciliation.id, tipo_documento="extrato", ativo=True)
        .order_by(Arquivo.data_upload.desc(), Arquivo.id.desc())
        .first()
    )
    account = db.query(ContaBancaria).filter_by(cliente_id=reconciliation.cliente_id, banco="Santander").first()
    expected_keys = {item["competencia"] for item in summary if item["situacao"] in {"Pendente em regras", "Ajuste lançado"} and statement_file}
    for item in summary:
        key = item["competencia"]
        movement, match, entries = existing.get(key, (None, None, []))
        if item["situacao"] not in {"Pendente em regras", "Ajuste lançado"}:
            if movement and item["situacao"] != "Ajuste lançado":
                remove_adjustment(movement, match, entries, db)
            continue
        if not statement_file:
            continue
        value = Decimal(item["diferenca"])
        if not movement:
            movement = MovimentoExtrato(
                conciliacao_id=reconciliation.id,
                arquivo_id=statement_file.id,
                pagina_numero=statement_file.paginas or 1,
                data=month_end(key),
                historico=GETNET_ADJUSTMENT_DESCRIPTION,
                nome_encontrado="",
                valor=value,
                natureza="Débito",
                texto_original=GETNET_ADJUSTMENT_DESCRIPTION,
                dados_originais=adjustment_marker(key, item["total_getnet"], item["total_santander"], item["diferenca"]),
                dados_normalizados={"nome": normalize_name(GETNET_ADJUSTMENT_DESCRIPTION)},
                ativo=False,
            )
            db.add(movement)
            db.flush()
        else:
            movement.data = month_end(key)
            movement.valor = value
            movement.historico = GETNET_ADJUSTMENT_DESCRIPTION
            movement.natureza = "Débito"
            movement.ativo = False
            movement.dados_originais = adjustment_marker(key, item["total_getnet"], item["total_santander"], item["diferenca"])
        if not match:
            match = Correspondencia(
                conciliacao_id=reconciliation.id,
                movimento_extrato_id=movement.id,
                fonte_regra=GETNET_ADJUSTMENT_ORIGIN,
                confianca="alta",
                criterio_correspondencia="Diferença entre Getnet líquido e recebimentos Getnet no Santander",
                status="Ajuste automático Getnet/Santander",
            )
            db.add(match)
            db.flush()
        entry = next((entry for entry in entries if entry.origem == GETNET_ADJUSTMENT_ORIGIN), None)
        if not entry:
            entry = LancamentoContabil(correspondencia_id=match.id, origem=GETNET_ADJUSTMENT_ORIGIN)
            db.add(entry)
        classified = entry.status in {"aplicado_por_regra", "editado_manual"} or bool(entry.regra_contabil_id)
        entry.componente = GETNET_ADJUSTMENT_COMPONENT
        entry.categoria = "JUROS"
        entry.descricao = GETNET_ADJUSTMENT_DESCRIPTION
        entry.efeito_no_total = "OUTROS"
        entry.ordem = 90
        entry.valor = value
        if not classified:
            entry.conta_debito = ""
            entry.conta_credito = account.conta_contabil.strip() if account and account.conta_contabil.strip() else ""
            entry.historico = GETNET_ADJUSTMENT_DESCRIPTION
            entry.complemento = GETNET_ADJUSTMENT_COMPLEMENT
            entry.status = GETNET_ADJUSTMENT_STATUS
    for key, (movement, match, entries) in existing.items():
        if key not in expected_keys and not any(item["competencia"] == key and item["situacao"] == "Ajuste lançado" for item in summary):
            remove_adjustment(movement, match, entries, db)
    db.flush()
    return calculate_getnet_anticipation_adjustments(reconciliation, db)
