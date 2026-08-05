from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def new_id() -> str:
    return str(uuid4())


class Cliente(Base):
    __tablename__ = "clientes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    nome: Mapped[str] = mapped_column(String(255))
    documento: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Conciliacao(Base):
    __tablename__ = "conciliacoes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    cliente_id: Mapped[str] = mapped_column(ForeignKey("clientes.id"), index=True)
    processo_id: Mapped[str | None] = mapped_column(ForeignKey("processos_conciliacao.id"), index=True)
    banco: Mapped[str] = mapped_column(String(100))
    data_inicio: Mapped[date] = mapped_column(Date)
    data_fim: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), default="rascunho")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ProcessoConciliacao(Base):
    __tablename__ = "processos_conciliacao"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    cliente_id: Mapped[str] = mapped_column(ForeignKey("clientes.id"), index=True)
    data_inicio: Mapped[date] = mapped_column(Date)
    data_fim: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), default="em_andamento")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Arquivo(Base):
    __tablename__ = "arquivos"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    conciliacao_id: Mapped[str] = mapped_column(ForeignKey("conciliacoes.id"), index=True)
    tipo_documento: Mapped[str] = mapped_column(String(20))
    banco_selecionado: Mapped[str] = mapped_column(String(100))
    nome_original: Mapped[str] = mapped_column(String(255))
    caminho: Mapped[str] = mapped_column(String(500))
    data_upload: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    texto_bruto: Mapped[str | None] = mapped_column(Text)
    status_processamento: Mapped[str] = mapped_column(String(30), default="pendente")
    mensagem_erro: Mapped[str | None] = mapped_column(Text)
    paginas: Mapped[int | None] = mapped_column(Integer)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class DocumentoImportante(Base):
    __tablename__ = "documentos_importantes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tipo: Mapped[str] = mapped_column(String(30))
    nome_original: Mapped[str] = mapped_column(String(255))
    caminho: Mapped[str] = mapped_column(String(500))
    extensao: Mapped[str] = mapped_column(String(10))
    catalogo: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RegistroBase:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    conciliacao_id: Mapped[str] = mapped_column(ForeignKey("conciliacoes.id"), index=True)
    arquivo_id: Mapped[str] = mapped_column(ForeignKey("arquivos.id"), index=True)
    pagina_numero: Mapped[int] = mapped_column(Integer)
    texto_original: Mapped[str] = mapped_column(Text, default="")
    dados_originais: Mapped[dict] = mapped_column(JSON, default=dict)
    dados_normalizados: Mapped[dict] = mapped_column(JSON, default=dict)
    editado_manual: Mapped[bool] = mapped_column(Boolean, default=False)
    status_revisao: Mapped[str] = mapped_column(String(30), default="valido")
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class MovimentoExtrato(RegistroBase, Base):
    __tablename__ = "movimentos_extrato"
    data: Mapped[date | None] = mapped_column(Date)
    hora: Mapped[str | None] = mapped_column(String(8))
    historico: Mapped[str] = mapped_column(Text, default="")
    nome_encontrado: Mapped[str] = mapped_column(Text, default="")
    valor: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    natureza: Mapped[str] = mapped_column(String(10), default="Débito")
    data_origem: Mapped[str] = mapped_column(String(10), default="")


class Comprovante(RegistroBase, Base):
    __tablename__ = "comprovantes"
    data: Mapped[date | None] = mapped_column(Date)
    hora: Mapped[str | None] = mapped_column(String(8))
    favorecido: Mapped[str] = mapped_column(Text, default="")
    valor: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    valor_original: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    valor_desconto: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    valor_abatimento: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    valor_desconto_abatimento: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    valor_juros: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    valor_multa: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    valor_encargos: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    valor_tarifa: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    valor_pago: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    detalhes_financeiros: Mapped[dict] = mapped_column(JSON, default=dict)
    tipo_operacao: Mapped[str] = mapped_column(String(20), default="")
    numero_documento: Mapped[str] = mapped_column(String(80), default="")
    banco_detectado: Mapped[str | None] = mapped_column(String(100))
    beneficiario: Mapped[str] = mapped_column(Text, default="")
    nome_fantasia: Mapped[str] = mapped_column(Text, default="")
    beneficiario_final: Mapped[str] = mapped_column(Text, default="")
    pagador: Mapped[str] = mapped_column(Text, default="")
    cnpj_beneficiario: Mapped[str] = mapped_column(String(32), default="")
    cnpj_beneficiario_final: Mapped[str] = mapped_column(String(32), default="")


class NotaFiscal(RegistroBase, Base):
    __tablename__ = "notas_fiscais"
    data_emissao: Mapped[date | None] = mapped_column(Date)
    fornecedor: Mapped[str] = mapped_column(Text, default="")
    cpf_cnpj: Mapped[str] = mapped_column(String(32), default="")
    numero_nota: Mapped[str] = mapped_column(String(80), default="")
    valor_total: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))


class ComprovanteRfb(Base):
    __tablename__ = "comprovantes_rfb"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    conciliacao_id: Mapped[str] = mapped_column(ForeignKey("conciliacoes.id"), index=True)
    arquivo_id: Mapped[str] = mapped_column(ForeignKey("arquivos.id"), index=True)
    pagina_numero: Mapped[int] = mapped_column(Integer)
    tipo: Mapped[str] = mapped_column(String(10))
    cnpj: Mapped[str] = mapped_column(String(32), default="")
    razao_social: Mapped[str] = mapped_column(Text, default="")
    competencia: Mapped[str] = mapped_column(String(30), default="")
    periodo_apuracao: Mapped[str] = mapped_column(String(30), default="")
    data_vencimento: Mapped[date | None] = mapped_column(Date)
    data_arrecadacao: Mapped[date | None] = mapped_column(Date)
    numero_documento: Mapped[str] = mapped_column(String(80), default="")
    codigo_banco: Mapped[str] = mapped_column(String(10), default="")
    nome_banco: Mapped[str] = mapped_column(String(150), default="")
    agencia: Mapped[str] = mapped_column(String(20), default="")
    valor_principal: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    valor_multa: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    valor_juros: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    valor_total: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    texto_original: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="pronto")
    editado_manualmente: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ComprovanteRfbItem(Base):
    __tablename__ = "comprovantes_rfb_itens"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    comprovante_rfb_id: Mapped[str] = mapped_column(ForeignKey("comprovantes_rfb.id", ondelete="CASCADE"), index=True)
    codigo: Mapped[str] = mapped_column(String(20), default="")
    descricao: Mapped[str] = mapped_column(Text, default="")
    valor_principal: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    valor_multa: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    valor_juros: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    valor_total: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))


class Correspondencia(Base):
    __tablename__ = "correspondencias"
    __table_args__ = (UniqueConstraint("conciliacao_id", "movimento_extrato_id", name="uq_correspondencias_conciliacao_movimento"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    conciliacao_id: Mapped[str] = mapped_column(ForeignKey("conciliacoes.id"), index=True)
    movimento_extrato_id: Mapped[str] = mapped_column(ForeignKey("movimentos_extrato.id"))
    comprovante_id: Mapped[str | None] = mapped_column(ForeignKey("comprovantes.id"))
    nota_fiscal_id: Mapped[str | None] = mapped_column(ForeignKey("notas_fiscais.id"))
    comprovante_rfb_id: Mapped[str | None] = mapped_column(ForeignKey("comprovantes_rfb.id"))
    fonte_regra: Mapped[str | None] = mapped_column(String(30))
    regra_contabil_id: Mapped[str | None] = mapped_column(ForeignKey("regras_contabeis.id"))
    confianca: Mapped[str] = mapped_column(String(20), default="")
    criterio_correspondencia: Mapped[str] = mapped_column(String(80), default="")
    status: Mapped[str] = mapped_column(String(40), default="possível correspondência")


class RegraContabil(Base):
    __tablename__ = "regras_contabeis"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    cliente_id: Mapped[str | None] = mapped_column(ForeignKey("clientes.id"), index=True)
    conciliacao_id: Mapped[str | None] = mapped_column(ForeignKey("conciliacoes.id"), index=True)
    banco: Mapped[str] = mapped_column(String(100), default="")
    tipo_fonte: Mapped[str] = mapped_column(String(30))
    tipo_operacao: Mapped[str] = mapped_column(String(80), default="")
    tipo_componente: Mapped[str] = mapped_column(String(30), default="")
    favorecido_normalizado: Mapped[str] = mapped_column(Text, default="")
    gatilho_comprovante_normalizado: Mapped[str] = mapped_column(Text, default="")
    codigo_receita: Mapped[str] = mapped_column(String(20), default="")
    conta_debito: Mapped[str] = mapped_column(String(100), default="")
    conta_credito: Mapped[str] = mapped_column(String(100), default="")
    historico: Mapped[str] = mapped_column(Text, default="")
    complemento: Mapped[str] = mapped_column(Text, default="")
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ContaBancaria(Base):
    __tablename__ = "contas_bancarias"
    __table_args__ = (UniqueConstraint("cliente_id", "banco", name="uq_contas_bancarias_cliente_banco"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    cliente_id: Mapped[str] = mapped_column(ForeignKey("clientes.id"), index=True)
    banco: Mapped[str] = mapped_column(String(100))
    agencia: Mapped[str] = mapped_column(String(30), default="")
    conta: Mapped[str] = mapped_column(String(50), default="")
    titular: Mapped[str] = mapped_column(String(255), default="")
    conta_contabil: Mapped[str] = mapped_column(String(100), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class LancamentoContabil(Base):
    __tablename__ = "lancamentos_contabeis"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    correspondencia_id: Mapped[str] = mapped_column(ForeignKey("correspondencias.id"), index=True)
    regra_contabil_id: Mapped[str | None] = mapped_column(ForeignKey("regras_contabeis.id"))
    componente: Mapped[str] = mapped_column(String(30), default="total")
    categoria: Mapped[str] = mapped_column(String(30), default="")
    tributo: Mapped[str] = mapped_column(Text, default="")
    codigo_receita: Mapped[str] = mapped_column(String(20), default="")
    descricao: Mapped[str] = mapped_column(Text, default="")
    efeito_no_total: Mapped[str] = mapped_column(String(10), default="SOMA")
    origem: Mapped[str] = mapped_column(String(20), default="")
    ordem: Mapped[int] = mapped_column(Integer, default=0)
    valor: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    conta_debito: Mapped[str] = mapped_column(String(100), default="")
    conta_credito: Mapped[str] = mapped_column(String(100), default="")
    historico: Mapped[str] = mapped_column(Text, default="")
    complemento: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="pendente")
