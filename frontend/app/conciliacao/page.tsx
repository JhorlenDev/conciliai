"use client";

import { ChangeEvent, Fragment, useEffect, useRef, useState } from "react";
import {
  BookOpenCheck,
  CalendarDays,
  CheckCircle2,
  Copy,
  Download,
  Eye,
  FileText,
  Gauge,
  ListPlus,
  PenLine,
  Plus,
  RefreshCw,
  Tags,
  Trash2,
  Upload,
  WandSparkles,
  X,
} from "lucide-react";
import { ProcessTopBar } from "../components/process-top-bar";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const MESSAGE_TIMEOUT_MS = 6000;
const banks = [
  "Banco do Brasil",
  "Santander",
  "BASA",
  "Bradesco",
  "Caixa",
  "Conta Caixa",
  "Notas",
  "Apropriações",
  "Empréstimos/Financiamentos",
];
type Client = { id: string; nome: string };
type Row = Record<string, string | null>;
type AccountingItem = {
  id: string;
  componente: string;
  categoria: string;
  tributo: string;
  codigo_receita: string;
  descricao: string;
  efeito_no_total: string;
  valor: string;
  conta_debito: string;
  conta_credito: string;
  historico: string;
  complemento: string;
  imposto?: string;
  competencia?: string;
  competencia_nao_identificada?: boolean;
  comprovante_origem?: string;
  origem: string;
  status: string;
};
type ResultRow = {
  id: string;
  data: string;
  tipo_pagamento: string;
  natureza?: string | null;
  natureza_contabil?: string | null;
  extrato: string;
  comprovante_bancario?: string | null;
  comprovante_rfb?: string | null;
  extrato_arquivo_id?: string | null;
  extrato_pagina?: string | number | null;
  comprovante_arquivo_id?: string | null;
  comprovante_pagina?: string | number | null;
  rfb_arquivo_id?: string | null;
  rfb_pagina?: string | number | null;
  valor: string;
  fonte_regra?: string | null;
  total_lancamentos?: string | null;
  diferenca?: string | null;
  confianca?: string | null;
  situacao: string;
  lancamentos?: AccountingItem[];
  movimento_id?: string | null;
  usado_no_periodo?: boolean;
  comprovante_tipo?: string | null;
  comprovante_composicao?: Record<string, string | boolean>;
};
type Review = {
  extratos: Row[];
  comprovantes: Row[];
  maquininhas?: Row[];
  emprestimos?: Row[];
  notas?: Row[];
  rfb: Row[];
  saldos?: {
    saldo_anterior?: string;
  };
  ajustes_getnet?: GetnetAdjustment[];
  arquivos: {
    id: string;
    nome: string;
    tipo: string;
    status: string;
    erro: string | null;
  }[];
};
type GetnetAdjustment = {
  competencia: string;
  competencia_label: string;
  total_getnet: string;
  total_santander: string;
  diferenca: string;
  situacao: string;
  lancamento?: {
    id: string;
    data: string;
    historico: string;
    complemento: string;
    valor: string;
    origem: string;
  } | null;
};
type Unused = {
  comprovantes: Row[];
  emprestimos?: Row[];
  rfb: Row[];
  resumo: { comprovantes: Record<string, number>; emprestimos?: Record<string, number>; rfb: Record<string, number> };
};
type Viewer = { arquivoId: string; pagina: number; titulo: string };
const getnetDocumentLabels: Record<string, string> = {
  maquininha_extrato: "Extrato de maquininha",
  getnet_extrato: "Extrato Getnet",
  getnet_vendas: "Extrato Getnet",
  getnet_comissoes: "Extrato Getnet",
};
const documentTypeLabels: Record<string, string> = {
  extrato: "Extrato",
  comprovante: "Comprovante bancário",
  rfb: "Comprovante RFB",
  emprestimo: "Empréstimos/Financiamentos",
  nota: "Notas fiscais",
};

function isMachineDocumentType(type: string | null | undefined) {
  return Boolean(type && getnetDocumentLabels[type]);
}

function machineDocumentLabel(selectedBank: string) {
  return selectedBank === "Santander" ? "Extrato Getnet" : "Extrato de maquininha";
}

function documentTypeLabel(type: string | null | undefined, selectedBank = "") {
  if (!type) return "—";
  if (type === "maquininha_extrato") return machineDocumentLabel(selectedBank);
  return getnetDocumentLabels[type] ?? documentTypeLabels[type] ?? type;
}

function visibleBank(value: string | null | undefined) {
  if (value === "Vendas com Cartão" || value === "Comissões Getnet") return "Santander";
  if (value === "Empréstimos/Financeiro") return "Empréstimos/Financiamentos";
  return value && banks.includes(value) ? value : banks[0];
}

function formatMoney(value: string | number | null | undefined) {
  const numeric = Number(value ?? 0);
  return numeric.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function PdfModal({
  viewer,
  onClose,
}: {
  viewer: Viewer;
  onClose: () => void;
}) {
  const url = `${API}/api/arquivos/${viewer.arquivoId}/visualizar#page=${viewer.pagina}`;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4">
      <section className="flex h-[90vh] w-full max-w-6xl flex-col overflow-hidden rounded-xl bg-white">
        <header className="flex items-center justify-between border-b px-4 py-3">
          <div>
            <strong>{viewer.titulo}</strong>
            <p className="text-xs text-slate-500">Página {viewer.pagina}</p>
          </div>
          <div className="flex gap-2">
            <a
              className="rounded border px-3 py-1 text-sm"
              href={url}
              target="_blank"
            >
              Abrir em nova aba
            </a>
            <button
              aria-label="Fechar visualizador"
              title="Fechar"
              onClick={onClose}
              className="rounded border p-1"
            >
              <X size={18} />
            </button>
          </div>
        </header>
        <iframe
          title="Documento original"
          className="min-h-0 flex-1"
          src={url}
        />
      </section>
    </div>
  );
}

export default function ConciliacaoPage() {
  return <ConciliacaoFlow />;
}

function Table({
  title,
  columns,
  rows,
  showOrigin = true,
  onView,
}: {
  title: string;
  columns: string[];
  rows: Row[];
  showOrigin?: boolean;
  onView?: (viewer: Viewer) => void;
}) {
  return (
    <section className="overflow-hidden rounded-xl border border-slate-200 bg-white">
      <div className="flex items-center justify-between border-b px-5 py-4">
        <h2 className="font-semibold">{title}</h2>
        <span className="rounded-full bg-slate-100 px-2 py-1 text-xs">
          {rows.length} registros
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[900px] text-left text-xs">
          <thead className="bg-slate-50 text-[10px] uppercase text-slate-500">
            <tr>
              {columns.map((column) => (
                <th className="px-2 py-2" key={column}>
                  {column}
                </th>
              ))}
              {showOrigin && <th className="px-2 py-2">Origem</th>}
              {onView && <th className="px-2 py-2">Ações</th>}
            </tr>
          </thead>
          <tbody>
            {rows.length ? (
              rows.map((row, index) => (
                <tr className="border-t align-top" key={row.id ?? index}>
                  {columns.map((column) => (
                    <td
                      className={`max-w-72 px-2 py-2${column === "Favorecido" ? " whitespace-pre-line" : ""}${column === "Natureza" ? row.natureza === "Crédito" ? " font-semibold text-blue-700" : " font-semibold text-red-700" : ""}`}
                      key={column}
                    >
                      {row[column.toLowerCase().replaceAll(" ", "_")] || "—"}
                    </td>
                  ))}
                  {showOrigin && (
                    <td className="px-2 py-2 text-slate-500">
                      p. {row.pagina}
                    </td>
                  )}
                  {onView && (
                    <td className="px-2 py-2">
                      {row.arquivo_id && (
                        <button
                          aria-label="Visualizar documento original"
                          title="Visualizar documento original"
                          onClick={() =>
                            onView({
                              arquivoId: String(row.arquivo_id),
                              pagina: Number(row.pagina || 1),
                              titulo: title,
                            })
                          }
                        >
                          <Eye size={16} />
                        </button>
                      )}
                    </td>
                  )}
                </tr>
              ))
            ) : (
              <tr>
                <td
                  className="px-2 py-8 text-slate-500"
                  colSpan={
                    columns.length +
                    Number(showOrigin) +
                    Number(Boolean(onView))
                  }
                >
                  Nenhum registro extraído.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function AdvancedSummary({
  label,
  previous,
  debit,
  credit,
  current,
}: {
  label: string;
  previous: number;
  debit: number;
  credit: number;
  current: number;
}) {
  const money = (value: number) =>
    value.toLocaleString("pt-BR", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  const cells = [
    ["Anterior", previous, "border-slate-200 bg-slate-50"],
    ["Débito", debit, "border-blue-200 bg-blue-50 text-blue-800"],
    ["Crédito", credit, "border-red-200 bg-red-50 text-red-800"],
    ["Atual", current, "border-slate-200 bg-slate-50"],
  ] as const;
  return (
    <div className="flex items-center gap-3">
      <div className="w-12 shrink-0 text-xs font-semibold text-slate-600">
        {label}
      </div>
      <div className="grid flex-1 grid-cols-2 gap-1 sm:grid-cols-4">
        {cells.map(([title, value, color]) => (
          <div
            className={`flex items-baseline justify-center gap-1 rounded-md border px-2 py-1 text-center ${color}`}
            key={title}
          >
            <span className="text-[9px] uppercase text-slate-500">{title}:</span>
            <strong className="text-xs">{money(value)}</strong>
          </div>
        ))}
      </div>
    </div>
  );
}

function OtherSummary({ previous, debit, credit }: { previous: number; debit: number; credit: number }) {
  const money = (value: number) => value.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const total = debit - credit;
  return <div className="flex items-center gap-3"><div className="w-12 shrink-0 text-xs font-semibold text-violet-700">Outros</div><div className="grid flex-1 grid-cols-2 gap-1 sm:grid-cols-4"><div className="flex items-baseline justify-center gap-1 rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-center text-slate-700"><span className="text-[9px] uppercase text-slate-500">Anterior:</span><strong className="text-xs">{money(previous)}</strong></div><div className="flex items-baseline justify-center gap-1 rounded-md border border-indigo-200 bg-indigo-50 px-2 py-1 text-center text-indigo-800"><span className="text-[9px] uppercase text-indigo-600">Débito:</span><strong className="text-xs">{money(debit)}</strong></div><div className="flex items-baseline justify-center gap-1 rounded-md border border-fuchsia-200 bg-fuchsia-50 px-2 py-1 text-center text-fuchsia-800"><span className="text-[9px] uppercase text-fuchsia-600">Crédito:</span><strong className="text-xs">{money(credit)}</strong></div><div className="flex items-baseline justify-center gap-1 rounded-md border border-violet-300 bg-violet-100 px-2 py-1 text-center text-violet-900"><span className="text-[9px] uppercase text-violet-700">Atual:</span><strong className="text-xs">{money(total)}</strong></div></div></div>;
}

function LoadingValuesOverlay() {
  return <div className="fixed bottom-12 right-4 z-50 flex items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 shadow-lg"><RefreshCw className="animate-spin text-teal-700" size={16} />Atualizando valores...</div>;
}

function showInputStart(input: HTMLInputElement) {
  requestAnimationFrame(() => {
    input.scrollLeft = 0;
  });
}

function formatPeriodCard(start: string, end: string) {
  const parse = (value: string) => {
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value || "");
    return match ? { year: match[1], month: match[2], day: match[3] } : null;
  };
  const startDate = parse(start);
  const endDate = parse(end);
  if (!startDate || !endDate) return "";
  const months = [
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
  ];
  const monthName = months[Number(startDate.month) - 1] ?? startDate.month;
  const startShortYear = startDate.year.slice(-2);
  const endShortYear = endDate.year.slice(-2);
  return `${monthName} ${startDate.year} · ${startDate.day}/${startDate.month}/${startShortYear} a ${endDate.day}/${endDate.month}/${endShortYear}`;
}

function useAutoDismissMessage(message: string, setMessage: (value: string) => void) {
  useEffect(() => {
    if (!message) return;
    const timeout = window.setTimeout(() => setMessage(""), MESSAGE_TIMEOUT_MS);
    return () => window.clearTimeout(timeout);
  }, [message, setMessage]);
}

function AdvancedOverview({
  reconciliationId,
  version,
}: {
  reconciliationId: string;
  version: number;
}) {
  const [data, setData] = useState<{
    pendentes: unknown[];
    salvas: unknown[];
    resumo: {
      extrato: { saldo_anterior?: string; debito: string; credito: string; outros: string; outros_debito: string; outros_credito: string };
      razao: { debito: string; credito: string; outros: string; outros_debito: string; outros_credito: string };
    };
    integridade: { csv_permitido: boolean; diferenca: string; movimentos_incompletos: { data: string; historico: string }[] };
  } | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    fetch(`${API}/api/conciliacoes/${reconciliationId}/regras-contabeis?atualizacao=${version}`, { cache: "no-store", signal: controller.signal })
      .then((response) => (response.ok ? response.json() : null))
      .then((result) => {
        if (!controller.signal.aborted) setData(result);
      })
      .catch((error) => {
        if (error.name !== "AbortError") setData(null);
      });
    return () => controller.abort();
  }, [reconciliationId, version]);
  const summary = data?.resumo;
  const statementPrevious = Number(summary?.extrato.saldo_anterior ?? 0);
  const csvBlocked = data?.integridade && !data.integridade.csv_permitido;
  return (
    <section className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-white p-2.5">
      <div className="flex flex-col gap-1.5">
        <button className="flex items-center rounded-md bg-teal-700 px-3 py-2 text-left text-xs font-semibold text-white">
          <PenLine className="mr-1.5" size={14} />
          Regras a criar{" "}
          <span className="ml-1 rounded-full bg-white/20 px-1.5">
            {data?.pendentes.length ?? 0}
          </span>
        </button>
        <button className="flex items-center rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-left text-xs font-semibold text-emerald-800">
          <CheckCircle2 className="mr-1.5" size={14} />
          Regras salvas{" "}
          <span className="ml-1 rounded-full bg-white px-1.5">
            {data?.salvas.length ?? 0}
          </span>
        </button>
      </div>
      <div className="min-w-[560px] flex-[1.5] space-y-1">
        <AdvancedSummary
          label="Extrato"
          previous={statementPrevious}
          debit={Number(summary?.extrato.debito ?? 0)}
          credit={Number(summary?.extrato.credito ?? 0)}
          current={
            statementPrevious +
            Number(summary?.extrato.credito ?? 0) -
            Number(summary?.extrato.debito ?? 0)
          }
        />
        <AdvancedSummary
          label="Razão"
          previous={0}
          debit={Number(summary?.razao.debito ?? 0)}
          credit={Number(summary?.razao.credito ?? 0)}
          current={
            Number(summary?.razao.credito ?? 0) -
            Number(summary?.razao.debito ?? 0)
          }
        />
        <OtherSummary previous={0} debit={Number(summary?.razao.outros_debito ?? 0)} credit={Number(summary?.razao.outros_credito ?? 0)} />
      </div>
      <div className="text-right text-[10px] text-slate-500">
        Gera o CSV pronto para importar no ERP.
        {csvBlocked ? <span title={`Revise os lançamentos incompletos: ${data.integridade.movimentos_incompletos.map((item) => item.data).join(", ")}`} className="mt-1 flex cursor-not-allowed items-center rounded bg-slate-300 px-2 py-1 text-[10px] font-semibold text-slate-600"><Download className="mr-1" size={12} />CSV bloqueado</span> : <><a href={`${API}/api/conciliacoes/${reconciliationId}/lancamentos-contabeis.csv`} className="mt-1 flex items-center rounded bg-teal-700 px-2 py-1 text-[10px] font-semibold text-white"><Download className="mr-1" size={12} />Gerar CSV</a><a href={`${API}/api/conciliacoes/${reconciliationId}/lancamentos-contabeis.pdf`} className="mt-1 flex items-center rounded border border-slate-300 bg-white px-2 py-1 text-[10px] font-semibold text-slate-700"><FileText className="mr-1" size={12} />Gerar PDF</a></>}
      </div>
    </section>
  );
}

type PendingRule = {
  id: string;
  movimento_id?: string;
  usado_no_periodo?: boolean;
  data: string;
  historico: string;
  valor: string;
  natureza: string;
  natureza_contabil?: string;
  palavras_comprovante?: string[];
  palavras_comprovante_banco?: string[];
  palavras_comprovante_rfb?: string[];
  movimento_composto?: boolean;
  componentes_documento?: string[];
  componentes_cobertos?: { componente: string; valor: string }[];
  tipo_componente?: string;
  valor_documento?: string;
  composicao_simples?: string;
  tarifa_no_extrato?: boolean;
  tarifa_referente_ao_comprovante?: boolean;
  tarifa_referencia_nome?: string;
  tarifa_referencia_valor?: string;
  tarifa_referencia_data?: string;
  comprovante_arquivo_id?: string | null;
  comprovante_pagina?: number | null;
  comprovante_rfb_arquivo_id?: string | null;
  comprovante_rfb_pagina?: number | null;
  comprovante_tipo?: string | null;
  comprovante_confere?: boolean;
  ajuste_getnet?: boolean;
  gatilho_sugerido?: string;
  complemento_sugerido?: string;
};

function LoanReceiptNotice({ compact = false }: { compact?: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded border border-amber-200 bg-amber-50 font-semibold text-amber-800 ${compact ? "px-1.5 py-0.5 text-[10px]" : "px-2 py-1 text-xs"}`}
    >
      <FileText size={compact ? 12 : 14} />
      Comprovante de empréstimos/financiamentos
    </span>
  );
}

function MovementUsageToggle({
  used,
  busy = false,
  onToggle,
}: {
  used: boolean;
  busy?: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      aria-pressed={used}
      title={used ? "Usar neste período" : "Não usar neste período"}
      disabled={busy}
      onClick={onToggle}
      className={`inline-flex items-center gap-1.5 rounded-full border px-1.5 py-1 text-[10px] font-semibold transition disabled:cursor-wait disabled:opacity-60 ${used ? "border-teal-200 bg-teal-50 text-teal-800" : "border-slate-300 bg-slate-100 text-slate-500"}`}
    >
      <span className={`flex h-3.5 w-6 items-center rounded-full px-0.5 ${used ? "justify-end bg-teal-700" : "justify-start bg-slate-400"}`}>
        <span className="h-2.5 w-2.5 rounded-full bg-white" />
      </span>
      {used ? "Usar" : "Ignorar"}
    </button>
  );
}
type SavedRule = {
  id: string;
  gatilho: string;
  gatilho_comprovante?: string;
  texto_exclusao?: string;
  natureza: string;
  natureza_contabil?: string;
  tipo_componente?: string;
  conta_debito: string;
  conta_credito: string;
  historico: string;
  complemento: string;
  escopo?: "periodo" | "global";
  criada_em?: string;
  cobertos: number;
  movimentos?: { data: string; historico: string; texto_extrato?: string; texto_comprovante?: string; tem_comprovante?: boolean; valor: string; tipo_componente?: string; natureza: string; natureza_contabil: string }[];
};

type IgnoredRule = Pick<SavedRule, "id" | "gatilho" | "gatilho_comprovante" | "texto_exclusao" | "tipo_componente" | "historico">;
type RuleCoverageMatch = {
  data: string;
  historico: string;
  componente?: string;
  fonte: string;
};
type RulePreview = {
  quantidade: number;
  lancamentos: RuleCoverageMatch[];
  motivo: string;
  gatilho?: string;
  gatilho_comprovante?: string;
  texto_exclusao?: string;
};
type RuleSaveBody = {
  gatilho: string;
  gatilho_comprovante: string;
  texto_exclusao: string;
  natureza: string;
  tipo_componente: string;
  escopo: string;
  conta_debito: string;
  conta_credito: string;
  historico: string;
  complemento: string;
};
type CoverageModal = {
  item: PendingRule | SavedRule;
  body: RuleSaveBody;
  preview: RulePreview;
  existing: boolean;
};

type IndependentRuleRow = {
  id: string;
  data: string;
  data_emissao?: string;
  data_vencimento?: string;
  data_pagamento?: string;
  texto: string;
  documento: string;
  forma_pagamento?: string;
  tipo_pagamento?: string;
  tipo_pagamento_label?: string;
  classificacao_antecipacao?: string;
  classificacao_antecipacao_label?: string;
  motivo_antecipacao?: string;
  gera_lancamento?: string;
  destino_lancamento?: string;
  destino_lancamento_label?: string;
  modo_lancamento?: string;
  modo_lancamento_label?: string;
  linhas_csv?: string;
  conta_antecipacao?: string;
  motivo_nao_geracao?: string;
  tipo_lancamento?: string;
  tipo_lancamento_label?: string;
  valor: string;
  arquivo_id?: string;
  pagina?: number;
  regra_id?: string;
  conta_debito?: string;
  conta_credito?: string;
  historico_contabil?: string;
  complemento?: string;
};
type IndependentRule = {
  id: string;
  gatilho: string;
  conta_debito: string;
  conta_credito: string;
  historico: string;
  complemento: string;
  tipo_componente?: string;
  tipo_componente_label?: string;
  cobertos: number;
};
type IndependentRulesData = {
  pendentes: IndependentRuleRow[];
  classificados: IndependentRuleRow[];
  salvas: IndependentRule[];
  resumo: { total: number; classificados: number; pendentes: number };
};

function IndependentRulesPanel({
  reconciliationId,
  source,
  title,
  triggerLabel,
  onView,
}: {
  reconciliationId: string;
  source: "maquininha" | "nota";
  title: string;
  triggerLabel: string;
  onView: (viewer: Viewer) => void;
}) {
  const [data, setData] = useState<IndependentRulesData>({ pendentes: [], classificados: [], salvas: [], resumo: { total: 0, classificados: 0, pendentes: 0 } });
  const [drafts, setDrafts] = useState<Record<string, Record<string, string>>>({});
  const [activeView, setActiveView] = useState<"pending" | "saved" | "classified">("pending");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState("");
  const [catalog, setCatalog] = useState<{
    contas: string[];
    historicos: string[];
  }>({ contas: [], historicos: [] });
  useAutoDismissMessage(message, setMessage);
  async function load() {
    const response = await fetch(`${API}/api/conciliacoes/${reconciliationId}/regras-fonte/${source}`, { cache: "no-store" });
    if (response.ok) setData(await response.json());
  }
  useEffect(() => {
    load();
    fetch(`${API}/api/documentos-importantes/catalogo`)
      .then((response) => (response.ok ? response.json() : null))
      .then((loadedCatalog) => {
        if (loadedCatalog) setCatalog(loadedCatalog);
      });
  }, [reconciliationId, source]);
  const value = (id: string, field: string, fallback = "") => drafts[id]?.[field] ?? fallback;
  const defaultComplement = (row: IndependentRuleRow) => {
    if (source === "maquininha") return "Conforme extrato de maquininha";
    const document = row.documento && row.documento !== "—" ? row.documento : "Conforme nota fiscal";
    return row.tipo_lancamento_label && row.tipo_lancamento_label !== "Principal" ? `${document} - ${row.tipo_lancamento_label}` : document;
  };
  const change = (id: string, field: string, input: string) => setDrafts((current) => ({ ...current, [id]: { ...current[id], [field]: input } }));
  async function save(row: IndependentRuleRow) {
    const body = {
      gatilho: value(row.id, "gatilho", row.texto),
      conta_debito: value(row.id, "debito"),
      conta_credito: value(row.id, "credito"),
      historico: value(row.id, "historico"),
      complemento: value(row.id, "complemento", defaultComplement(row)),
      escopo: "global",
      tipo_componente: row.tipo_lancamento || "PRINCIPAL",
    };
    if (!body.gatilho.trim() || !body.conta_debito.trim() || !body.conta_credito.trim() || !body.historico.trim()) {
      setMessage("Preencha gatilho, débito, crédito e histórico.");
      return;
    }
    setBusy(row.id);
    try {
      const response = await fetch(`${API}/api/conciliacoes/${reconciliationId}/regras-fonte/${source}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const result = await response.json().catch(() => null);
      if (!response.ok) throw new Error(result?.detail ?? "Não foi possível salvar a regra.");
      setData(result.regras);
      setDrafts((current) => ({ ...current, [row.id]: {} }));
      setMessage("Regra salva nesta aba.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Não foi possível salvar a regra.");
    } finally {
      setBusy("");
    }
  }
  async function remove(rule: IndependentRule) {
    setBusy(rule.id);
    try {
      const response = await fetch(`${API}/api/conciliacoes/${reconciliationId}/regras-fonte/${source}/${rule.id}`, { method: "DELETE" });
      const result = await response.json().catch(() => null);
      if (!response.ok) throw new Error(result?.detail ?? "Não foi possível excluir a regra.");
      setData(result.regras);
      setMessage(result.message ?? "Regra excluída.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Não foi possível excluir a regra.");
    } finally {
      setBusy("");
    }
  }
  const money = (value: string) => formatMoney(value);
  const isNoteSource = source === "nota";
  const tabs = [
    { id: "pending" as const, label: "Regras a criar", count: data.pendentes.length },
    { id: "saved" as const, label: "Regras criadas", count: data.salvas.length },
    { id: "classified" as const, label: "Classificados", count: data.classificados.length },
  ];
  const RowFileButton = ({ row }: { row: IndependentRuleRow }) =>
    row.arquivo_id ? (
      <button
        onClick={() => onView({ arquivoId: String(row.arquivo_id), pagina: Number(row.pagina || 1), titulo: title })}
        title="Visualizar arquivo"
        aria-label="Visualizar arquivo"
        className="rounded p-1 text-slate-700 hover:bg-slate-100"
      >
        <Eye size={15} />
      </button>
    ) : null;
  const isSplitNoteRule = (row: IndependentRuleRow) => isNoteSource && ["ANTECIPACAO_CLIENTES", "BAIXA_ANTECIPACAO"].includes(row.tipo_lancamento || "");
  const noteComponentLabel = (row: IndependentRuleRow) =>
    row.tipo_lancamento === "BAIXA_ANTECIPACAO" ? "Baixa Ant." : row.tipo_lancamento_label || "Principal";
  const pendingSourceGroups = data.pendentes.reduce<IndependentRuleRow[][]>((groups, row) => {
    if (!isSplitNoteRule(row)) {
      groups.push([row]);
      return groups;
    }
    const groupKey = row.id.split(":")[0];
    const group = groups.find((items) => items.some((item) => item.id.split(":")[0] === groupKey));
    if (group) group.push(row);
    else groups.push([row]);
    return groups;
  }, []).map((group) => [...group].sort((left, right) => {
    const order = { ANTECIPACAO_CLIENTES: 1, BAIXA_ANTECIPACAO: 2 } as Record<string, number>;
    return (order[left.tipo_lancamento || ""] || 9) - (order[right.tipo_lancamento || ""] || 9);
  }));
  const renderPendingSourceRow = (row: IndependentRuleRow, grouped = false) => {
    const splitNoteRule = isSplitNoteRule(row);
    return (
      <tr className={`border-t align-top ${grouped ? "border-x-2 border-sky-200" : ""} ${row.tipo_lancamento === "ANTECIPACAO_CLIENTES" ? "bg-violet-50/30" : row.tipo_lancamento === "BAIXA_ANTECIPACAO" ? "bg-indigo-50/30" : ""}`} key={row.id}>
        <td className="break-words px-2 py-1.5">{grouped ? "—" : row.data}</td>
        <td className="break-words px-2 py-1.5">
          {grouped ? (
            <span className="font-semibold text-slate-800">{noteComponentLabel(row)}</span>
          ) : (
            <>
              <span className="line-clamp-2 font-medium text-slate-800" title={row.texto}>{row.texto}</span>
              <span className="text-slate-500">{row.documento}</span>
            </>
          )}
        </td>
        {isNoteSource && (
          <td className="break-words px-2 py-1.5">
            <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold ${row.tipo_lancamento === "BAIXA_ANTECIPACAO" ? "bg-indigo-50 text-indigo-800" : row.tipo_lancamento === "ANTECIPACAO_CLIENTES" ? "bg-violet-50 text-violet-800" : "bg-slate-100 text-slate-600"}`}>
              {noteComponentLabel(row)}
            </span>
          </td>
        )}
        {isNoteSource && (
          <td className="break-words px-2 py-1.5">
            {grouped ? (
              <span className="text-[10px] text-slate-500">{row.data}</span>
            ) : (
              <div className="flex flex-col items-start gap-1">
                <span className={`inline-flex max-w-full rounded-full px-2 py-1 text-[10px] font-semibold ${row.forma_pagamento && row.forma_pagamento !== "—" ? "bg-amber-50 text-amber-800" : "bg-slate-100 text-slate-500"}`}>
                  {row.tipo_pagamento_label || row.forma_pagamento || "—"}
                </span>
                <span className="block text-[10px] text-slate-500">
                  Emissão {row.data_emissao || row.data || "—"} · Pgto. {row.data_pagamento || "—"}
                </span>
                <span title={row.motivo_antecipacao || ""} className={`inline-flex max-w-full rounded-full px-2 py-1 text-[10px] font-semibold ${row.classificacao_antecipacao?.startsWith("ANTECIPACAO") ? "bg-violet-50 text-violet-800" : row.classificacao_antecipacao === "NORMAL" ? "bg-emerald-50 text-emerald-800" : "bg-amber-50 text-amber-800"}`}>
                  {row.classificacao_antecipacao_label || "Revisar"}
                </span>
                <span title={row.motivo_nao_geracao || row.destino_lancamento_label || row.destino_lancamento || ""} className={`inline-flex max-w-full rounded-full px-2 py-1 text-[10px] font-semibold ${row.gera_lancamento === "Antecipação + baixa" ? "bg-violet-50 text-violet-800" : row.gera_lancamento === "Sim" ? "bg-teal-50 text-teal-800" : row.gera_lancamento === "Via extrato" ? "bg-sky-50 text-sky-800" : row.gera_lancamento === "Aguardando forma" || row.gera_lancamento === "Conferir" ? "bg-amber-50 text-amber-800" : "bg-slate-100 text-slate-600"}`}>
                  {row.gera_lancamento || "—"}
                </span>
              </div>
            )}
          </td>
        )}
        <td className="break-words px-2 py-1.5 font-semibold">{money(row.valor)}</td>
        <td className="px-2 py-1">
          <input value={value(row.id, "gatilho", row.texto)} onChange={(event) => change(row.id, "gatilho", event.target.value)} className="w-full min-w-0 rounded border px-2 py-1" />
        </td>
        <td className="px-2 py-1">
          <input
            list="catalogo-contas"
            value={value(row.id, "debito")}
            onChange={(event) => {
              change(row.id, "debito", event.target.value);
              showInputStart(event.currentTarget);
            }}
            onBlur={(event) => showInputStart(event.currentTarget)}
            className="w-full min-w-0 rounded border px-2 py-1 pr-5 text-left"
            placeholder="Selecionar"
          />
        </td>
        <td className="px-2 py-1">
          <input
            list="catalogo-contas"
            value={value(row.id, "credito")}
            onChange={(event) => {
              change(row.id, "credito", event.target.value);
              showInputStart(event.currentTarget);
            }}
            onBlur={(event) => showInputStart(event.currentTarget)}
            className="w-full min-w-0 rounded border px-2 py-1 pr-5 text-left"
            placeholder="Selecionar"
          />
        </td>
        <td className="px-2 py-1">
          <input
            list="catalogo-historicos"
            value={value(row.id, "historico")}
            onChange={(event) => {
              change(row.id, "historico", event.target.value);
              showInputStart(event.currentTarget);
            }}
            onBlur={(event) => showInputStart(event.currentTarget)}
            className="w-full min-w-0 rounded border px-2 py-1 pr-5 text-left"
            placeholder="Selecionar"
          />
        </td>
        <td className="px-2 py-1"><input value={value(row.id, "complemento", defaultComplement(row))} onChange={(event) => change(row.id, "complemento", event.target.value)} className="w-full min-w-0 rounded border px-2 py-1" /></td>
        <td className="px-2 py-1">
          <button
            disabled={busy === row.id}
            onClick={() => save(row)}
            title="Salvar regra"
            aria-label="Salvar regra"
            className="mb-1 inline-flex h-7 w-7 items-center justify-center rounded bg-teal-700 text-white hover:bg-teal-800 disabled:opacity-60"
          >
            {busy === row.id ? <RefreshCw className="animate-spin" size={14} /> : <CheckCircle2 size={14} />}
          </button>
          <RowFileButton row={row} />
        </td>
      </tr>
    );
  };
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5">
      <datalist id="catalogo-contas">
        {catalog.contas.map((option) => (
          <option value={option} key={option} />
        ))}
      </datalist>
      <datalist id="catalogo-historicos">
        {catalog.historicos.map((option) => (
          <option value={option} key={option} />
        ))}
      </datalist>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-semibold">Regras de {title}</h2>
          <p className="text-sm text-slate-500">Classificação independente e CSV próprio desta aba.</p>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="rounded-full bg-slate-100 px-3 py-1 font-semibold text-slate-700">{data.resumo.classificados}/{data.resumo.total} classificados</span>
          <a href={`${API}/api/conciliacoes/${reconciliationId}/regras-fonte/${source}/csv`} className="inline-flex items-center gap-1 rounded bg-teal-700 px-3 py-1.5 font-semibold text-white">
            <Download size={14} />
            Gerar CSV
          </a>
        </div>
      </div>
      {message && <p className="mb-3 rounded bg-teal-50 p-2 text-xs text-teal-900">{message}</p>}
      <div className="mb-3 flex flex-wrap gap-2">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveView(tab.id)}
            className={`rounded-md border px-3 py-2 text-xs font-semibold ${activeView === tab.id ? "border-teal-700 bg-teal-700 text-white" : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"}`}
          >
            {tab.label} ({tab.count})
          </button>
        ))}
      </div>
      {activeView === "pending" && (
        <div className="max-h-[calc(100dvh-360px)] overflow-y-auto overflow-x-hidden rounded-lg border">
          <table className="w-full table-fixed text-left text-[11px]">
            <thead className="sticky top-0 z-10 bg-slate-50 text-[10px] uppercase text-slate-500">
              <tr>
                <th className="w-[6%] px-2 py-2">Data</th>
                <th className={`${isNoteSource ? "w-[13%]" : "w-[18%]"} px-2 py-2`}>{triggerLabel}</th>
                {isNoteSource && <th className="w-[9%] px-2 py-2">Tipo</th>}
                {isNoteSource && <th className="w-[13%] px-2 py-2">Pagamento</th>}
                <th className="w-[8%] px-2 py-2">Valor</th>
                <th className="w-[11%] px-2 py-2">Gatilho</th>
                <th className="w-[10%] px-2 py-2">D</th>
                <th className="w-[10%] px-2 py-2">C</th>
                <th className="w-[10%] px-2 py-2">H</th>
                <th className="w-[7%] px-2 py-2">Compl.</th>
                <th className="w-[3%] px-2 py-2">Ação</th>
              </tr>
            </thead>
            <tbody>
              {pendingSourceGroups.map((group) => {
                const splitGroup = group.some(isSplitNoteRule);
                const first = group[0];
                if (!splitGroup) return renderPendingSourceRow(first);
                return (
                  <Fragment key={first.id.split(":")[0]}>
                    <tr className="border-t bg-sky-50">
                      <td colSpan={isNoteSource ? 11 : 9} className="border-l-4 border-sky-400 px-3 py-2">
                        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                          <strong>{first.texto}</strong>
                          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-600">NF {first.documento}</span>
                          <span className="text-[10px] font-semibold text-sky-800">2 lançamentos: Antecipação + Baixa Ant.</span>
                          <span className="text-[10px] text-slate-500">Emissão {first.data_emissao || "—"} · Pgto. {first.data_pagamento || "—"}</span>
                          <RowFileButton row={first} />
                        </div>
                      </td>
                    </tr>
                    {group.map((row) => renderPendingSourceRow(row, true))}
                    <tr className="bg-sky-50">
                      <td colSpan={isNoteSource ? 11 : 9} className="border-x-2 border-b-2 border-sky-200 px-3 py-1" />
                    </tr>
                  </Fragment>
                );
              })}
              {!data.pendentes.length && (
                <tr><td className="px-2 py-6 text-center text-slate-500" colSpan={isNoteSource ? 11 : 9}>Nenhum registro pendente nesta aba.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
      {activeView === "saved" && (
        <div className="max-h-[calc(100dvh-360px)] overflow-y-auto overflow-x-hidden rounded-lg border">
          <table className="w-full table-fixed text-left text-[11px]">
            <thead className="sticky top-0 z-10 bg-slate-50 text-[10px] uppercase text-slate-500">
              <tr>
                <th className="w-[12%] px-3 py-2">Tipo</th>
                <th className="w-[18%] px-3 py-2">Gatilho</th>
                <th className="w-[7%] px-3 py-2">Cobertos</th>
                <th className="w-[15%] px-3 py-2">Débito</th>
                <th className="w-[15%] px-3 py-2">Crédito</th>
                <th className="w-[15%] px-3 py-2">Histórico</th>
                <th className="w-[14%] px-3 py-2">Complemento</th>
                <th className="w-[4%] px-3 py-2">Ação</th>
              </tr>
            </thead>
            <tbody>
              {data.salvas.map((rule) => (
                <tr className="border-t" key={rule.id}>
                  <td className="break-words px-3 py-2">{rule.tipo_componente_label || rule.tipo_componente || "Principal"}</td>
                  <td className="break-words px-3 py-2 font-semibold text-slate-800">{rule.gatilho}</td>
                  <td className="px-3 py-2">{rule.cobertos}</td>
                  <td className="break-words px-3 py-2">{rule.conta_debito}</td>
                  <td className="break-words px-3 py-2">{rule.conta_credito}</td>
                  <td className="break-words px-3 py-2">{rule.historico}</td>
                  <td className="break-words px-3 py-2">{rule.complemento}</td>
                  <td className="px-3 py-2"><button disabled={busy === rule.id} onClick={() => remove(rule)} className="rounded p-1 text-red-600 hover:bg-red-50" title="Excluir regra"><Trash2 size={15} /></button></td>
                </tr>
              ))}
              {!data.salvas.length && <tr><td className="px-3 py-6 text-center text-slate-500" colSpan={8}>Nenhuma regra criada.</td></tr>}
            </tbody>
          </table>
        </div>
      )}
      {activeView === "classified" && (
        <div className="max-h-[calc(100dvh-360px)] overflow-y-auto overflow-x-hidden rounded-lg border">
          <table className="w-full table-fixed text-left text-[11px]">
            <thead className="sticky top-0 z-10 bg-slate-50 text-[10px] uppercase text-slate-500">
              <tr>
                <th className="w-[7%] px-3 py-2">Data</th>
                <th className={`${isNoteSource ? "w-[14%]" : "w-[24%]"} px-3 py-2`}>{triggerLabel}</th>
                {isNoteSource && <th className="w-[9%] px-3 py-2">Tipo</th>}
                {isNoteSource && <th className="w-[9%] px-3 py-2">Pgto.</th>}
                {isNoteSource && <th className="w-[10%] px-3 py-2">Classif.</th>}
                {isNoteSource && <th className="w-[9%] px-3 py-2">CSV</th>}
                <th className="w-[7%] px-3 py-2">Valor</th>
                <th className="w-[8%] px-3 py-2">D</th>
                <th className="w-[8%] px-3 py-2">C</th>
                <th className="w-[8%] px-3 py-2">H</th>
                <th className="w-[7%] px-3 py-2">Compl.</th>
                <th className="w-[3%] px-3 py-2">Arq.</th>
              </tr>
            </thead>
            <tbody>
              {data.classificados.map((row) => (
                <tr className="border-t" key={row.id}>
                  <td className="break-words px-3 py-2">{row.data}</td>
                  <td className="break-words px-3 py-2"><span className="block font-semibold text-slate-800">{row.texto}</span><span className="text-slate-500">{row.documento}</span></td>
                  {isNoteSource && <td className="break-words px-3 py-2">{row.tipo_lancamento_label || "Principal"}</td>}
                  {isNoteSource && <td className="break-words px-3 py-2">{row.tipo_pagamento_label || row.forma_pagamento || "—"}</td>}
                  {isNoteSource && <td className="break-words px-3 py-2">{row.classificacao_antecipacao_label || "—"}</td>}
                  {isNoteSource && (
                    <td className="break-words px-3 py-2">
                      <span className={row.gera_lancamento === "Antecipação + baixa" ? "font-semibold text-violet-700" : ""}>
                        {row.gera_lancamento || "—"}
                      </span>
                      {row.conta_antecipacao && row.conta_antecipacao !== "—" && (
                        <span className="block text-[10px] text-slate-500">{row.conta_antecipacao}</span>
                      )}
                    </td>
                  )}
                  <td className="break-words px-3 py-2 font-semibold">{money(row.valor)}</td>
                  <td className="break-words px-3 py-2">{row.conta_debito}</td>
                  <td className="break-words px-3 py-2">{row.conta_credito}</td>
                  <td className="break-words px-3 py-2">{row.historico_contabil}</td>
                  <td className="break-words px-3 py-2">{row.complemento}</td>
                  <td className="px-3 py-2"><RowFileButton row={row} /></td>
                </tr>
              ))}
              {!data.classificados.length && <tr><td className="px-3 py-6 text-center text-slate-500" colSpan={isNoteSource ? 12 : 8}>Nenhum registro classificado.</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function LegacyAdvancedRulesPanel({
  reconciliationId,
}: {
  reconciliationId: string;
}) {
  const [pending, setPending] = useState<PendingRule[]>([]),
    [saved, setSaved] = useState<SavedRule[]>([]),
    [view, setView] = useState<"pending" | "saved">("pending"),
    [filter, setFilter] = useState(""),
    [drafts, setDrafts] = useState<Record<string, Record<string, string>>>({}),
    [message, setMessage] = useState("");
  useAutoDismissMessage(message, setMessage);
  async function loadRules() {
    const response = await fetch(
      `${API}/api/conciliacoes/${reconciliationId}/regras-contabeis`,
    );
    if (!response.ok) return setMessage("Não foi possível carregar as regras.");
    const data = await response.json();
    setPending(data.pendentes);
    setSaved(data.salvas);
  }
  useEffect(() => {
    loadRules();
  }, [reconciliationId]);
  function field(item: PendingRule, name: string, fallback = "") {
    return drafts[item.id]?.[name] ?? fallback;
  }
  function change(item: PendingRule, name: string, value: string) {
    setDrafts((items) => ({
      ...items,
      [item.id]: { ...items[item.id], [name]: value },
    }));
  }
  async function save(item: PendingRule) {
    const response = await fetch(
      `${API}/api/conciliacoes/${reconciliationId}/regras-contabeis`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          gatilho: field(item, "gatilho", item.historico),
          natureza: item.natureza,
          escopo: "global",
          conta_debito: field(item, "debito"),
          conta_credito: field(item, "credito"),
          historico: field(item, "historico", item.historico),
          complemento: field(item, "complemento", "Conforme extrato bancário"),
        }),
      },
    );
    if (!response.ok)
      return setMessage(
        (await response.json()).detail ?? "Não foi possível salvar a regra.",
      );
    setMessage("Regra salva e aplicada aos lançamentos compatíveis.");
    loadRules();
  }
  async function remove(id: string) {
    await fetch(`${API}/api/regras-contabeis/${id}`, { method: "DELETE" });
    loadRules();
  }
  const visible = pending.filter((item) =>
    item.historico.toLowerCase().includes(filter.toLowerCase()),
  );
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-3">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <button
          onClick={() => setView("pending")}
          className={`rounded-md px-3 py-1.5 text-xs font-semibold ${view === "pending" ? "bg-teal-700 text-white" : "border text-slate-600"}`}
        >
          Regras a criar ({pending.length})
        </button>
        <button
          onClick={() => setView("saved")}
          className={`rounded-md px-3 py-1.5 text-xs font-semibold ${view === "saved" ? "bg-teal-700 text-white" : "border text-slate-600"}`}
        >
          Regras salvas ({saved.length})
        </button>
        {view === "pending" && (
          <input
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
            className="ml-auto rounded-md border px-2 py-1.5 text-xs"
            placeholder="Filtrar histórico"
          />
        )}
      </div>
      {message && <p className="mb-2 text-xs text-teal-800">{message}</p>}
      {view === "pending" ? (
        <div className="max-h-[calc(100dvh-390px)] overflow-auto rounded-md border">
          <table className="w-full min-w-[1120px] text-left text-xs">
            <thead className="sticky top-0 bg-slate-50 text-[10px] uppercase text-slate-500">
              <tr>
                {[
                  "Data",
                  "Histórico",
                  "Valor",
                  "Gatilho",
                  "Débito",
                  "Crédito",
                  "Histórico contábil",
                  "Complemento",
                  "",
                ].map((item) => (
                  <th className="px-2 py-2" key={item}>
                    {item}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {visible.map((item) => (
                <tr className="border-t align-top" key={item.id}>
                  <td className="whitespace-nowrap px-2 py-2">{item.data}</td>
                  <td className="max-w-56 px-2 py-2">{item.historico}</td>
                  <td className="whitespace-nowrap px-2 py-2">{item.valor}</td>
                  <td className="px-2 py-1">
                    <input
                      value={field(item, "gatilho", item.historico)}
                      onChange={(event) =>
                        change(item, "gatilho", event.target.value)
                      }
                      className="w-36 rounded border px-1.5 py-1"
                    />
                  </td>
                  <td className="px-2 py-1">
                    <input
                      value={field(item, "debito")}
                      onChange={(event) =>
                        change(item, "debito", event.target.value)
                      }
                      className="w-32 rounded border px-1.5 py-1"
                      placeholder="Conta débito"
                    />
                  </td>
                  <td className="px-2 py-1">
                    <input
                      value={field(item, "credito")}
                      onChange={(event) =>
                        change(item, "credito", event.target.value)
                      }
                      className="w-32 rounded border px-1.5 py-1"
                      placeholder="Conta crédito"
                    />
                  </td>
                  <td className="px-2 py-1">
                    <input
                      value={field(item, "historico", item.historico)}
                      onChange={(event) =>
                        change(item, "historico", event.target.value)
                      }
                      className="w-40 rounded border px-1.5 py-1"
                    />
                  </td>
                  <td className="px-2 py-1">
                    <input
                      value={field(
                        item,
                        "complemento",
                        "Conforme extrato bancário",
                      )}
                      onChange={(event) =>
                        change(item, "complemento", event.target.value)
                      }
                      className="w-40 rounded border px-1.5 py-1"
                    />
                  </td>
                  <td className="px-2 py-1">
                    <button
                      onClick={() => save(item)}
                      className="rounded bg-teal-700 px-2 py-1 text-white"
                    >
                      Salvar
                    </button>
                  </td>
                </tr>
              ))}
              {!visible.length && (
                <tr>
                  <td
                    className="px-3 py-6 text-center text-slate-500"
                    colSpan={9}
                  >
                    Nenhum lançamento sem regra.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="max-h-[calc(100dvh-390px)] overflow-auto rounded-md border">
          <table className="w-full min-w-[760px] text-left text-xs">
            <thead className="sticky top-0 bg-slate-50 text-[10px] uppercase text-slate-500">
              <tr>
                {[
                  "Gatilho",
                  "Natureza",
                  "Débito",
                  "Crédito",
                  "Histórico",
                  "Cobertos",
                  "",
                ].map((item) => (
                  <th className="px-2 py-2" key={item}>
                    {item}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {saved.map((item) => (
                <tr className="border-t" key={item.id}>
                  <td className="px-2 py-2">{item.gatilho}</td>
                  <td className="px-2 py-2">{item.natureza}</td>
                  <td className="px-2 py-2">{item.conta_debito}</td>
                  <td className="px-2 py-2">{item.conta_credito}</td>
                  <td className="px-2 py-2">{item.historico}</td>
                  <td className="px-2 py-2">{item.cobertos}</td>
                  <td className="px-2 py-1">
                    <button
                      onClick={() => remove(item.id)}
                      className="rounded border border-red-300 px-2 py-1 text-red-700"
                    >
                      Excluir
                    </button>
                  </td>
                </tr>
              ))}
              {!saved.length && (
                <tr>
                  <td
                    className="px-3 py-6 text-center text-slate-500"
                    colSpan={7}
                  >
                    Nenhuma regra salva.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function AdvancedRulesPanel({
  reconciliationId,
  version,
  onView,
  onRulesChanged,
}: {
  reconciliationId: string;
  version: number;
  onView: (viewer: Viewer) => void;
  onRulesChanged: () => void;
}) {
  const [pending, setPending] = useState<PendingRule[]>([]);
  const [saved, setSaved] = useState<SavedRule[]>([]);
  const [ignored, setIgnored] = useState<IgnoredRule[]>([]);
  const [previews, setPreviews] = useState<Record<string, RulePreview>>({});
  const [coverageModal, setCoverageModal] = useState<CoverageModal | null>(null);
  const [recentRuleId, setRecentRuleId] = useState<string | null>(null);
  const [account, setAccount] = useState("Sem conta");
  const [drafts, setDrafts] = useState<Record<string, Record<string, string>>>(
    {},
  );
  const [view, setView] = useState<"pending" | "saved" | "hidden">("pending");
  const [filter, setFilter] = useState(""),
    [wordPicker, setWordPicker] = useState<string | null>(null),
    [receiptWordPicker, setReceiptWordPicker] = useState<string | null>(null),
    [keywordMode, setKeywordMode] = useState<Record<string, "full" | "words">>(
      {},
    );
  const cleanHistory = (value: string) =>
    value
      .replace(/[—–\-_/]+/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  const [message, setMessage] = useState("");
  useAutoDismissMessage(message, setMessage);
  const [busyRuleId, setBusyRuleId] = useState<string | null>(null);
  const [confirmClearAll, setConfirmClearAll] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<SavedRule | null>(null);
  const [csvPermitted, setCsvPermitted] = useState(true);
  const [catalog, setCatalog] = useState<{
    contas: string[];
    historicos: string[];
  }>({ contas: [], historicos: [] });
  const loadRequest = useRef(0);
  const recentRuleTimer = useRef<number | null>(null);
  useEffect(() => () => {
    if (recentRuleTimer.current) window.clearTimeout(recentRuleTimer.current);
  }, []);
  function markRecentRule(id: string) {
    setRecentRuleId(id);
    if (recentRuleTimer.current) window.clearTimeout(recentRuleTimer.current);
    recentRuleTimer.current = window.setTimeout(() => {
      setRecentRuleId((current) => (current === id ? null : current));
    }, 20000);
  }
  function componentOrder(component = "") {
    return ({
      PRINCIPAL: 1,
      VALOR_COBRADO: 1,
      MULTA: 2,
      JUROS: 3,
      ENCARGOS: 4,
      DESCONTO: 5,
      ABATIMENTO: 6,
      DESCONTO_ABATIMENTO: 7,
    } as Record<string, number>)[component] ?? 99;
  }
  function savedMovementKeys(rule: SavedRule) {
    return (rule.movimentos ?? [])
      .map((movement) =>
        [
          movement.data,
          movement.texto_extrato || movement.historico,
          movement.texto_comprovante || "",
          movement.natureza_contabil,
        ].join("|"),
      );
  }
  function savedRulesOverlap(left: SavedRule, right: SavedRule) {
    const rightKeys = new Set(savedMovementKeys(right));
    return savedMovementKeys(left).some((key) => rightKeys.has(key));
  }
  function sortSavedRules(items: SavedRule[], topRuleId?: string | null) {
    const topRule = topRuleId ? items.find((item) => item.id === topRuleId) : null;
    const topRuleIsCompositeMember = Boolean(
      topRule &&
        items.some(
          (item) =>
            item.id !== topRule.id &&
            savedRulesOverlap(item, topRule) &&
            componentOrder(item.tipo_componente) !== componentOrder(topRule.tipo_componente),
        ),
    );
    return [...items].sort((left, right) => {
      if (topRuleId && !topRuleIsCompositeMember && left.id !== right.id) {
        if (left.id === topRuleId) return -1;
        if (right.id === topRuleId) return 1;
      }
      return String(right.criada_em || "").localeCompare(String(left.criada_em || ""));
    });
  }
  function applyRulesSnapshot(rules: { pendentes: PendingRule[]; salvas: SavedRule[]; ignoradas?: IgnoredRule[]; integridade?: { csv_permitido?: boolean } }, topRuleId?: string | null) {
    loadRequest.current += 1;
    setPending(rules.pendentes.map((item) => ({ ...item, historico: cleanHistory(item.historico) })));
    setSaved(sortSavedRules(rules.salvas.map((item) => ({ ...item, historico: cleanHistory(item.historico) })), topRuleId ?? recentRuleId));
    setIgnored(rules.ignoradas ?? []);
    setCsvPermitted(rules.integridade?.csv_permitido !== false);
  }
  async function load() {
    const request = ++loadRequest.current;
    const [rulesResponse, accountResponse] = await Promise.all([
      fetch(`${API}/api/conciliacoes/${reconciliationId}/regras-contabeis`, { cache: "no-store" }),
      fetch(`${API}/api/conciliacoes/${reconciliationId}/conta-bancaria`, { cache: "no-store" }),
    ]);
    if (!rulesResponse.ok || !accountResponse.ok) {
      if (request !== loadRequest.current) return null;
      return setMessage("Não foi possível carregar as regras.");
    }
    const rules = await rulesResponse.json();
    const bankAccount = await accountResponse.json();
    if (request !== loadRequest.current) return null;
    applyRulesSnapshot(rules);
    setAccount(bankAccount.conta_contabil || "Sem conta");
    return rules;
  }
  useEffect(() => {
    load();
    fetch(`${API}/api/documentos-importantes/catalogo`)
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => {
        if (data) setCatalog(data);
      });
  }, [reconciliationId, version]);
  const value = (id: string, name: string, fallback = "") =>
    drafts[id]?.[name] ?? fallback;
  const change = (id: string, name: string, input: string) => {
    setDrafts((items) => ({ ...items, [id]: { ...items[id], [name]: input } }));
    setPreviews((items) => {
      const { [id]: _, ...remaining } = items;
      return remaining;
    });
  };
  const errorMessage = async (response: Response, fallback: string) => {
    try {
      const error = await response.json();
      return error.detail ?? error.message ?? fallback;
    } catch {
      return fallback;
    }
  };
  const requestWithTimeout = async (url: string, init: RequestInit, action: string) => {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 30000);
    try {
      return await fetch(url, { ...init, signal: controller.signal });
    } catch (error) {
      if (controller.signal.aborted) throw new Error(`${action} demorou mais de 30 segundos. Nenhuma confirmação foi recebida; tente novamente.`);
      throw error;
    } finally {
      window.clearTimeout(timeout);
    }
  };
  async function previewRule(item: PendingRule | SavedRule) {
    if (busyRuleId) return;
    const fields = defaults(item);
    const body = {
      gatilho: value(item.id, "gatilho", fields.gatilho),
      gatilho_comprovante: value(item.id, "gatilhoComprovante", fields.gatilhoComprovante),
      texto_exclusao: value(item.id, "textoExclusao", fields.textoExclusao),
      natureza: item.natureza_contabil || item.natureza,
      tipo_componente: item.tipo_componente || "",
      regra_id: "gatilho" in item ? item.id : "",
    };
    if (!body.gatilho.trim() && !body.gatilho_comprovante.trim()) {
      setPreviews((current) => ({ ...current, [item.id]: { quantidade: 0, lancamentos: [], motivo: "Informe um gatilho para validar a regra.", gatilho: body.gatilho, gatilho_comprovante: body.gatilho_comprovante, texto_exclusao: body.texto_exclusao } }));
      setMessage("Informe um gatilho para ver a cobertura da regra.");
      return;
    }
    setBusyRuleId(item.id);
    setMessage("Calculando cobertura da regra...");
    try {
      const response = await requestWithTimeout(`${API}/api/conciliacoes/${reconciliationId}/regras-contabeis/previa`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), cache: "no-store" }, "A validação da regra");
      if (!response.ok) {
        const message = await errorMessage(response, "Não foi possível validar o gatilho.");
        setMessage(message);
        return setPreviews((current) => ({ ...current, [item.id]: { quantidade: 0, lancamentos: [], motivo: message, gatilho: body.gatilho, gatilho_comprovante: body.gatilho_comprovante, texto_exclusao: body.texto_exclusao } }));
      }
      const result = await response.json();
      setPreviews((current) => ({ ...current, [item.id]: { ...result, gatilho: body.gatilho, gatilho_comprovante: body.gatilho_comprovante, texto_exclusao: body.texto_exclusao } }));
      setMessage(result.quantidade ? `Cobertura calculada: vai cobrir ${result.quantidade} lançamento(s).` : result.motivo || "Nenhum lançamento elegível corresponde ao gatilho informado.");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Não foi possível validar o gatilho.";
      setPreviews((current) => ({ ...current, [item.id]: { quantidade: 0, lancamentos: [], motivo: message, gatilho: body.gatilho, gatilho_comprovante: body.gatilho_comprovante, texto_exclusao: body.texto_exclusao } }));
      setMessage(message);
    } finally {
      setBusyRuleId(null);
    }
  }
  const defaults = (item: PendingRule | SavedRule) =>
    "gatilho" in item
      ? {
           gatilho: item.gatilho,
           gatilhoComprovante: item.gatilho_comprovante || "",
          textoExclusao: item.texto_exclusao || "",
          debito: item.conta_debito,
          credito: item.conta_credito,
          historico: item.historico,
          complemento: item.complemento,
        }
      : {
           gatilho: item.gatilho_sugerido || "",
           gatilhoComprovante: "",
          textoExclusao: "",
          debito: item.natureza_contabil === "Débito" ? account : "",
          credito: item.natureza_contabil === "Crédito" ? account : "",
          historico: item.ajuste_getnet ? item.historico : "",
          complemento: item.complemento_sugerido || "Conforme extrato bancário",
        };
  async function saveAccount() {
    const response = await fetch(
      `${API}/api/conciliacoes/${reconciliationId}/conta-bancaria`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ conta_contabil: account }),
      },
    );
    setMessage(
      response.ok
        ? "Conta bancária salva para este cliente e banco."
        : "Não foi possível salvar a conta bancária.",
    );
  }
  const movementIdFor = (item: PendingRule | SavedRule) =>
    "data" in item ? item.movimento_id || item.id.split(":")[0] : "";
  async function setMovementUsage(item: PendingRule | SavedRule, usar: boolean) {
    const movementId = movementIdFor(item);
    if (!movementId) return;
    setBusyRuleId(`movimento-${movementId}`);
    try {
      const response = await fetch(`${API}/api/conciliacoes/${reconciliationId}/movimentos-extrato/${movementId}/uso`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ usar }),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error(data?.detail ?? "Não foi possível atualizar o lançamento.");
      }
      setMessage(usar ? "Lançamento voltou a ser usado neste período." : "Lançamento marcado para não usar neste período.");
      onRulesChanged();
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : "Não foi possível atualizar o lançamento.");
    } finally {
      setBusyRuleId(null);
    }
  }
  function buildRuleBody(item: PendingRule | SavedRule, existing = false): RuleSaveBody {
    const fields = defaults(item);
    return {
      gatilho: value(item.id, "gatilho", fields.gatilho),
      gatilho_comprovante: value(item.id, "gatilhoComprovante", fields.gatilhoComprovante),
      texto_exclusao: value(item.id, "textoExclusao", fields.textoExclusao),
      natureza: item.natureza_contabil || item.natureza,
      tipo_componente: item.tipo_componente || "",
      escopo: existing && "gatilho" in item ? item.escopo || "global" : "global",
      conta_debito: value(item.id, "debito", fields.debito),
      conta_credito: value(item.id, "credito", fields.credito),
      historico: value(item.id, "historico", fields.historico),
      complemento: value(item.id, "complemento", fields.complemento),
    };
  }
  function ruleValidationMessage(body: RuleSaveBody) {
    const missing = [
      !body.gatilho.trim() && !body.gatilho_comprovante.trim() ? "gatilho" : "",
      !body.conta_debito.trim() ? "débito" : "",
      !body.conta_credito.trim() ? "crédito" : "",
      !body.historico.trim() ? "histórico contábil" : "",
    ].filter(Boolean);
    return missing.length ? `Preencha ${missing.join(", ")} antes de salvar a regra.` : "";
  }
  async function loadRulePreview(item: PendingRule | SavedRule, body: RuleSaveBody, existing = false) {
    const response = await requestWithTimeout(`${API}/api/conciliacoes/${reconciliationId}/regras-contabeis/previa`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        gatilho: body.gatilho,
        gatilho_comprovante: body.gatilho_comprovante,
        texto_exclusao: body.texto_exclusao,
        natureza: body.natureza,
        tipo_componente: body.tipo_componente,
        regra_id: existing && "gatilho" in item ? item.id : "",
      }),
      cache: "no-store",
    }, "A validação da regra");
    if (!response.ok) throw new Error(await errorMessage(response, "Não foi possível calcular a cobertura da regra."));
    const result = await response.json();
    const preview = { ...result, gatilho: body.gatilho, gatilho_comprovante: body.gatilho_comprovante, texto_exclusao: body.texto_exclusao } as RulePreview;
    setPreviews((current) => ({ ...current, [item.id]: preview }));
    return preview;
  }
  async function submitRule(item: PendingRule | SavedRule, body: RuleSaveBody, existing = false) {
    if (busyRuleId) return;
    setBusyRuleId(item.id);
    setMessage(existing ? "Atualizando regra..." : "Salvando regra...");
    const url = existing
      ? `${API}/api/conciliacoes/${reconciliationId}/regras-contabeis/${item.id}`
      : `${API}/api/conciliacoes/${reconciliationId}/regras-contabeis`;
    try {
      const response = await requestWithTimeout(url, {
        method: existing ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }, existing ? "A atualização da regra" : "O salvamento da regra");
      if (!response.ok) {
        return setMessage(await errorMessage(response, "Não foi possível salvar a regra."));
      }
      const result = await response.json();
      const topRuleId = !existing ? String(result.id || "") : "";
      if (topRuleId) markRecentRule(topRuleId);
      setMessage(
        existing
          ? "Regra atualizada e reaplicada."
          : result.reativada
            ? `Regra oculta restaurada e aplicada a ${result.movimentos_aplicados ?? 0} lançamento(s) neste período.`
            : `Regra salva e aplicada a ${result.movimentos_aplicados ?? 0} lançamento(s) neste período.`,
      );
      setCoverageModal(null);
      setDrafts((items) => ({ ...items, [item.id]: {} }));
      if (result.regras) applyRulesSnapshot(result.regras, topRuleId || undefined);
      else await load();
      if (!existing) setView("saved");
      onRulesChanged();
    } catch {
      setMessage("Não foi possível salvar a regra. Verifique a conexão e tente novamente.");
    } finally {
      setBusyRuleId(null);
    }
  }
  async function saveRule(item: PendingRule | SavedRule, existing = false) {
    if (busyRuleId) return;
    const body = buildRuleBody(item, existing);
    const validationMessage = ruleValidationMessage(body);
    if (validationMessage) {
      setMessage(validationMessage);
      return;
    }
    if (existing) return submitRule(item, body, true);
    setBusyRuleId(item.id);
    setMessage("Validando cobertura antes de salvar...");
    try {
      const storedPreview = previews[item.id];
      const preview = storedPreview?.gatilho === body.gatilho && storedPreview.gatilho_comprovante === body.gatilho_comprovante && storedPreview.texto_exclusao === body.texto_exclusao
        ? storedPreview
        : await loadRulePreview(item, body, false);
      if (!preview.quantidade) {
        setMessage(preview.motivo || "Essa regra não cobre lançamentos elegíveis.");
        return;
      }
      setCoverageModal({ item, body, preview, existing: false });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Não foi possível calcular a cobertura da regra.");
    } finally {
      setBusyRuleId(null);
    }
  }
  async function remove(scope: "periodo" | "global") {
    if (!deleteTarget) return;
    if (busyRuleId) return;
    setBusyRuleId(deleteTarget.id);
    try {
      const path = scope === "periodo"
        ? `${API}/api/conciliacoes/${reconciliationId}/regras-contabeis/${deleteTarget.id}/periodo`
        : `${API}/api/conciliacoes/${reconciliationId}/regras-contabeis/${deleteTarget.id}`;
      const response = await requestWithTimeout(path, {
        method: "DELETE",
      }, "A exclusão da regra");
      if (!response.ok) return setMessage(await errorMessage(response, "Não foi possível excluir a regra."));
      const result = await response.json();
      if (result.regras) applyRulesSnapshot(result.regras);
      else await load();
      setDeleteTarget(null);
      setMessage(result.message ?? "Regra excluída.");
      onRulesChanged();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Não foi possível concluir a exclusão. Verifique a conexão e tente novamente.");
    } finally {
      setBusyRuleId(null);
    }
  }
  async function restore(id: string) {
    if (busyRuleId) return;
    setBusyRuleId(id);
    try {
      const response = await requestWithTimeout(`${API}/api/conciliacoes/${reconciliationId}/regras-contabeis/${id}/periodo/excecao`, { method: "DELETE" }, "A restauração da regra");
      if (!response.ok) return setMessage(await errorMessage(response, "Não foi possível restaurar a regra."));
      const result = await response.json();
      if (result.regras) applyRulesSnapshot(result.regras);
      setView("saved");
      setMessage(result.message ?? "Regra restaurada neste período.");
      onRulesChanged();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Não foi possível restaurar a regra. Verifique a conexão e tente novamente.");
    } finally {
      setBusyRuleId(null);
    }
  }
  async function restoreCoveredHiddenRules() {
    if (busyRuleId) return;
    setBusyRuleId("restore-covered-hidden");
    try {
      const response = await requestWithTimeout(`${API}/api/conciliacoes/${reconciliationId}/regras-contabeis/ocultas/restaurar-com-cobertura`, { method: "POST" }, "A busca de regras existentes");
      if (!response.ok) return setMessage(await errorMessage(response, "Não foi possível buscar regras existentes."));
      const result = await response.json();
      if (result.regras) applyRulesSnapshot(result.regras);
      setView(result.quantidade ? "saved" : "hidden");
      setMessage(result.message ?? "Busca de regras existentes concluída.");
      if (result.quantidade) onRulesChanged();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Não foi possível buscar regras existentes. Verifique a conexão e tente novamente.");
    } finally {
      setBusyRuleId(null);
    }
  }
  async function clearAllRules() {
    if (busyRuleId) return;
    setBusyRuleId("all");
    try {
      const response = await requestWithTimeout(`${API}/api/conciliacoes/${reconciliationId}/regras-contabeis`, { method: "DELETE" }, "A limpeza das regras");
      if (!response.ok) return setMessage(await errorMessage(response, "Não foi possível limpar as regras."));
      const result = await response.json();
      setConfirmClearAll(false);
      setMessage(result.message ?? "Regras removidas somente deste período.");
      if (result.regras) applyRulesSnapshot(result.regras);
      else await load();
      onRulesChanged();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Não foi possível limpar as regras. Verifique a conexão e tente novamente.");
    } finally {
      setBusyRuleId(null);
    }
  }
  async function clearZeroCoveredRules(openHidden = false) {
    if (busyRuleId) return;
    setBusyRuleId("zero-covered");
    try {
      const response = await requestWithTimeout(`${API}/api/conciliacoes/${reconciliationId}/regras-contabeis/sem-cobertura`, { method: "DELETE" }, "A limpeza das regras sem cobertura");
      if (!response.ok) return setMessage(await errorMessage(response, "Não foi possível limpar as regras sem cobertura."));
      const result = await response.json();
      setMessage(result.message ?? "Regras sem cobertura ocultadas somente deste período.");
      if (result.regras) applyRulesSnapshot(result.regras);
      else await load();
      if (openHidden) setView("hidden");
      onRulesChanged();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Não foi possível limpar as regras sem cobertura. Verifique a conexão e tente novamente.");
    } finally {
      setBusyRuleId(null);
    }
  }
  function componentTriggerLabel(component = "") {
    return ({
      DESCONTO_ABATIMENTO: "Desconto",
      DESCONTO: "Desconto",
      ABATIMENTO: "Abatimento",
      JUROS: "Juros",
      MULTA: "Multa",
      JUROS_ANTECIPACAO_GETNET: "Getnet",
    } as Record<string, string>)[component.toUpperCase()] ?? "";
  }
  function keywordHasPart(keyword: string, part: string) {
    return keyword.toUpperCase().split(/\s+/).includes(part.toUpperCase());
  }
  function toggleKeywordPart(keyword: string, part: string) {
    return keywordHasPart(keyword, part)
      ? keyword.split(/\s+/).filter((item) => item.toUpperCase() !== part.toUpperCase()).join(" ")
      : [keyword, part].filter(Boolean).join(" ");
  }
  function legacyEditor(item: PendingRule | SavedRule, existing = false) {
    const fields = defaults(item);
    const pendingItem = "data" in item ? item : null;
    const isDebit = (item.natureza_contabil || item.natureza) === "Débito";
    const words = pendingItem?.historico.match(/[\p{L}\p{N}]+/gu) ?? [];
    const keyword = value(item.id, "gatilho", fields.gatilho);
    const componentTrigger = componentTriggerLabel(item.tipo_componente);
    const coveredCount =
      "cobertos" in item && keyword === fields.gatilho
        ? item.cobertos
        : keyword
          ? pending.filter(
              (candidate) =>
                candidate.historico
                  .toUpperCase()
                  .includes(keyword.toUpperCase()) &&
                (candidate.natureza_contabil || candidate.natureza) === (item.natureza_contabil || item.natureza),
            ).length
          : 0;
    return (
      <tr className="border-t align-top" key={item.id}>
        <td className="px-2 py-2">
          {"data" in item ? (
            <>
              <span>{item.data}</span>
              <span className="mt-1 block">
                <MovementUsageToggle
                  used={item.usado_no_periodo !== false}
                  busy={busyRuleId === `movimento-${movementIdFor(item)}`}
                  onToggle={() => setMovementUsage(item, item.usado_no_periodo === false)}
                />
              </span>
            </>
          ) : `${item.cobertos} cobertos`}
        </td>
        <td className="max-w-64 px-2 py-2">
          <p>{"gatilho" in item ? item.gatilho : item.historico}</p>
          {pendingItem?.comprovante_tipo === "emprestimo" && (
            <div className="mt-1">
              <LoanReceiptNotice compact />
            </div>
          )}
          {pendingItem?.comprovante_confere && (
            <div className="mt-1 flex items-center gap-1 text-[10px] text-emerald-700">
              <button
                onClick={() =>
                  onView({
                    arquivoId: String(pendingItem.comprovante_arquivo_id),
                    pagina: Number(pendingItem.comprovante_pagina || 1),
                    titulo: "Comprovante bancário",
                  })
                }
                className="rounded border border-emerald-200 px-1.5 py-0.5"
              >
                📎 Comprovante
              </button>
              <span>✓ Confere com o extrato</span>
            </div>
          )}
        </td>
        <td className="px-2 py-2">{item.natureza}</td>
        <td className="px-2 py-1">
          <div className="space-y-1">
            <input
              className="w-32 rounded border px-1.5 py-1"
              value={value(item.id, "gatilho", fields.gatilho)}
              onChange={(e) => change(item.id, "gatilho", e.target.value)}
            />
            {pendingItem && (
              <>
                <button
                  onClick={() =>
                    change(item.id, "gatilho", pendingItem.historico)
                  }
                  className="text-[10px] text-teal-700 underline"
                >
                  Usar histórico completo
                </button>
                <div className="flex max-w-40 flex-wrap gap-1">
                  {componentTrigger && (
                    <button
                      type="button"
                      onClick={() => change(item.id, "gatilho", toggleKeywordPart(keyword, componentTrigger))}
                      className={`rounded px-1 py-0.5 text-[9px] ${keywordHasPart(keyword, componentTrigger) ? "bg-teal-700 text-white" : "bg-amber-100 text-amber-800"}`}
                    >
                      {componentTrigger}
                    </button>
                  )}
                  {words.map((word, index) => (
                    <button
                      onClick={() =>
                        change(
                          item.id,
                          "gatilho",
                          [value(item.id, "gatilho", ""), word]
                            .filter(Boolean)
                            .join(" "),
                        )
                      }
                      className="rounded bg-slate-100 px-1 py-0.5 text-[9px] text-slate-600"
                      key={`${word}-${index}`}
                    >
                      {word}
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>
        </td>
        <td className="px-2 py-1">
          <input
            className="w-32 rounded border px-1.5 py-1"
            value={value(item.id, "debito", fields.debito)}
            onChange={(e) => change(item.id, "debito", e.target.value)}
          />
        </td>
        <td className="px-2 py-1">
          <input
            className="w-32 rounded border px-1.5 py-1"
            value={value(item.id, "credito", fields.credito)}
            onChange={(e) => change(item.id, "credito", e.target.value)}
          />
        </td>
        <td className="px-2 py-1">
          <input
            className="w-40 rounded border px-1.5 py-1"
            value={value(item.id, "historico", fields.historico)}
            onChange={(e) => change(item.id, "historico", e.target.value)}
          />
        </td>
        <td className="px-2 py-1">
          <input
            className="w-40 rounded border px-1.5 py-1"
            value={value(item.id, "complemento", fields.complemento)}
            onChange={(e) => change(item.id, "complemento", e.target.value)}
          />
        </td>
        <td className="whitespace-nowrap px-2 py-1">
          <button
            onClick={() => saveRule(item, existing)}
            className="rounded bg-teal-700 px-2 py-1 text-white"
          >
            {existing ? "Atualizar" : "Salvar"}
          </button>
          {existing && (
            <button
              onClick={() => setDeleteTarget(item as SavedRule)}
              className="ml-1 rounded border border-red-200 px-2 py-1 text-red-700"
            >
              Excluir
            </button>
          )}
        </td>
      </tr>
    );
  }
  const componentLabel = (component = "") =>
    ({
      VALOR_COBRADO: "Principal",
      PRINCIPAL: "Principal",
      DESCONTO_ABATIMENTO: "Desconto",
      DESCONTO: "Desconto",
      ABATIMENTO: "Abatimento",
      JUROS: "Juros",
      MULTA: "Multa",
      ENCARGOS: "Encargos",
      SIMPLES_NACIONAL: "Simples Nacional",
      JUROS_ANTECIPACAO_GETNET: "Juros antecipação Getnet",
    })[component] ?? component;
  function editor(
    item: PendingRule | SavedRule,
    existing = false,
    compact = false,
    simple = false,
    showAction = true,
    composite = false,
  ) {
    const fields = defaults(item);
    const pendingItem = "data" in item ? item : null;
    const isDebit = (item.natureza_contabil || item.natureza) === "Débito";
    const words = pendingItem?.historico.match(/[\p{L}\p{N}]+/gu) ?? [];
    const keyword = value(item.id, "gatilho", fields.gatilho);
    const receiptKeyword = value(item.id, "gatilhoComprovante", fields.gatilhoComprovante);
    const exclusionKeyword = value(item.id, "textoExclusao", fields.textoExclusao);
    const componentTrigger = componentTriggerLabel(item.tipo_componente);
    const debitValue = value(item.id, "debito", fields.debito);
    const creditValue = value(item.id, "credito", fields.credito);
    const historyValue = value(item.id, "historico", fields.historico);
    const complementValue = value(item.id, "complemento", fields.complemento);
    const storedPreview = previews[item.id];
    const preview = storedPreview && storedPreview.gatilho === keyword && storedPreview.gatilho_comprovante === receiptKeyword && storedPreview.texto_exclusao === exclusionKeyword ? storedPreview : undefined;
    const coveredCount =
      "cobertos" in item && keyword === fields.gatilho && receiptKeyword === fields.gatilhoComprovante && exclusionKeyword === fields.textoExclusao
        ? item.cobertos
        : preview?.quantidade ?? 0;
    const saveIssue = ruleValidationMessage(buildRuleBody(item, existing));
    const isRecent = "gatilho" in item && recentRuleId === item.id;
    const coverageMessage = existing
      ? coveredCount
        ? `Cobrindo ${coveredCount} lançamento(s)`
        : "Sem lançamentos cobertos neste período"
      : preview
        ? coveredCount
          ? `Vai cobrir ${coveredCount} lançamento(s)`
          : "Não cobre lançamentos elegíveis"
        : "Clique em Ver cobertura para calcular";
    const coverageClass = coveredCount ? "" : preview || existing ? "text-red-700" : "text-slate-500";
    const isGetnetAdjustment = Boolean(pendingItem?.ajuste_getnet || item.tipo_componente === "JUROS_ANTECIPACAO_GETNET");
    return (
      <tr
        className={`border-t align-top ${isGetnetAdjustment && !compact ? "border-l-4 border-l-rose-500 bg-rose-50/70" : ""} ${composite ? "border-x-2 border-x-sky-200 bg-sky-50/50" : ""} ${isRecent ? "bg-teal-50" : compact ? "bg-inherit" : simple ? "border-y border-l-4 border-emerald-200 border-l-emerald-300 bg-emerald-50/70" : ""}`}
        key={item.id}
      >
        {compact && pendingItem ? (
          <td colSpan={4} className="border-l-2 border-sky-200 whitespace-nowrap px-3 py-2">
            <strong className="text-slate-800">
              {componentLabel(pendingItem.tipo_componente)}
            </strong>
            <span className="mx-2 text-slate-300">|</span>
            <span
              className={`font-semibold ${isDebit ? "text-blue-700" : "text-red-700"}`}
            >
              R$ {pendingItem.valor}
            </span>
          </td>
        ) : (
          <>
            <td className={`${existing ? "w-[8%]" : ""} px-2 py-2`}>
              {"data" in item ? (
                <>
                  <span>{item.data}</span>
                  <span className="mt-1 block">
                    <MovementUsageToggle
                      used={item.usado_no_periodo !== false}
                      busy={busyRuleId === `movimento-${movementIdFor(item)}`}
                      onToggle={() => setMovementUsage(item, item.usado_no_periodo === false)}
                    />
                  </span>
                </>
              ) : <><span>{item.cobertos} cobertos</span>{isRecent && <span className="mt-1 block rounded bg-teal-700 px-1.5 py-0.5 text-[10px] font-semibold text-white">Criada agora há pouco</span>}</>}
            </td>
            <td className={`${existing ? "w-[14%]" : "w-64 max-w-64"} px-2 py-2`}>
              <p className="line-clamp-2 break-words leading-4" title={"gatilho" in item ? item.gatilho : item.historico}>{"gatilho" in item ? item.gatilho : item.historico}</p>
              {"gatilho" in item && item.gatilho_comprovante && <p className={`mt-1 text-[10px] text-violet-700 ${existing ? "break-words" : "max-w-64 truncate"}`} title={item.gatilho_comprovante}>Comprovante: {item.gatilho_comprovante}</p>}
              {"gatilho" in item && item.texto_exclusao && <p className={`mt-1 text-[10px] text-rose-700 ${existing ? "break-words" : "max-w-64 truncate"}`} title={item.texto_exclusao}>Não contém: {item.texto_exclusao}</p>}
              {pendingItem?.tarifa_no_extrato && <p className="mt-1 text-[10px] text-sky-700">Tarifa do comprovante está presente no extrato.</p>}
              {pendingItem?.tarifa_referente_ao_comprovante && <p className="mt-1 text-[10px] text-slate-500">Esta tarifa é referente ao comprovante de {pendingItem.tarifa_referencia_nome}, R$ {Number(pendingItem.tarifa_referencia_valor || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 })} em {pendingItem.tarifa_referencia_data}.</p>}
              {pendingItem?.composicao_simples && <p className="mt-1 whitespace-pre-line text-[10px] text-slate-500">{pendingItem.composicao_simples}</p>}
              {pendingItem?.comprovante_tipo === "emprestimo" && (
                <div className="mt-1">
                  <LoanReceiptNotice compact />
                </div>
              )}
              {(pendingItem?.comprovante_arquivo_id || pendingItem?.comprovante_rfb_arquivo_id) && (
                <div className="mt-1 flex items-center gap-1 text-[10px] text-emerald-700">
                  {pendingItem.comprovante_arquivo_id && <button
                    onClick={() =>
                      onView({
                        arquivoId: String(pendingItem.comprovante_arquivo_id),
                        pagina: Number(pendingItem.comprovante_pagina || 1),
                        titulo: "Comprovante bancário",
                      })
                    }
                    className="rounded border border-emerald-200 px-1.5 py-0.5"
                  >
                    Comprovante bancário
                  </button>}
                  {pendingItem.comprovante_rfb_arquivo_id && <button onClick={() => onView({ arquivoId: String(pendingItem.comprovante_rfb_arquivo_id), pagina: Number(pendingItem.comprovante_rfb_pagina || 1), titulo: "Comprovante RFB" })} className="rounded border border-violet-200 px-1.5 py-0.5 text-violet-800">Comprovante RFB</button>}
                  {pendingItem.comprovante_confere && <span>✓ Confere com o extrato</span>}
                </div>
              )}
            </td>
            <td className={`${existing ? "w-[8%]" : ""} px-2 py-2`}>
              <div className="flex flex-col items-start gap-1">
                <span
                  className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${isDebit ? "bg-blue-100 text-blue-800" : "bg-red-100 text-red-800"}`}
                >
                  {isDebit ? "Débito" : "Crédito"}
                </span>
                {item.tipo_componente && !simple && (
                  <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${isGetnetAdjustment ? "bg-rose-100 text-rose-800" : "bg-slate-100 text-slate-700"}`}>
                    {componentLabel(item.tipo_componente)}
                  </span>
                )}
                {isGetnetAdjustment && !existing && (
                  <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold text-amber-800">
                    Ajuste Getnet
                  </span>
                )}
                {existing && "gatilho" in item && <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${item.escopo === "periodo" ? "bg-violet-100 text-violet-800" : "bg-amber-100 text-amber-800"}`}>{item.escopo === "periodo" ? "Este período" : "Global"}</span>}
              </div>
            </td>
            <td
              className={`${existing ? "w-[8%]" : ""} px-2 py-2 font-semibold whitespace-nowrap ${isDebit ? "text-blue-700" : "text-red-700"}`}
            >
              {pendingItem ? `R$ ${pendingItem.valor}` : "—"}
            </td>
          </>
        )}
        <td className={`${existing ? "w-[11%]" : ""} px-2 py-1`}>
          <div className="relative">
            <div className="flex items-center gap-1">
              <input
                className={`${existing ? "w-full min-w-0" : "w-20"} rounded border px-1.5 py-1`}
                placeholder="gatilho..."
                value={keyword}
                onChange={(event) =>
                  change(item.id, "gatilho", event.target.value)
                }
              />
              {pendingItem && (
                <>
                  <button
                    title="Usar histórico completo"
                    onClick={() => {
                      change(item.id, "gatilho", pendingItem.historico);
                      setKeywordMode((items) => ({
                        ...items,
                        [item.id]: "full",
                      }));
                    }}
                    className="rounded border border-slate-300 bg-white p-1 text-slate-700 hover:border-teal-600 hover:text-teal-700"
                  >
                    <Copy size={13} />
                  </button>
                  <button
                    title="Selecionar palavras"
                    onClick={() =>
                      setWordPicker(wordPicker === item.id ? null : item.id)
                    }
                    className="rounded border border-slate-300 bg-white p-1 text-slate-700 hover:border-teal-600 hover:text-teal-700"
                  >
                    <Tags size={13} />
                  </button>
                  {wordPicker === item.id && (
                    <div className="absolute left-0 top-8 z-30 w-56 rounded-lg border border-slate-300 bg-white p-2 shadow-xl">
                      <div className="mb-2 flex items-center justify-between border-b pb-1 text-[10px] font-semibold text-slate-700">
                        Clique nas palavras que quer usar
                        <button
                          onClick={() => setWordPicker(null)}
                          className="text-sm leading-none text-slate-500 hover:text-slate-900"
                        >
                          ✕
                        </button>
                      </div>
                      {componentTrigger && (
                        <div className="mb-2 border-b border-slate-100 pb-2">
                          <p className="mb-1 text-[9px] font-semibold uppercase text-amber-600">Componente</p>
                          <button
                            type="button"
                            onClick={() => {
                              change(item.id, "gatilho", toggleKeywordPart(keyword, componentTrigger));
                              setKeywordMode((items) => ({
                                ...items,
                                [item.id]: "words",
                              }));
                            }}
                            className={`rounded px-1.5 py-0.5 text-[10px] ${keywordHasPart(keyword, componentTrigger) ? "bg-teal-700 text-white" : "bg-amber-100 text-amber-800 hover:bg-amber-200"}`}
                          >
                            {componentTrigger}
                          </button>
                        </div>
                      )}
                      <div className="flex flex-wrap gap-1">
                        {words.map((word, index) => {
                          const selected = keyword
                            .toUpperCase()
                            .split(/\s+/)
                            .includes(word.toUpperCase());
                          return (
                            <button
                              onClick={() => {
                                change(
                                  item.id,
                                  "gatilho",
                                  selected
                                    ? keyword
                                        .split(/\s+/)
                                        .filter(
                                          (part) =>
                                            part.toUpperCase() !==
                                            word.toUpperCase(),
                                        )
                                        .join(" ")
                                    : [keyword, word].filter(Boolean).join(" "),
                                );
                                setKeywordMode((items) => ({
                                  ...items,
                                  [item.id]: "words",
                                }));
                              }}
                              className={`rounded px-1.5 py-0.5 text-[10px] ${selected ? "bg-teal-700 text-white" : "bg-slate-100 text-slate-700 hover:bg-teal-100"}`}
                              key={`${word}-${index}`}
                            >
                              {word}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
            {componentTrigger && (
              <button
                type="button"
                onClick={() => {
                  change(item.id, "gatilho", toggleKeywordPart(keyword, componentTrigger));
                  setKeywordMode((items) => ({ ...items, [item.id]: "words" }));
                }}
                className={`mt-1 rounded px-1.5 py-0.5 text-[10px] font-semibold ${keywordHasPart(keyword, componentTrigger) ? "bg-teal-700 text-white" : "bg-amber-100 text-amber-800 hover:bg-amber-200"}`}
              >
                {componentTrigger}
              </button>
            )}
            <input
              className={`${existing ? "mt-1 w-full min-w-0" : "mt-1 w-20"} rounded border border-rose-200 px-1.5 py-1 text-[10px]`}
              placeholder="não contém..."
              title="Texto de exclusão"
              value={exclusionKeyword}
              onChange={(event) => change(item.id, "textoExclusao", event.target.value)}
            />
            {(pendingItem?.comprovante_arquivo_id || pendingItem?.comprovante_rfb_arquivo_id) && (
              <div className="mt-1 flex items-center gap-1">
                <input className="w-20 rounded border border-violet-200 px-1.5 py-1" placeholder="comprovante..." value={receiptKeyword} onChange={(event) => change(item.id, "gatilhoComprovante", event.target.value)} />
                <button title="Usar comprovante completo" onClick={() => change(item.id, "gatilhoComprovante", (pendingItem.palavras_comprovante ?? []).join(" "))} className="rounded border border-violet-200 bg-violet-50 p-1 text-violet-700 hover:border-violet-500">
                  <Copy size={13} />
                </button>
                <button title="Selecionar palavras do comprovante" onClick={() => setReceiptWordPicker(receiptWordPicker === item.id ? null : item.id)} className="rounded border border-violet-200 bg-violet-50 p-1 text-violet-700 hover:border-violet-500">
                  <Tags size={13} />
                </button>
                {receiptWordPicker === item.id && (
                  <div className="absolute left-24 top-8 z-30 w-56 rounded-lg border border-violet-200 bg-white p-2 shadow-xl">
                    <div className="mb-2 flex items-center justify-between border-b pb-1 text-[10px] font-semibold text-violet-800">Palavras dos comprovantes<button onClick={() => setReceiptWordPicker(null)} className="text-sm leading-none text-slate-500">✕</button></div>
                    {[["Banco", pendingItem.palavras_comprovante_banco ?? []], ["RFB", pendingItem.palavras_comprovante_rfb ?? []]].map(([source, words]) => Array.isArray(words) && words.length > 0 && <div className="mb-2" key={source as string}><p className="mb-1 text-[9px] font-semibold uppercase text-violet-500">{source as string}</p><div className="flex flex-wrap gap-1">{words.map((word, index) => { const selected = receiptKeyword.toUpperCase().split(/\s+/).includes(word); return <button onClick={() => change(item.id, "gatilhoComprovante", selected ? receiptKeyword.split(/\s+/).filter(part => part !== word).join(" ") : [receiptKeyword, word].filter(Boolean).join(" "))} className={`rounded px-1.5 py-0.5 text-[10px] ${selected ? "bg-violet-700 text-white" : "bg-violet-50 text-violet-800"}`} key={`${source}-${word}-${index}`}>{word}</button>; })}</div></div>)}
                  </div>
                )}
              </div>
            )}
            {(keyword || receiptKeyword || preview) && (
              <div className="mt-1 w-48 text-[10px] leading-4 text-emerald-700">
                <span className="font-semibold">Texto usado pela regra</span>
                <br /><span className={coverageClass}>{coveredCount ? "✓" : preview || existing ? "!" : "•"} {coverageMessage}</span>
                {(keyword || receiptKeyword) && <><br /><span className="text-slate-500">«{[keyword, receiptKeyword].filter(Boolean).join(" | ")}»</span></>}
                {exclusionKeyword && <><br /><span className="text-rose-700">Não contém: «{exclusionKeyword}»</span></>}
                {preview?.lancamentos[0]?.fonte && <><br /><span className="text-slate-500">Fonte: {preview.lancamentos.map((match) => match.fonte).filter((value, index, values) => values.indexOf(value) === index).join(", ")}</span></>}
                {preview?.motivo && <><br /><span className="text-red-700">{preview.motivo}</span></>}
              </div>
            )}
          </div>
        </td>
        <td className={`${existing ? "w-[10%]" : ""} px-2 py-1`}>
          <input
            list="catalogo-contas"
            title={value(item.id, "debito", fields.debito)}
            className={`${existing ? "w-full min-w-0" : "w-20"} rounded border px-1.5 py-1 pr-5 text-left text-[10px]`}
            placeholder="Selecionar"
            value={debitValue}
            onChange={(event) => {
              change(item.id, "debito", event.target.value);
              showInputStart(event.currentTarget);
            }}
            onBlur={(event) => showInputStart(event.currentTarget)}
          />
        </td>
        <td className={`${existing ? "w-[10%]" : ""} px-2 py-1`}>
          <input
            list="catalogo-contas"
            title={value(item.id, "credito", fields.credito)}
            className={`${existing ? "w-full min-w-0" : "w-20"} rounded border px-1.5 py-1 pr-5 text-left text-[10px]`}
            placeholder="Selecionar"
            value={creditValue}
            onChange={(event) => {
              change(item.id, "credito", event.target.value);
              showInputStart(event.currentTarget);
            }}
            onBlur={(event) => showInputStart(event.currentTarget)}
          />
        </td>
        <td className={`${existing ? "w-[14%]" : ""} px-2 py-1`}>
          <input
            list="catalogo-historicos"
            title={value(item.id, "historico", fields.historico)}
            className={`${existing ? "w-full min-w-0" : "w-28"} rounded border px-1.5 py-1 pr-5 text-left text-[10px]`}
            placeholder="Selecionar"
            value={historyValue}
            onChange={(event) => {
              change(item.id, "historico", event.target.value);
              showInputStart(event.currentTarget);
            }}
            onBlur={(event) => showInputStart(event.currentTarget)}
          />
        </td>
        <td className={`${existing ? "w-[13%]" : ""} px-2 py-1`}>
          <input
            className={`${existing ? "w-full min-w-0" : "w-28"} rounded border px-1.5 py-1`}
            value={complementValue}
            onChange={(event) =>
              change(item.id, "complemento", event.target.value)
            }
          />
        </td>
        {showAction && <td className={`${existing ? "w-[6%]" : "w-px"} whitespace-nowrap px-2 py-1`}>
          {!existing && <button title="Ver cobertura" aria-label="Ver cobertura" disabled={busyRuleId === item.id} onClick={() => previewRule(item)} className="inline-flex h-7 w-7 items-center justify-center rounded border border-teal-700 text-teal-800 hover:bg-teal-50 disabled:cursor-wait disabled:opacity-60">{busyRuleId === item.id ? <RefreshCw className="animate-spin" size={14} /> : <Gauge size={14} />}</button>}
          <button title={saveIssue || (existing ? "Atualizar regra" : "Salvar regra")} aria-label={existing ? "Atualizar regra" : "Salvar regra"} disabled={busyRuleId === item.id} onClick={() => saveRule(item, existing)} className={`ml-1 inline-flex h-7 w-7 items-center justify-center rounded text-white disabled:cursor-wait disabled:opacity-60 ${saveIssue ? "bg-slate-400 hover:bg-slate-500" : "bg-teal-700 hover:bg-teal-800"}`}>
            {busyRuleId === item.id ? <RefreshCw className="animate-spin" size={14} /> : existing ? <RefreshCw size={14} /> : <CheckCircle2 size={14} />}
          </button>
          {existing && <button title="Excluir regra" aria-label="Excluir regra" disabled={busyRuleId === item.id} onClick={() => setDeleteTarget(item as SavedRule)} className="ml-1 rounded border border-red-200 px-2 py-1 text-red-700 disabled:cursor-wait disabled:opacity-60">{busyRuleId === item.id ? <RefreshCw className="animate-spin" size={14} /> : <Trash2 size={14} />}</button>}
        </td>}
      </tr>
    );
  }
  const visible = pending.filter((item) =>
    item.historico.toLowerCase().includes(filter.toLowerCase()),
  );
  const visibleSaved = saved.filter((item) =>
    [item.gatilho, item.historico, item.complemento]
      .join(" ")
      .toLowerCase()
      .includes(filter.toLowerCase()),
  );
  const pendingGroups = Object.values(
    visible.reduce<Record<string, PendingRule[]>>((groups, item) => {
      const movementId = item.id.split(":")[0];
      (groups[movementId] ??= []).push(item);
      return groups;
    }, {}),
  );
  const savedGroups = (() => {
    const groups: SavedRule[][] = [];
    visibleSaved.forEach((rule) => {
      const matchingIndexes = groups
        .map((group, index) => (group.some((item) => savedRulesOverlap(item, rule)) ? index : -1))
        .filter((index) => index >= 0);
      if (!matchingIndexes.length) {
        groups.push([rule]);
        return;
      }
      const [firstIndex, ...mergeIndexes] = matchingIndexes;
      groups[firstIndex].push(rule);
      mergeIndexes.reverse().forEach((index) => {
        groups[firstIndex].push(...groups[index]);
        groups.splice(index, 1);
      });
    });
    return groups;
  })().map((group) =>
    group.sort(
      (left, right) =>
        componentOrder(left.tipo_componente) -
          componentOrder(right.tipo_componente) ||
        left.historico.localeCompare(right.historico),
    ),
  ).sort((left, right) => {
    const leftAnchor = left.find((item) => componentOrder(item.tipo_componente) === 1) ?? left[0];
    const rightAnchor = right.find((item) => componentOrder(item.tipo_componente) === 1) ?? right[0];
    return String(rightAnchor.criada_em || "").localeCompare(String(leftAnchor.criada_em || ""));
  });
  const isSavedComposite = (group: SavedRule[]) =>
    group.length > 1 &&
    new Set(group.map((rule) => componentOrder(rule.tipo_componente))).size > 1;
  const zeroCoveredRulesCount = saved.filter((rule) => rule.cobertos === 0).length;
  const showActions = true;
  return (
    <section className="space-y-2 rounded-xl border border-slate-200 bg-white p-2.5">
      <datalist id="catalogo-contas">
        {catalog.contas.map((option) => (
          <option value={option} key={option} />
        ))}
      </datalist>
      <datalist id="catalogo-historicos">
        {catalog.historicos.map((option) => (
          <option value={option} key={option} />
        ))}
      </datalist>
      <div className="hidden flex-wrap items-center gap-1.5 rounded-md bg-slate-50 p-2">
        <label className="flex items-center gap-1.5 text-[11px] font-medium text-slate-600">
          <span className="whitespace-nowrap">Conta deste banco</span>
          <input
            list="catalogo-contas"
            value={account}
            onChange={(e) => setAccount(e.target.value)}
            className="w-64 rounded border bg-white px-2 py-1 text-xs"
            placeholder="Ex.: 33 - Banco Santander S/A"
          />
        </label>
        <button
          onClick={saveAccount}
          className="rounded border border-teal-700 px-2 py-1 text-[11px] font-semibold text-teal-800"
        >
          Salvar conta
        </button>
        {csvPermitted ? <><a href={`${API}/api/conciliacoes/${reconciliationId}/lancamentos-contabeis.csv`} className="rounded bg-teal-700 px-2 py-1 text-[11px] font-semibold text-white">Gerar CSV</a><a href={`${API}/api/conciliacoes/${reconciliationId}/lancamentos-contabeis.pdf`} className="rounded border border-slate-300 bg-white px-2 py-1 text-[11px] font-semibold text-slate-700">Gerar PDF</a></> : <span className="cursor-not-allowed rounded bg-slate-200 px-2 py-1 text-[11px] font-semibold text-slate-500">CSV bloqueado</span>}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={() => setView("pending")}
          className={`rounded-md px-3 py-1.5 text-xs font-semibold ${view === "pending" ? "bg-teal-700 text-white" : "border"}`}
        >
          Regras a criar ({pending.length})
        </button>
        <button
          onClick={() => setView("saved")}
          className={`rounded-md px-3 py-1.5 text-xs font-semibold ${view === "saved" ? "bg-teal-700 text-white" : "border"}`}
        >
          Regras salvas ({saved.length})
        </button>
        <input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="w-32 rounded border px-2 py-1.5 text-xs"
          placeholder="Filtrar histórico"
        />
        <button
          disabled={busyRuleId === "zero-covered"}
          onClick={() => zeroCoveredRulesCount ? clearZeroCoveredRules(true) : setView("hidden")}
          className={`rounded-md px-3 py-1.5 text-xs font-semibold disabled:cursor-wait disabled:opacity-60 ${view === "hidden" ? "bg-violet-700 text-white" : "border border-violet-200 bg-violet-50 text-violet-800"}`}
        >
          {busyRuleId === "zero-covered" ? "Limpando..." : `Regras ocultas (${ignored.length}) · 0 cobertos (${zeroCoveredRulesCount})`}
        </button>
        {ignored.length > 0 && (
          <button
            disabled={busyRuleId === "restore-covered-hidden"}
            onClick={restoreCoveredHiddenRules}
            className="rounded-md border border-amber-200 bg-amber-50 px-3 py-1.5 text-xs font-semibold text-amber-800 disabled:cursor-wait disabled:opacity-60"
          >
            {busyRuleId === "restore-covered-hidden" ? "Buscando..." : `Buscar regras existentes (${ignored.length})`}
          </button>
        )}
        {saved.length > 0 && <button onClick={() => setConfirmClearAll(true)} className="rounded-md border border-red-200 px-3 py-1.5 text-xs font-semibold text-red-700">Limpar todas</button>}
        <div className="ml-auto flex flex-wrap items-center gap-1.5 rounded-md bg-slate-50 p-1.5">
          <label className="flex items-center gap-1 text-[11px] font-medium text-slate-600">
            <span className="whitespace-nowrap">Conta deste banco</span>
            <input list="catalogo-contas" value={account} onChange={(e) => setAccount(e.target.value)} className="w-52 rounded border bg-white px-2 py-1 text-xs" placeholder="Ex.: 33 - Banco Santander S/A" />
          </label>
          <button title="Salvar conta" aria-label="Salvar conta" onClick={saveAccount} className="rounded border border-teal-700 p-1.5 text-teal-800"><CheckCircle2 size={14}/></button>
          {csvPermitted ? <><a title="Gerar CSV" aria-label="Gerar CSV" href={`${API}/api/conciliacoes/${reconciliationId}/lancamentos-contabeis.csv`} className="rounded bg-teal-700 p-1.5 text-white"><Download size={14}/></a><a title="Gerar PDF" aria-label="Gerar PDF" href={`${API}/api/conciliacoes/${reconciliationId}/lancamentos-contabeis.pdf`} className="rounded border border-slate-300 bg-white p-1.5 text-slate-700"><FileText size={14}/></a></> : <span title="CSV bloqueado por integridade" className="cursor-not-allowed rounded bg-slate-200 p-1.5 text-slate-500"><Download size={14}/></span>}
        </div>
      </div>
      {message && <p className="text-xs text-teal-800">{message}</p>}
      {view === "hidden" ? (
        <div className="max-h-[calc(100dvh-330px)] overflow-auto rounded border border-violet-200 bg-violet-50 p-3 text-xs text-violet-950 overscroll-contain">
          {ignored.length ? (
            <div className="divide-y divide-violet-200">
              {ignored.map((rule) => <div className="flex items-center justify-between gap-3 py-2" key={rule.id}><span className="min-w-0 truncate"><strong>{rule.gatilho || rule.historico}</strong>{rule.tipo_componente ? ` · ${rule.tipo_componente}` : ""}</span><button disabled={busyRuleId === rule.id} onClick={() => restore(rule.id)} className="shrink-0 rounded border border-violet-300 bg-white px-2 py-1 font-semibold text-violet-800 disabled:opacity-60">{busyRuleId === rule.id ? "Restaurando..." : "Restaurar regra"}</button></div>)}
            </div>
          ) : (
            <p className="py-6 text-center text-violet-800">Nenhuma regra oculta neste período.</p>
          )}
        </div>
      ) : (
      <div className="h-[calc(100dvh-330px)] min-h-96 overflow-auto rounded border overscroll-contain">
        <table className={`w-full text-left text-xs ${view === "saved" ? "table-fixed" : ""}`}>
          <thead className="sticky top-0 z-10 bg-slate-50 text-[10px] uppercase text-slate-500 shadow-sm">
            <tr>
              {[
                "Data",
                "Histórico",
                "Tipo",
                "Valor",
                "Gatilho",
                "Débito",
                "Crédito",
                "Histórico contábil",
                "Complemento",
                ...(showActions ? ["Ação"] : []),
              ].map((label) => (
                <th className={label ? "px-2 py-2" : "w-px px-1 py-2"} key={label}>
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {view === "pending"
              ? pendingGroups.map((items) => {
                  const movement = items[0];
                  const compound = items.length > 1 || items.some((item) => item.movimento_composto);
                  if (!compound)
                    return (
                      <Fragment key={movement.id}>
                        {editor(movement, false, false, true, showActions)}
                      </Fragment>
                    );
                  return (
                    <Fragment key={movement.id.split(":")[0]}>
                      <tr
                        className={`border-t ${compound ? "bg-sky-50" : "bg-emerald-50/70"}`}
                      >
                        <td
                          colSpan={showActions ? 10 : 9}
                          className="border-x-2 border-t-2 border-l-4 border-sky-200 border-l-sky-400 px-3 py-3"
                        >
                          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                            <strong>{movement.data}</strong>
                            <MovementUsageToggle
                              used={movement.usado_no_periodo !== false}
                              busy={busyRuleId === `movimento-${movementIdFor(movement)}`}
                              onToggle={() => setMovementUsage(movement, movement.usado_no_periodo === false)}
                            />
                            <span className="max-w-96 truncate font-medium text-slate-800" title={movement.historico}>
                              {movement.historico}
                            </span>
                             <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-semibold text-blue-800">
                               Extrato: {movement.natureza} | Contábil: {movement.natureza_contabil}
                             </span>
                              <span className="text-[10px] font-semibold text-sky-800">
                               Composição do comprovante: {items.map((item) => componentLabel(item.tipo_componente)).join(", ")} pendente{items.length > 1 ? "s" : ""}.
                             </span>
                            {movement.comprovante_confere && (
                              <span className="text-[10px] text-emerald-700">
                                ✓ Confere com o extrato
                              </span>
                            )}
                            {movement.comprovante_tipo === "emprestimo" && (
                              <LoanReceiptNotice compact />
                            )}
                            {movement.comprovante_arquivo_id && (
                              <button
                                onClick={() =>
                                  onView({
                                    arquivoId: String(
                                      movement.comprovante_arquivo_id,
                                    ),
                                    pagina: Number(
                                      movement.comprovante_pagina || 1,
                                    ),
                                    titulo: "Comprovante bancário",
                                  })
                                }
                                className="rounded border border-emerald-200 bg-white/80 px-1.5 py-0.5 text-[10px] text-emerald-700"
                              >
                                Comprovante bancário
                              </button>
                            )}
                            {movement.comprovante_rfb_arquivo_id && <button onClick={() => onView({ arquivoId: String(movement.comprovante_rfb_arquivo_id), pagina: Number(movement.comprovante_rfb_pagina || 1), titulo: "Comprovante RFB" })} className="rounded border border-violet-200 bg-white/80 px-1.5 py-0.5 text-[10px] text-violet-800">Comprovante RFB</button>}
                          </div>
                        </td>
                      </tr>
                      {items.map((item) => editor(item, false, true, false, showActions))}
                       {(movement.valor_documento || movement.componentes_cobertos?.length) && (
                         <tr
                          className={
                            compound ? "bg-sky-50" : "bg-emerald-50/70"
                          }
                        >
                          <td
                            colSpan={showActions ? 10 : 9}
                            className="border-x-2 border-b-2 border-sky-200 px-3 pb-3 text-[10px] text-slate-500"
                          >
                            {(() => {
                              const principalComponents = ["PRINCIPAL", "VALOR_COBRADO"];
                              const isPrincipal = (component = "") => principalComponents.includes(component);
                              const principal = movement.componentes_cobertos?.find((item) => isPrincipal(item.componente));
                              const missingPrincipal = items
                                .filter((item) => isPrincipal(item.tipo_componente))
                                .reduce((total, item) => total + Number(item.valor || 0), 0);
                              const pendingAdjustments = items
                                .filter((item) => !isPrincipal(item.tipo_componente))
                                .reduce((total, item) => total + Number(item.valor || 0), 0);
                              const money = (value: string | number) => Number(value || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 });
                              return <span>Principal já lançado: R$ {money(principal?.valor || 0)} | Principal faltando: R$ {money(missingPrincipal)}{pendingAdjustments ? ` | Ajustes pendentes: R$ ${money(pendingAdjustments)}` : ""} | Valor total do documento: R$ {money(movement.valor_documento || 0)}</span>;
                            })()}
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })
               : savedGroups.map((group) => {
                  const composite = isSavedComposite(group);
                  const components = group.map((item) => componentLabel(item.tipo_componente)).filter(Boolean);
                  return (
                    <Fragment key={group.map((item) => item.id).join(":")}>
                      {composite && (
                        <tr className="border-t-2 border-sky-300 bg-sky-50">
                          <td colSpan={showActions ? 10 : 9} className="border-x-2 border-t-2 border-sky-200 px-3 py-2">
                            <div className="flex flex-wrap items-center gap-2 text-[11px] text-sky-900">
                              <strong className="rounded bg-sky-700 px-2 py-0.5 text-white">Regra composta</strong>
                              <span>{components.join(" + ")}</span>
                              <span className="text-sky-700">Componentes do mesmo lançamento ficam juntos aqui e no CSV.</span>
                            </div>
                          </td>
                        </tr>
                      )}
                      {group.map((item, index) => (
                        <Fragment key={item.id}>
                          {editor(item, true, false, false, showActions, composite)}
                          {item.movimentos?.length ? (
                            <tr className={composite ? "bg-sky-50/60" : "bg-slate-50"}>
                              <td colSpan={showActions ? 10 : 9} className={`${composite ? `border-x-2 border-sky-200 ${index === group.length - 1 ? "border-b-2" : ""}` : ""} px-3 pb-3 pt-1`}>
                                <p className={`mb-1 text-[10px] font-semibold uppercase ${composite ? "text-sky-700" : "text-slate-500"}`}>Lançamentos cobertos</p>
                                <div className={`divide-y text-[11px] leading-[1.25] text-slate-600 ${composite ? "divide-sky-200 border-y border-sky-200" : "divide-slate-200 border-y border-slate-200"}`}>
                                  {item.movimentos.map((movement, index) => (
                                    <div className="grid grid-cols-[72px_minmax(220px,1fr)_max-content_64px] gap-x-3 gap-y-1 py-1.5 max-sm:grid-cols-1 max-sm:gap-y-1" key={`${movement.data}-${index}`}>
                                      <strong className="whitespace-nowrap text-slate-700">{movement.data}</strong>
                                      <div className="min-w-0 space-y-0.5 whitespace-normal break-words [overflow-wrap:anywhere]">
                                        <p><span className="text-[10px] font-semibold text-slate-500">Texto Extrato: </span>{movement.texto_extrato || movement.historico}</p>
                                        {movement.tem_comprovante && <p><span className="text-[10px] font-semibold text-slate-500">Texto Comprovante: </span>{movement.texto_comprovante || "Não identificado"}</p>}
                                      </div>
                                      <span className="whitespace-nowrap text-slate-700">{movement.tipo_componente && `${componentLabel(movement.tipo_componente)} · `}R$ {Number(movement.valor).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</span>
                                      <span className="whitespace-nowrap text-slate-700">{movement.natureza_contabil}</span>
                                    </div>
                                  ))}
                                </div>
                              </td>
                            </tr>
                          ) : null}
                        </Fragment>
                      ))}
                    </Fragment>
                  );
                })}
          </tbody>
        </table>
      </div>
      )}
      {coverageModal && <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-4">
        <div className="w-full max-w-2xl rounded-xl bg-white p-5 shadow-xl">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold text-slate-900">Confirmar regra</h3>
              <p className="mt-1 text-xs leading-5 text-slate-600">
                Esta regra vai cobrir {coverageModal.preview.quantidade} lançamento(s). Confira antes de salvar.
              </p>
            </div>
            <button
              aria-label="Fechar confirmação"
              title="Fechar"
              disabled={busyRuleId === coverageModal.item.id}
              onClick={() => setCoverageModal(null)}
              className="rounded border p-1 text-slate-600 disabled:opacity-60"
            >
              <X size={16} />
            </button>
          </div>
          <div className="mt-3 rounded border border-slate-200 bg-slate-50 p-2 text-[11px] text-slate-700">
            <div className="grid grid-cols-2 gap-2 max-sm:grid-cols-1">
              <p><strong>Gatilho:</strong> {coverageModal.body.gatilho || "—"}</p>
              <p><strong>Comprovante:</strong> {coverageModal.body.gatilho_comprovante || "—"}</p>
              <p><strong>Não contém:</strong> {coverageModal.body.texto_exclusao || "—"}</p>
              <p><strong>Débito:</strong> {coverageModal.body.conta_debito}</p>
              <p><strong>Crédito:</strong> {coverageModal.body.conta_credito}</p>
              <p className="col-span-2 max-sm:col-span-1"><strong>Histórico:</strong> {coverageModal.body.historico}</p>
            </div>
          </div>
          <div className="mt-3 max-h-72 overflow-auto rounded border border-slate-200 text-xs">
            <div className="sticky top-0 grid grid-cols-[86px_minmax(180px,1fr)_120px] gap-2 bg-white px-3 py-2 text-[10px] font-semibold uppercase text-slate-500 shadow-sm max-sm:grid-cols-1">
              <span>Data</span>
              <span>Lançamento</span>
              <span>Fonte</span>
            </div>
            {coverageModal.preview.lancamentos.map((movement, index) => (
              <div className="grid grid-cols-[86px_minmax(180px,1fr)_120px] gap-2 border-t px-3 py-2 max-sm:grid-cols-1" key={`${movement.data}-${movement.historico}-${index}`}>
                <strong className="whitespace-nowrap text-slate-700">{movement.data}</strong>
                <div className="min-w-0">
                  <p className="break-words leading-4">{movement.historico}</p>
                  {movement.componente && <span className="mt-1 inline-block rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold text-slate-600">{componentLabel(movement.componente)}</span>}
                </div>
                <span className="text-slate-600">{movement.fonte}</span>
              </div>
            ))}
          </div>
          <div className="mt-4 flex justify-end gap-2">
            <button
              disabled={busyRuleId === coverageModal.item.id}
              onClick={() => setCoverageModal(null)}
              className="rounded border px-3 py-1.5 text-xs font-semibold text-slate-700 disabled:opacity-60"
            >
              Cancelar
            </button>
            <button
              disabled={busyRuleId === coverageModal.item.id}
              onClick={() => submitRule(coverageModal.item, coverageModal.body, coverageModal.existing)}
              className="rounded bg-teal-700 px-3 py-1.5 text-xs font-semibold text-white disabled:cursor-wait disabled:opacity-60"
            >
              {busyRuleId === coverageModal.item.id ? "Salvando..." : "Salvar e ir para regras salvas"}
            </button>
          </div>
        </div>
      </div>}
      {confirmClearAll && <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-4">
        <div className="w-full max-w-md rounded-xl bg-white p-5 shadow-xl">
          <h3 className="text-sm font-semibold text-slate-900">Limpar todas as regras?</h3>
          <p className="mt-2 text-xs leading-5 text-slate-600">As regras deste período serão removidas. Regras globais serão apenas ignoradas neste período; meses anteriores não serão alterados.</p>
          <div className="mt-4 flex justify-end gap-2">
            <button disabled={busyRuleId === "all"} onClick={() => setConfirmClearAll(false)} className="rounded border px-3 py-1.5 text-xs font-semibold text-slate-700">Cancelar</button>
            <button disabled={busyRuleId === "all"} onClick={clearAllRules} className="rounded bg-red-700 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-60">{busyRuleId === "all" ? "Limpando..." : "Sim, limpar todas"}</button>
          </div>
        </div>
      </div>}
      {deleteTarget && <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-4">
        <div className="w-full max-w-md rounded-xl bg-white p-5 shadow-xl">
          <h3 className="text-sm font-semibold text-slate-900">{deleteTarget.escopo === "periodo" ? "Excluir regra deste período?" : "Esta regra é global"}</h3>
          <p className="mt-2 text-xs leading-5 text-slate-600">{deleteTarget.escopo === "periodo" ? <>A regra <strong>{deleteTarget.gatilho || deleteTarget.historico}</strong> vale somente para esta conciliação.</> : <>A regra <strong>{deleteTarget.gatilho || deleteTarget.historico}</strong> está disponível para todas as conciliações deste cliente e banco. Escolha onde ela deve ser removida.</>}</p>
          <div className="mt-4 space-y-2">
            {deleteTarget.escopo === "periodo" ? <button disabled={busyRuleId === deleteTarget.id} onClick={() => remove("global")} className="w-full rounded border border-red-200 bg-red-50 px-3 py-2 text-left text-xs font-semibold text-red-800 disabled:opacity-60">{busyRuleId === deleteTarget.id ? "Excluindo..." : "Excluir regra deste período"}</button> : <><button disabled={busyRuleId === deleteTarget.id} onClick={() => remove("periodo")} className="w-full rounded border border-violet-300 bg-violet-50 px-3 py-2 text-left text-xs font-semibold text-violet-900 disabled:opacity-60">{busyRuleId === deleteTarget.id ? "Removendo..." : "Remover somente deste período"}<span className="mt-0.5 block font-normal text-violet-700">Os demais meses continuam usando a regra.</span></button><button disabled={busyRuleId === deleteTarget.id} onClick={() => remove("global")} className="w-full rounded border border-red-200 bg-red-50 px-3 py-2 text-left text-xs font-semibold text-red-800 disabled:opacity-60">{busyRuleId === deleteTarget.id ? "Excluindo..." : "Excluir de todos os períodos"}<span className="mt-0.5 block font-normal text-red-700">A regra será desativada para este cliente e banco.</span></button></>}
          </div>
          <div className="mt-4 flex justify-end"><button disabled={busyRuleId === deleteTarget.id} onClick={() => setDeleteTarget(null)} className="rounded border px-3 py-1.5 text-xs font-semibold text-slate-700">Cancelar</button></div>
        </div>
      </div>}
    </section>
  );
}

function LegacyResultTable({
  rows,
  onView,
}: {
  rows: ResultRow[];
  onView: (viewer: Viewer) => void;
}) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const reconciliationClass = (value: string | null) =>
    String(value ?? "").startsWith("Conciliado")
      ? "bg-emerald-100 text-emerald-800"
      : String(value ?? "").startsWith("Extrato +") ||
          String(value ?? "").includes("Possível")
        ? "bg-amber-100 text-amber-800"
        : "bg-red-100 text-red-800";
  const movementTag = (value: string | null) => {
    const text = String(value ?? "").toUpperCase();
    if (text.includes("TARIFA"))
      return [
        "Tarifa",
        "bg-slate-200 text-slate-700",
        "border-l-slate-400",
        "bg-slate-50",
      ];
    if (text.includes("COBRANÇA"))
      return [
        "Cobrança",
        "bg-sky-100 text-sky-800",
        "border-l-sky-400",
        "bg-sky-50",
      ];
    if (text.includes("SEG CRÉD") || text.includes("SEGURO"))
      return [
        "Seguro",
        "bg-violet-100 text-violet-800",
        "border-l-violet-400",
        "bg-violet-50",
      ];
    if (text.includes("RENDE FÁCIL") || text.includes("RENDIMENTO"))
      return [
        "Rendimento",
        "bg-teal-100 text-teal-800",
        "border-l-teal-400",
        "bg-teal-50",
      ];
    if (text.includes("PIX"))
      return [
        "PIX",
        "bg-emerald-100 text-emerald-800",
        "border-l-emerald-400",
        "bg-emerald-50",
      ];
    if (text.includes("TED") || text.includes("TRANSFERÊNCIA"))
      return [
        "Transferência",
        "bg-orange-100 text-orange-800",
        "border-l-orange-400",
        "bg-orange-50",
      ];
    if (text.includes("BOLETO"))
      return [
        "Boleto",
        "bg-amber-100 text-amber-800",
        "border-l-amber-400",
        "bg-amber-50",
      ];
    if (text.includes("IMPOSTO") || text.includes("DAS"))
      return [
        "Imposto",
        "bg-rose-100 text-rose-800",
        "border-l-rose-400",
        "bg-rose-50",
      ];
    if (text.includes("CARTÃO"))
      return [
        "Cartão",
        "bg-indigo-100 text-indigo-800",
        "border-l-indigo-400",
        "bg-indigo-50",
      ];
    return null;
  };
  const eye = (file: string | null | undefined, page: string | number | null | undefined, title: string) =>
    file && (
      <button
        aria-label="Visualizar documento original"
        title="Visualizar documento original"
        onClick={() =>
          onView({ arquivoId: file, pagina: Number(page || 1), titulo: title })
        }
        className="ml-2 inline-flex rounded border border-slate-300 bg-white/70 p-1"
      >
        <Eye size={14} />
      </button>
    );
  return (
    <section className="overflow-hidden rounded-xl border border-slate-200 bg-white">
      <div className="flex items-center justify-between border-b px-5 py-4">
        <h2 className="font-semibold">Resultado da conciliação</h2>
        <span className="rounded-full bg-slate-100 px-2 py-1 text-xs">
          {rows.length} movimentos
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1180px] text-left text-xs">
          <thead className="bg-slate-50 text-[10px] uppercase text-slate-500">
            <tr>
              {[
                "Data",
                "Tipo de pagamento",
                "Extrato",
                "Comprovante bancário",
                "Comprovante RFB",
                "Valor",
                "Natureza contábil",
                "Fonte",
                "Situação",
                "",
              ].map((item) => (
                <th className="px-3 py-2" key={item}>
                  {item}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const tag = movementTag(row.extrato);
              return (
                <>
                  <tr
                    className={`border-t border-l-4 align-top ${tag?.[3] ?? "bg-white"} ${tag?.[2] ?? "border-l-transparent"}`}
                    key={String(row.id)}
                  >
                    <td className="whitespace-nowrap px-3 py-3 font-medium">
                      {row.data}
                    </td>
                    <td className="px-3 py-3">{row.tipo_pagamento}</td>
                    <td className="whitespace-pre-line px-3 py-3">
                      {row.extrato}
                      {eye(
                        row.extrato_arquivo_id,
                        row.extrato_pagina,
                        "Extrato bancário",
                      )}
                    </td>
                    <td className="whitespace-pre-line px-3 py-3">
                      {row.comprovante_bancario}
                      {row.comprovante_tipo === "emprestimo" && (
                        <span className="mt-2 block">
                          <LoanReceiptNotice compact />
                        </span>
                      )}
                      {eye(
                        row.comprovante_arquivo_id,
                        row.comprovante_pagina,
                        "Comprovante bancário",
                      )}
                    </td>
                    <td className="whitespace-pre-line px-3 py-3">
                      {row.comprovante_rfb}
                      {eye(
                        row.rfb_arquivo_id,
                        row.rfb_pagina,
                        "Comprovante RFB",
                      )}
                    </td>
                    <td className="whitespace-nowrap px-3 py-3">{row.valor}</td>
                    <td className={`px-3 py-3 font-semibold ${row.natureza_contabil === "Débito" ? "text-blue-700" : "text-red-700"}`}>{row.natureza_contabil}</td>
                    <td className="px-3 py-3">{row.fonte_regra}</td>
                    <td className="px-3 py-3">
                      <span
                        className={`rounded-full px-2 py-1 text-[10px] font-medium ${reconciliationClass(row.situacao)}`}
                      >
                        {row.situacao}
                      </span>
                    </td>
                    <td className="px-3 py-3">
                      <button
                        onClick={() =>
                          setExpanded(
                            expanded === row.id ? null : String(row.id),
                          )
                        }
                        className="rounded border border-slate-300 bg-white/70 px-2 py-1"
                      >
                        {expanded === row.id ? "Fechar" : "Detalhes"}
                      </button>
                    </td>
                  </tr>
                  {expanded === row.id && (
                    <tr
                      className={`border-t ${tag?.[3] ?? "bg-white"}`}
                      key={`${row.id}-details`}
                    >
                      <td className="px-3 py-3 text-slate-600" colSpan={10}>
                        <p>
                          Confiança: {row.confianca} | Total dos lançamentos:{" "}
                          {row.total_lancamentos} | Diferença: {row.diferenca}
                        </p>
                        {row.lancamentos?.length ? (
                          <div className="mt-3 overflow-x-auto rounded border border-slate-200 bg-white">
                            <h3 className="border-b bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-700">
                              Itens contabeis
                            </h3>
                            <table className="w-full min-w-[900px] text-left text-xs">
                              <thead className="bg-slate-50 text-[10px] uppercase text-slate-500">
                                <tr>
                                  {[
                                    "Componente / Descrição",
                                    "Valor",
                                    "Efeito",
                                    "Débito",
                                    "Crédito",
                                    "Histórico",
                                  ].map((column) => (
                                    <th className="px-3 py-2" key={column}>
                                      {column}
                                    </th>
                                  ))}
                                </tr>
                              </thead>
                              <tbody>
                                {row.lancamentos.map((item) => (
                                  <tr
                                    className="border-t align-top"
                                    key={item.id}
                                  >
                                    <td className="px-3 py-2">
                                      <strong className="block text-slate-800">
                                        {item.componente}
                                      </strong>
                                      <span>{item.descricao}</span>
                                    </td>
                                    <td className="whitespace-nowrap px-3 py-2">
                                      {item.valor}
                                    </td>
                                    <td className="px-3 py-2">
                                      {item.efeito_no_total}
                                    </td>
                                    <td className="px-3 py-2">
                                      {item.conta_debito}
                                    </td>
                                    <td className="px-3 py-2">
                                      {item.conta_credito}
                                    </td>
                                    <td className="px-3 py-2">
                                      {item.historico}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        ) : null}
                      </td>
                    </tr>
                  )}
                </>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function EditableResultTable({
  rows,
  reconciliationId,
  onView,
  onSaved,
}: {
  rows: ResultRow[];
  reconciliationId: string;
  onView: (viewer: Viewer) => void;
  onSaved: () => void;
}) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<
    Record<string, Record<string, Partial<AccountingItem>>>
  >({});
  const [extras, setExtras] = useState<Record<string, AccountingItem[]>>({});
  const [saving, setSaving] = useState<string | null>(null);
  const [usageSaving, setUsageSaving] = useState<string | null>(null);
  const [error, setError] = useState("");
  const value = (
    rowId: string,
    item: AccountingItem,
    field: "conta_debito" | "conta_credito" | "historico" | "complemento",
  ) => drafts[rowId]?.[item.id]?.[field] ?? item[field];
  const change = (
    rowId: string,
    item: AccountingItem,
    field: "conta_debito" | "conta_credito" | "historico" | "complemento",
    input: string,
  ) =>
    setDrafts((current) => ({
      ...current,
      [rowId]: {
        ...current[rowId],
        [item.id]: {
          ...current[rowId]?.[item.id],
           conta_debito: value(rowId, item, "conta_debito"),
           conta_credito: value(rowId, item, "conta_credito"),
           historico: value(rowId, item, "historico"),
           complemento: value(rowId, item, "complemento"),
          [field]: input,
        },
      },
    }));
  const decimal = (input: string) => {
    const value = input.replace(/[^\d,.-]/g, "");
    const comma = value.lastIndexOf(","),
      dot = value.lastIndexOf(".");
    const normalized =
      comma > dot
        ? value.replaceAll(".", "").replace(",", ".")
        : value.replaceAll(",", "");
    const number = Number(normalized);
    return Number.isFinite(number) ? number.toFixed(2) : null;
  };
  const itemsFor = (row: ResultRow) => [
    ...(row.lancamentos ?? []),
    ...(extras[String(row.id)] ?? []),
  ];
  const newComplementaryItem = (): AccountingItem => ({
    id: `novo-${Date.now()}-${Math.random().toString(36).slice(2)}`,
    componente: "OUTRO",
    categoria: "OUTRO",
    tributo: "",
    codigo_receita: "",
    descricao: "Lançamento complementar",
    efeito_no_total: "SOMA",
    valor: "R$ 0,00",
    conta_debito: "",
    conta_credito: "",
    historico: "",
    complemento: "",
    origem: "manual",
    status: "novo",
  });
  function addComplementary(row: ResultRow) {
    const rowId = String(row.id);
    const item = newComplementaryItem();
    setExpanded(rowId);
    setExtras((current) => ({
      ...current,
      [rowId]: [...(current[rowId] ?? []), item],
    }));
    setDrafts((current) => ({
      ...current,
      [rowId]: {
        ...current[rowId],
        [item.id]: {
          valor: "",
          conta_debito: "",
          conta_credito: "",
          historico: "",
          complemento: "",
        },
      },
    }));
  }
  function removeUnsavedComplementary(rowId: string, itemId: string) {
    setExtras((current) => ({
      ...current,
      [rowId]: (current[rowId] ?? []).filter((item) => item.id !== itemId),
    }));
    setDrafts((current) => {
      const rowDrafts = { ...(current[rowId] ?? {}) };
      delete rowDrafts[itemId];
      return { ...current, [rowId]: rowDrafts };
    });
  }
  async function save(row: ResultRow, selected?: AccountingItem) {
    const rowId = String(row.id);
    const items = selected ? [selected] : itemsFor(row);
    const payload = items.map((item) => {
      const valor = decimal(drafts[rowId]?.[item.id]?.valor ?? item.valor);
        return (
          valor && {
          id: item.id.startsWith("novo-") ? "" : item.id,
          componente: item.componente,
          valor,
          efeito_no_total: item.efeito_no_total,
          conta_debito: value(rowId, item, "conta_debito"),
          conta_credito: value(rowId, item, "conta_credito"),
          historico: value(rowId, item, "historico"),
          complemento: value(rowId, item, "complemento"),
          descricao: item.descricao,
          tributo: item.tributo,
          codigo_receita: item.codigo_receita,
        }
      );
    });
    if (payload.some((item) => !item))
      return setError("Há um valor de lançamento inválido.");
    setSaving(rowId);
    setError("");
    try {
      const response = await fetch(
        `${API}/api/conciliacoes/${reconciliationId}/correspondencias/${rowId}/lancamentos`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ itens: payload }),
        },
      );
      if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error(data?.detail ?? "Não foi possível salvar os itens.");
      }
      setDrafts((current) => ({ ...current, [rowId]: {} }));
      onSaved();
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Não foi possível salvar os itens.",
      );
    } finally {
      setSaving(null);
    }
  }
  async function setMovementUsage(row: ResultRow, usar: boolean) {
    const movementId = row.movimento_id;
    if (!movementId) return;
    setUsageSaving(String(row.id));
    setError("");
    try {
      const response = await fetch(`${API}/api/conciliacoes/${reconciliationId}/movimentos-extrato/${movementId}/uso`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ usar }),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error(data?.detail ?? "Não foi possível atualizar o lançamento.");
      }
      if (!usar) setExpanded((current) => current === String(row.id) ? null : current);
      onSaved();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Não foi possível atualizar o lançamento.");
    } finally {
      setUsageSaving(null);
    }
  }
  return (
    <section className="overflow-hidden rounded-xl border border-slate-200 bg-white">
      <div className="flex items-center justify-between border-b px-5 py-4">
        <h2 className="font-semibold">Resultado da conciliação</h2>
        <span className="rounded-full bg-slate-100 px-2 py-1 text-xs">
          {rows.length} movimentos
        </span>
      </div>
      {error && (
        <p className="border-b border-red-200 bg-red-50 px-5 py-2 text-xs text-red-700">
          {error}
        </p>
      )}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[900px] text-left text-xs">
          <thead className="bg-slate-50 text-[10px] uppercase text-slate-500">
            <tr>
              {[
                "Uso",
                "Data",
                "Tipo de pagamento",
                "Extrato",
                "Valor",
                "Situação",
                "",
              ].map((item) => (
                <th className="px-3 py-2" key={item}>
                  {item}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const rowId = String(row.id);
              const usedInPeriod = row.usado_no_periodo !== false;
              return (
                <Fragment key={rowId}>
                  <tr className={`border-t align-top ${usedInPeriod ? "" : "bg-slate-50 text-slate-500"}`}>
                    <td className="whitespace-nowrap px-3 py-3">
                      <MovementUsageToggle
                        used={usedInPeriod}
                        busy={usageSaving === rowId}
                        onToggle={() => setMovementUsage(row, !usedInPeriod)}
                      />
                    </td>
                    <td className="whitespace-nowrap px-3 py-3 font-medium">
                      {row.data}
                    </td>
                    <td className="px-3 py-3">{row.tipo_pagamento}</td>
                    <td className="whitespace-pre-line px-3 py-3">
                      {row.extrato}
                      {row.comprovante_tipo === "emprestimo" && (
                        <span className="mt-2 block whitespace-normal">
                          <LoanReceiptNotice compact />
                        </span>
                      )}
                      {row.extrato_arquivo_id && (
                        <button
                          aria-label="Visualizar extrato bancário"
                          onClick={() =>
                            onView({
                              arquivoId: String(row.extrato_arquivo_id),
                              pagina: Number(row.extrato_pagina || 1),
                              titulo: "Extrato bancário",
                            })
                          }
                          className="ml-2 inline-flex rounded border p-1"
                        >
                          <Eye size={14} />
                        </button>
                      )}
                    </td>
                    <td className="whitespace-nowrap px-3 py-3">{row.valor}</td>
                    <td className="px-3 py-3">{row.situacao}</td>
                    <td className="px-3 py-3">
                      <div className="flex items-center gap-1.5">
                        <button
                          disabled={!usedInPeriod}
                          onClick={() =>
                            setExpanded(expanded === rowId ? null : rowId)
                          }
                          className="rounded border border-slate-300 bg-white/70 px-2 py-1 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          {expanded === rowId ? "Fechar" : "Configurar"}
                        </button>
                        <button
                          disabled={!usedInPeriod}
                          onClick={() => addComplementary(row)}
                          title="Adicionar lançamento complementar"
                          aria-label="Adicionar lançamento complementar"
                          className="rounded border border-teal-700 bg-teal-50 p-1.5 text-teal-800 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          <Plus size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                  {expanded === rowId && (
                    <tr className="border-t bg-slate-50">
                      <td colSpan={7} className="px-3 py-3">
                        <p className="text-slate-600">
                          Confiança: {row.confianca} | Total dos lançamentos:{" "}
                          {row.total_lancamentos} | Diferença: {row.diferenca}
                        </p>
                        {row.comprovante_tipo === "emprestimo" && (
                          <div className="mt-2">
                            <LoanReceiptNotice />
                          </div>
                        )}
                        {(() => {
                          const composition = (
                            row as unknown as {
                              comprovante_composicao?: Record<
                                string,
                                string | boolean
                              >;
                            }
                          ).comprovante_composicao;
                          return (
                            composition && (
                              <div
                                className={`mt-3 rounded border p-3 text-xs ${composition.confere ? "border-emerald-200 bg-emerald-50" : "border-amber-200 bg-amber-50"}`}
                              >
                                <strong>Informações do comprovante</strong>
                                <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1">
                                  <span>
                                    Documento: {composition.valor_documento}
                                  </span>
                                  <span>
                                    Cobrado: {composition.valor_cobrado}
                                  </span>
                                  <span>
                                    Desconto/abatimento: {composition.desconto}
                                  </span>
                                  <span>Juros: {composition.juros}</span>
                                  <span>Multa: {composition.multa}</span>
                                  <span>Encargos: {composition.encargos}</span>
                                </div>
                                <p className="mt-1">
                                  Conferência: {composition.valor_calculado} |
                                  Diferença: {composition.diferenca}
                                </p>
                              </div>
                            )
                          );
                        })()}
                        <div className="mt-3 overflow-x-auto rounded border bg-white">
                            <div className="flex items-center justify-between border-b bg-slate-50 px-3 py-2">
                              <h3 className="text-xs font-semibold text-slate-700">
                                Detalhamento dos lançamentos
                              </h3>
                              <div className="flex gap-2">
                                <button
                                  onClick={() => addComplementary(row)}
                                  className="rounded border border-teal-700 px-2 py-1 text-xs font-semibold text-teal-800"
                                >
                                  Adicionar complementar
                                </button>
                                <button
                                  disabled={saving === rowId || !itemsFor(row).length}
                                  onClick={() => save(row)}
                                  className="rounded bg-teal-700 px-2 py-1 text-xs font-semibold text-white disabled:opacity-60"
                                >
                                  {saving === rowId
                                    ? "Salvando..."
                                    : "Salvar todos"}
                                </button>
                              </div>
                            </div>
                            {itemsFor(row).length ? (
                            <table className="w-full min-w-[900px] text-left text-xs">
                              <thead className="bg-slate-50 text-[10px] uppercase text-slate-500">
                                <tr>
                                  {[
                                    "Componente / Descrição",
                                    "Valor",
                                    "Efeito",
                                    "Débito",
                                     "Crédito",
                                     "Histórico",
                                     "Complemento",
                                     "Ação",
                                   ].map((column) => (
                                    <th className="px-3 py-2" key={column}>
                                      {column}
                                    </th>
                                  ))}
                                </tr>
                              </thead>
                              <tbody>
                                {itemsFor(row).map((item) => (
                                  <tr
                                    className={`border-t align-top ${item.efeito_no_total === "OUTROS" || ["DESCONTO", "ABATIMENTO", "DESCONTO_ABATIMENTO"].includes(item.componente) ? "bg-violet-50/70 italic text-violet-950" : ""}`}
                                    key={item.id}
                                  >
                                    <td className="px-3 py-2">
                                      <strong className="block text-slate-800">
                                        {item.componente}
                                      </strong>
                                      <span>{item.descricao}</span>
                                      {(item.efeito_no_total === "OUTROS" || ["DESCONTO", "ABATIMENTO", "DESCONTO_ABATIMENTO"].includes(item.componente)) && <span className="ml-1 rounded bg-violet-200 px-1 py-0.5 text-[9px] font-semibold not-italic text-violet-900">Outros</span>}
                                    </td>
                                    <td className="whitespace-nowrap px-3 py-2">
                                      <input
                                        value={
                                          drafts[rowId]?.[item.id]?.valor ??
                                          item.valor
                                        }
                                        onChange={(event) =>
                                          setDrafts((current) => ({
                                            ...current,
                                            [rowId]: {
                                              ...current[rowId],
                                              [item.id]: {
                                                ...current[rowId]?.[item.id],
                                                valor: event.target.value,
                                              },
                                            },
                                          }))
                                        }
                                        className="w-24 rounded border px-1.5 py-1"
                                      />
                                    </td>
                                    <td className="px-3 py-2">
                                      {item.efeito_no_total}
                                    </td>
                                    <td className="px-3 py-1">
                                      <input
                                        list="catalogo-contas"
                                        value={value(
                                          rowId,
                                          item,
                                          "conta_debito",
                                        )}
                                        onChange={(event) => {
                                          change(
                                            rowId,
                                            item,
                                            "conta_debito",
                                            event.target.value,
                                          );
                                          showInputStart(event.currentTarget);
                                        }}
                                        onBlur={(event) => showInputStart(event.currentTarget)}
                                        className="w-32 rounded border px-1.5 py-1 pr-5 text-left"
                                      />
                                    </td>
                                    <td className="px-3 py-1">
                                      <input
                                        list="catalogo-contas"
                                        value={value(
                                          rowId,
                                          item,
                                          "conta_credito",
                                        )}
                                        onChange={(event) => {
                                          change(
                                            rowId,
                                            item,
                                            "conta_credito",
                                            event.target.value,
                                          );
                                          showInputStart(event.currentTarget);
                                        }}
                                        onBlur={(event) => showInputStart(event.currentTarget)}
                                        className="w-32 rounded border px-1.5 py-1 pr-5 text-left"
                                      />
                                    </td>
                                    <td className="px-3 py-1">
                                      <input
                                        list="catalogo-historicos"
                                        value={value(rowId, item, "historico")}
                                        onChange={(event) => {
                                          change(
                                            rowId,
                                            item,
                                            "historico",
                                            event.target.value,
                                          );
                                          showInputStart(event.currentTarget);
                                        }}
                                        onBlur={(event) => showInputStart(event.currentTarget)}
                                        className="w-48 rounded border px-1.5 py-1 pr-5 text-left"
                                      />
                                    </td>
                                    <td className="px-3 py-1">
                                      <input
                                        value={value(rowId, item, "complemento")}
                                        onChange={(event) => change(rowId, item, "complemento", event.target.value)}
                                        className="w-64 rounded border px-1.5 py-1"
                                        placeholder={item.competencia_nao_identificada ? "Competência não identificada" : "Complemento"}
                                      />
                                      {item.imposto && <p className={`mt-1 text-[10px] ${item.competencia_nao_identificada ? "text-amber-700" : "text-emerald-700"}`}>{item.imposto}{item.competencia ? ` · Competência ${item.competencia}` : " · Competência não identificada"}{item.comprovante_origem ? ` · ${item.comprovante_origem}` : ""}</p>}
                                    </td>
                                    <td className="px-3 py-1">
                                      <div className="flex items-center gap-1">
                                        <button
                                          disabled={saving === rowId}
                                          onClick={() => save(row, item)}
                                          className="rounded border border-teal-700 px-2 py-1 text-teal-800"
                                        >
                                          Salvar
                                        </button>
                                        {item.id.startsWith("novo-") && (
                                          <button
                                            disabled={saving === rowId}
                                            onClick={() => removeUnsavedComplementary(rowId, item.id)}
                                            title="Remover"
                                            aria-label="Remover lançamento complementar"
                                            className="rounded border border-red-200 p-1 text-red-600"
                                          >
                                            <Trash2 size={13} />
                                          </button>
                                        )}
                                      </div>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                            ) : (
                              <p className="px-3 py-4 text-xs text-slate-500">
                                Nenhum lançamento contábil neste registro.
                              </p>
                            )}
                          </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ConciliacaoFlow({
  initialBank,
  initialClientId,
}: {
  initialBank?: string;
  initialClientId?: string;
}) {
  const [clients, setClients] = useState<Client[]>([]),
    [clientId, setClientId] = useState(initialClientId || ""),
    [newClient, setNewClient] = useState("");
  const [bank, setBank] = useState(visibleBank(initialBank)),
    [start, setStart] = useState(""),
    [end, setEnd] = useState(""),
    [reconciliationId, setReconciliationId] = useState("");
  const [selectedBankAccount, setSelectedBankAccount] = useState<{ agencia: string; conta: string; titular: string } | null>(null);
  const [processId, setProcessId] = useState(""),
    [processBanks, setProcessBanks] = useState<
      { id: string; banco: string; status: string }[]
    >([]),
    [isSwitchingBank, setIsSwitchingBank] = useState(false);
  const [review, setReview] = useState<Review>({
      extratos: [],
      comprovantes: [],
      rfb: [],
      arquivos: [],
    }),
    [results, setResults] = useState<ResultRow[] | null>(null),
    [reviewLoading, setReviewLoading] = useState(false),
    [resultsLoading, setResultsLoading] = useState(false),
    [unused, setUnused] = useState<Unused>({
      comprovantes: [],
      rfb: [],
      resumo: { comprovantes: {}, rfb: {} },
    }),
    [viewer, setViewer] = useState<Viewer | null>(null),
    [activeTab, setActiveTab] = useState("Início"),
    [message, setMessage] = useState(""),
    [isReconciling, setIsReconciling] = useState(false),
    [rulesVersion, setRulesVersion] = useState(0),
    [resultsVersion, setResultsVersion] = useState(0),
    [reviewVersion, setReviewVersion] = useState(0);
  const resultRequest = useRef(0);
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const requestedProcess = params.get("process");
    const requestedBank = params.get("bank");
    const fallbackBank = requestedBank ? visibleBank(requestedBank) : visibleBank(initialBank || localStorage.getItem("conciliai_banco"));
    const storedClientId = params.get("client") || initialClientId || localStorage.getItem("conciliai_cliente_id") || "";
    fetch(`${API}/api/clientes`)
      .then((r) => r.json())
      .then((loadedClients: Client[]) => {
        setClients(loadedClients);
        if (storedClientId && loadedClients.some((client) => client.id === storedClientId)) {
          setClientId(storedClientId);
          return;
        }
        if (storedClientId) localStorage.removeItem("conciliai_cliente_id");
        setClientId("");
      })
      .catch(() => setMessage("Sistema indisponível no momento."));
    setBank(fallbackBank);
    if (!requestedProcess) return;
    fetch(`${API}/api/processos-conciliacao/${requestedProcess}`)
      .then((response) => (response.ok ? response.json() : Promise.reject()))
      .then((process) => {
        setProcessId(process.id);
        setClientId(process.cliente_id);
        setStart(process.data_inicio);
        setEnd(process.data_fim);
        setProcessBanks(process.bancos);
        const reconciliation =
          process.bancos.find(
            (item: { id: string; banco: string }) =>
              item.id === params.get("reconciliation") ||
              item.banco === requestedBank,
          ) || process.bancos[0];
        if (!reconciliation) {
          setReconciliationId("");
          window.history.replaceState(null, "", `/conciliacao?process=${process.id}`);
          return;
        }
        setBank(reconciliation.banco);
        setReconciliationId(reconciliation.id);
        window.history.replaceState(
          null,
          "",
          `/conciliacao?process=${process.id}&bank=${encodeURIComponent(reconciliation.banco)}&reconciliation=${reconciliation.id}`,
        );
      })
      .catch(() => setMessage("Processo de conciliação não encontrado."));
  }, [initialBank, initialClientId]);
  useEffect(() => {
    if (!reconciliationId) return;
    let cancelled = false;
    setReviewLoading(true);
    fetch(`${API}/api/conciliacoes/${reconciliationId}/revisao`, { cache: "no-store" })
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => {
        if (!cancelled && data) setReview(data);
      })
      .finally(() => {
        if (!cancelled) setReviewLoading(false);
      });
    return () => { cancelled = true; };
  }, [reconciliationId, reviewVersion]);
  useEffect(() => {
    if (!clientId) {
      setSelectedBankAccount(null);
      return;
    }
    if (clients.length && !clients.some((client) => client.id === clientId)) {
      localStorage.removeItem("conciliai_cliente_id");
      setClientId("");
      setSelectedBankAccount(null);
      return;
    }
    let cancelled = false;
    fetch(`${API}/api/clientes/${clientId}/contas-bancarias`)
      .then((response) => (response.ok ? response.json() : []))
      .then((accounts) => {
        if (!cancelled) setSelectedBankAccount(accounts.find((account: { banco: string }) => account.banco === bank) ?? null);
      })
      .catch(() => {
        if (!cancelled) setSelectedBankAccount(null);
      });
    return () => { cancelled = true; };
  }, [clientId, bank, clients]);
  useAutoDismissMessage(message, setMessage);
  useEffect(() => {
    if (
      !reconciliationId ||
      !["Conciliação", "Conciliação Avançada"].includes(activeTab)
    ) {
      setResultsLoading(false);
      return;
    }
    const request = ++resultRequest.current;
    const controller = new AbortController();
    setResultsLoading(true);
    Promise.all([
      fetch(`${API}/api/conciliacoes/${reconciliationId}/resultado`, { cache: "no-store", signal: controller.signal }).then(
        (response) => (response.ok ? response.json() : []),
      ),
      fetch(
        `${API}/api/conciliacoes/${reconciliationId}/documentos-nao-utilizados`,
        { cache: "no-store", signal: controller.signal },
      ).then((response) => (response.ok ? response.json() : null)),
    ]).then(([storedResults, storedUnused]) => {
      if (request !== resultRequest.current) return;
      setResults(Array.isArray(storedResults) ? storedResults : []);
      if (storedUnused) setUnused(storedUnused);
    }).catch((error) => {
      if (error.name !== "AbortError" && request === resultRequest.current) setMessage("Não foi possível carregar os valores.");
    }).finally(() => {
      if (request === resultRequest.current) setResultsLoading(false);
    });
    return () => controller.abort();
  }, [activeTab, reconciliationId, resultsVersion]);
  async function createClient() {
    const response = await fetch(`${API}/api/clientes`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nome: newClient }),
    });
    const client = await response.json();
    setClients((items) => [...items, client]);
    setClientId(client.id);
    setNewClient("");
  }
  async function createReconciliation() {
    if (processId && !reconciliationId) {
      await selectProcessBank(bank);
      return;
    }
    if (reconciliationId)
      return setMessage(
        "Esta conciliação já está em andamento. Envie os documentos ou acesse a aba Conciliação.",
      );
    const response = await fetch(`${API}/api/conciliacoes`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        cliente_id: clientId,
        banco: bank,
        data_inicio: start,
        data_fim: end,
      }),
    });
    if (!response.ok)
      return setMessage("Preencha cliente e período corretamente.");
    const data = await response.json();
    setReconciliationId(data.id);
    setProcessId(data.processo_id || "");
    setProcessBanks([{ id: data.id, banco: data.banco, status: data.status }]);
    setReview({ extratos: [], comprovantes: [], rfb: [], arquivos: [] });
    setResults(null);
    setUnused({
      comprovantes: [],
      rfb: [],
      resumo: { comprovantes: {}, rfb: {} },
    });
    setMessage("Conciliação criada. Envie os documentos.");
  }
  async function selectProcessBank(selectedBank: string) {
    if (!processId || (selectedBank === bank && reconciliationId) || isSwitchingBank) return;
    setIsSwitchingBank(true);
    try {
      let reconciliation = processBanks.find(
        (item) => item.banco === selectedBank,
      );
      if (!reconciliation) {
        const response = await fetch(
          `${API}/api/processos-conciliacao/${processId}/bancos`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ banco: selectedBank }),
          },
        );
        if (!response.ok)
          throw new Error(
            (await response.json()).detail ??
              "Não foi possível abrir este banco.",
          );
        reconciliation = await response.json();
        setProcessBanks((items) => [...items, reconciliation!]);
      }
      if (!reconciliation)
        throw new Error("Não foi possível abrir este banco.");
      setBank(reconciliation.banco);
      setReconciliationId(reconciliation.id);
      setActiveTab("Início");
      setResults(null);
      setUnused({
        comprovantes: [],
        rfb: [],
        resumo: { comprovantes: {}, rfb: {} },
      });
      window.history.replaceState(
        null,
        "",
        `/conciliacao?process=${processId}&bank=${encodeURIComponent(reconciliation.banco)}&reconciliation=${reconciliation.id}`,
      );
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Não foi possível abrir este banco.",
      );
    } finally {
      setIsSwitchingBank(false);
    }
  }
  async function upload(type: string, event: ChangeEvent<HTMLInputElement>) {
    const files = event.target.files;
    if (!files || !reconciliationId) return;
    try {
      for (const file of Array.from(files)) {
        const form = new FormData();
        form.append("file", file);
        const response = await fetch(
          `${API}/api/conciliacoes/${reconciliationId}/arquivos?tipo_documento=${type}`,
          { method: "POST", body: form },
        );
        if (!response.ok)
          throw new Error(
            (await response.json()).detail ?? "Não foi possível enviar o PDF.",
          );
      }
      const response = await fetch(
        `${API}/api/conciliacoes/${reconciliationId}/revisao`,
      );
      if (!response.ok)
        throw new Error("Não foi possível atualizar os dados extraídos.");
      setReview(await response.json());
      setResults(null);
      setUnused({
        comprovantes: [],
        rfb: [],
        resumo: { comprovantes: {}, rfb: {} },
      });
      const documentName =
        type === "extrato"
          ? "Extrato"
          : type === "comprovante"
            ? "Comprovantes bancários"
            : type === "rfb"
              ? "Comprovantes RFB"
              : documentTypeLabel(type, bank);
      setMessage(
        `${documentName} disponível. Continue na aba Início para enviar os demais documentos.`,
      );
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Falha no envio do arquivo.",
      );
    } finally {
      event.target.value = "";
    }
  }
  async function reprocessDocument(fileId: string) {
    try {
      const response = await fetch(
        `${API}/api/arquivos/${fileId}/reprocessar`,
        { method: "POST" },
      );
      if (!response.ok)
        throw new Error(
          (await response.json()).detail ??
            "Não foi possível reprocessar o extrato.",
        );
      const result = await response.json();
      const reviewResponse = await fetch(
        `${API}/api/conciliacoes/${reconciliationId}/revisao`,
      );
      setReview(await reviewResponse.json());
      setResults(null);
      setUnused({
        comprovantes: [],
        rfb: [],
        resumo: { comprovantes: {}, rfb: {} },
      });
      setMessage(
        `Documento reprocessado: ${result.registros_extraidos} registros encontrados.`,
      );
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Falha no reprocessamento.",
      );
    }
  }
  async function deleteDocument(fileId: string) {
    if (
      !confirm(
        "Excluir este arquivo e seus dados extraídos? A conciliação precisará ser executada novamente.",
      )
    )
      return;
    const response = await fetch(`${API}/api/arquivos/${fileId}`, {
      method: "DELETE",
    });
    if (!response.ok)
      return setMessage(
        (await response.json()).detail ?? "Não foi possível excluir o arquivo.",
      );
    const reviewResponse = await fetch(
      `${API}/api/conciliacoes/${reconciliationId}/revisao`,
    );
    setReview(await reviewResponse.json());
    setResults(null);
    setUnused({
      comprovantes: [],
      rfb: [],
      resumo: { comprovantes: {}, rfb: {} },
    });
    setMessage(
      "Arquivo excluído. Execute a conciliação novamente após revisar os documentos.",
    );
  }
  async function reconcileDocuments() {
    try {
      resultRequest.current += 1;
      setIsReconciling(true);
      setMessage("Conciliando documentos...");
      const response = await fetch(
        `${API}/api/conciliacoes/${reconciliationId}/conciliar`,
        { method: "POST" },
      );
      if (!response.ok)
        throw new Error(
          (await response.json()).detail ?? "Não foi possível conciliar.",
        );
      const completion = await response.json();
      if (completion.conciliacoes_geradas === 0)
        throw new Error(
          "Esta conciliação não possui lançamentos do extrato. Inicie uma nova e envie os documentos novamente.",
        );
      const resultResponse = await fetch(
        `${API}/api/conciliacoes/${reconciliationId}/resultado`,
      );
      if (!resultResponse.ok)
        throw new Error(
          "Não foi possível carregar o resultado da conciliação.",
        );
      setResults(await resultResponse.json());
      const unusedResponse = await fetch(
        `${API}/api/conciliacoes/${reconciliationId}/documentos-nao-utilizados`,
      );
      if (!unusedResponse.ok)
        throw new Error("Não foi possível carregar o resumo dos documentos.");
      setUnused(await unusedResponse.json());
      setMessage("Conciliação concluída. Revise os resultados.");
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Falha na conciliação.",
      );
    } finally {
      setIsReconciling(false);
    }
  }
  const theme =
    bank === "Banco do Brasil"
      ? "border-amber-500 text-amber-800 bg-amber-50"
      : bank === "Santander" || bank === "Bradesco"
        ? "border-red-600 text-red-800 bg-red-50"
        : bank === "BASA"
          ? "border-lime-600 text-lime-800 bg-lime-50"
          : bank === "Caixa"
            ? "border-sky-600 text-sky-800 bg-sky-50"
            : "border-emerald-700 text-emerald-800 bg-emerald-50";
  const numberValue = (value: string | null | undefined) =>
    Number(
      String(value ?? "0")
        .replace("R$", "")
        .replaceAll(".", "")
        .replace(",", ".")
        .trim(),
    ) || 0;
  const extratoDebito = review.extratos
    .filter((item) => item.natureza === "Débito")
    .reduce((total, item) => total + numberValue(item.valor), 0);
  const extratoCredito = review.extratos
    .filter((item) => item.natureza === "Crédito")
    .reduce((total, item) => total + numberValue(item.valor), 0);
  const rulesToCreate =
    results?.filter((item) => item.fonte_regra === "extrato").length ?? 0;
  const isSantander = bank === "Santander";
  const isNotesArea = bank === "Notas";
  const machineTabLabel = isSantander ? "Getnet" : "Maquininhas";
  const machineUploadLabel = machineDocumentLabel(bank);
  const machineFiles = review.arquivos.filter((file) => isMachineDocumentType(file.tipo));
  const loanFiles = review.arquivos.filter((file) => file.tipo === "emprestimo");
  const noteFiles = review.arquivos.filter((file) => file.tipo === "nota");
  const machineReceipts = review.maquininhas ?? [];
  const loanReceipts = review.emprestimos ?? [];
  const invoiceRows = review.notas ?? [];
  const getnetAdjustments = review.ajustes_getnet ?? [];
  const bankReceipts = review.comprovantes;
  const navigationTabs = [
    "Início",
    ...(isNotesArea
      ? review.arquivos.length
        ? ["Notas Extraídas", "Regras"]
        : []
      : review.arquivos.length
      ? [
          "Extrato",
          "Comprovantes bancários",
          machineTabLabel,
          "Comprovantes RFB",
          "Empréstimos/Financiamentos",
          "Conciliação",
          "Conciliação Avançada",
        ]
      : []),
  ];
  function downloadCsv() {
    if (!reconciliationId) return;
    window.location.assign(
      `${API}/api/conciliacoes/${reconciliationId}/lancamentos-contabeis.csv`,
    );
  }
  const periodCard = formatPeriodCard(start, end);
  return (
    <>
      <>
        {processId && (
          <ProcessTopBar
            processId={processId}
            activeBank={bank}
            processBanks={processBanks}
            onSelectBank={selectProcessBank}
            isSwitching={isSwitchingBank}
          />
        )}
      </>
      {(reviewLoading || resultsLoading) && <LoadingValuesOverlay />}
      <main className="workspace-main mx-auto max-w-[90rem] px-3 py-3 sm:px-4">
        <div className="mb-5 flex items-center justify-center gap-2 overflow-x-auto border-b text-sm">
          <div className="flex shrink-0">
            {navigationTabs.map((item) => (
              <button
                onClick={() => setActiveTab(item)}
                className={`flex shrink-0 items-center gap-1.5 border-b-2 px-4 py-2 ${activeTab === item ? `${theme} font-semibold` : "border-transparent text-slate-500"}`}
                key={item}
              >
                {item === "Conciliação Avançada" && <WandSparkles size={15} />}{" "}
                {item}
              </button>
            ))}
          </div>
          {periodCard && (
            <div className="mb-1 inline-flex shrink-0 items-center gap-1.5 rounded-md border border-emerald-300 bg-emerald-50 px-3 py-1.5 text-xs font-bold text-emerald-900 shadow-sm">
              <CalendarDays className="text-emerald-700" size={14} />
              {periodCard}
            </div>
          )}
        </div>
        {activeTab === "Início" && (
          <>
            <section className="rounded-xl border border-slate-200 bg-white p-5">
              <h2 className="mb-4 font-semibold">
                Início e período da conciliação
              </h2>
              <div className="grid gap-3 md:grid-cols-4">
                <div className="rounded-md border bg-slate-50 p-2">
                  <span className="block text-xs text-slate-500">
                    Cliente selecionado
                  </span>
                  <strong className="text-sm">
                    {clients.find((client) => client.id === clientId)?.nome ||
                      "Selecione no topo"}
                  </strong>
                </div>
                <div className="rounded-md border bg-slate-50 p-2">
                  <span className="block text-xs text-slate-500">{isNotesArea ? "Área" : "Banco"}</span>
                  <strong className="text-sm">{bank}</strong>
                </div>
                <label className="text-xs text-slate-500">
                  Data inicial
                  <input
                    type="date"
                    value={start}
                    onChange={(e) => setStart(e.target.value)}
                    className="mt-1 w-full rounded-md border p-2 text-sm text-slate-800"
                  />
                </label>
                <label className="text-xs text-slate-500">
                  Data final
                  <input
                    type="date"
                    value={end}
                    onChange={(e) => setEnd(e.target.value)}
                    className="mt-1 w-full rounded-md border p-2 text-sm text-slate-800"
                  />
                </label>
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    onClick={createReconciliation}
                    className={`rounded-md px-4 py-2 font-medium text-white ${bank === "Banco do Brasil" ? "bg-amber-600" : bank === "Santander" || bank === "Bradesco" ? "bg-red-700" : bank === "BASA" ? "bg-lime-700" : bank === "Caixa" ? "bg-sky-700" : bank === "Conta Caixa" ? "bg-cyan-800" : "bg-emerald-800"}`}
                  >
                    Iniciar conciliação
                  </button>
                  {!isNotesArea && (
                    <span className="rounded-md border border-sky-200 bg-sky-50 px-3 py-2 text-xs text-sky-900" title={`Titular: ${selectedBankAccount?.titular || "Não informado"}`}>Agência: <strong>{selectedBankAccount?.agencia || "—"}</strong> · Conta: <strong>{selectedBankAccount?.conta || "Sem conta"}</strong></span>
                  )}
                </div>
              </div>
            </section>
            {reconciliationId && (
              <section className="my-6 grid gap-4 md:grid-cols-3 xl:grid-cols-5">
                {[
                  ...(isNotesArea
                    ? [["nota", "Notas fiscais", true]]
                    : [
                        ["extrato", "Extrato bancário", false],
                        ["comprovante", "Comprovantes bancários", true],
                        ["rfb", "Comprovantes da Receita Federal", true],
                        ["maquininha_extrato", machineUploadLabel, true],
                        ["emprestimo", "Empréstimos/Financiamentos", true],
                      ]),
                ].map(([type, label, multiple]) => (
                  <label
                    className={`cursor-pointer rounded-xl border-2 border-dashed bg-white p-5 text-center ${
                      isMachineDocumentType(String(type))
                        ? "border-red-200 hover:border-red-700"
                        : "border-slate-300 hover:border-teal-600"
                    }`}
                    key={String(type)}
                  >
                    <Upload className={`mx-auto mb-2 ${isMachineDocumentType(String(type)) ? "text-red-700" : "text-teal-700"}`} />
                    <strong className="block">{String(label)}</strong>
                    <input
                      className="hidden"
                      type="file"
                      accept={String(type) === "emprestimo" ? "application/pdf,.pdf,.xlsx,.xlsm,.csv,text/csv" : "application/pdf,.pdf"}
                      multiple={Boolean(multiple)}
                      onChange={(event) => upload(String(type), event)}
                    />
                  </label>
                ))}
              </section>
            )}
          </>
        )}
        {reconciliationId && activeTab === "Início" && (
          <section className="mb-5 rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="font-semibold">Arquivos enviados</h2>
                <p className="text-sm text-slate-500">
                  Acesse cada aba para revisar os registros extraídos.
                </p>
              </div>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-sm font-semibold">
                {review.arquivos.length} arquivo(s)
              </span>
            </div>
            {review.arquivos.length > 0 && (
              <ul className="mt-4 divide-y rounded-md border text-sm">
                {review.arquivos.map((file) => (
                  <li
                    className="flex items-center justify-between gap-3 px-3 py-2"
                    key={file.id}
                  >
                    <span className="min-w-0 truncate">{file.nome}</span>
                    <span className="ml-auto shrink-0 text-slate-500">
                      {documentTypeLabel(file.tipo, bank)} · {file.status}
                    </span>
                    <button
                      onClick={() =>
                        setViewer({
                          arquivoId: file.id,
                          pagina: 1,
                          titulo: documentTypeLabel(file.tipo, bank),
                        })
                      }
                      title="Visualizar arquivo"
                      aria-label={`Visualizar ${file.nome}`}
                      className="shrink-0 rounded p-1 text-slate-700 hover:bg-slate-100"
                    >
                      <Eye size={15} />
                    </button>
                    <button
                      onClick={() => reprocessDocument(file.id)}
                      title="Reprocessar arquivo"
                      aria-label={`Reprocessar ${file.nome}`}
                      className="shrink-0 rounded p-1 text-teal-700 hover:bg-teal-50"
                    >
                      <RefreshCw size={15} />
                    </button>
                    <button
                      onClick={() => deleteDocument(file.id)}
                      title="Excluir arquivo"
                      aria-label={`Excluir ${file.nome}`}
                      className="shrink-0 rounded p-1 text-red-600 hover:bg-red-50"
                    >
                      <Trash2 size={15} />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}
        {message && (
          <p className="mb-5 rounded-md bg-teal-50 p-3 text-sm text-teal-900">
            {message}
          </p>
        )}
        {reconciliationId && isNotesArea && activeTab === "Notas Extraídas" && (
          <div className="space-y-5">
            <Table
              title="Notas fiscais extraídas"
              columns={[
                "Data emissao",
                "Data vencimento",
                "Data pagamento",
                "Fornecedor",
                "Cpf cnpj",
                "Numero nota",
                "Forma pagamento",
                "Tipo pagamento",
                "Classificacao",
                "Motivo",
                "Gera csv",
                "Destino",
                "Modo lancamento",
                "Linhas csv",
                "Conta antecipacao",
                "Motivo nao geracao",
                "Valor total",
                "Situacao",
              ]}
              rows={invoiceRows}
              onView={setViewer}
            />
          </div>
        )}
        {reconciliationId && isNotesArea && activeTab === "Regras" && (
          <div className="space-y-5">
            <IndependentRulesPanel
              reconciliationId={reconciliationId}
              source="nota"
              title="Notas"
              triggerLabel="Tomador, forma ou serviço"
              onView={setViewer}
            />
          </div>
        )}
        {reconciliationId && activeTab === "Extrato" && (
          <div className="space-y-4">
            {review.saldos?.saldo_anterior && (
              <section className="flex w-full flex-wrap items-center justify-between gap-3 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3">
                <div>
                  <p className="text-xs font-semibold uppercase text-emerald-700">
                    Saldo anterior
                  </p>
                  <strong className="text-lg text-emerald-950">
                    {review.saldos.saldo_anterior}
                  </strong>
                </div>
                <span className="text-sm font-medium text-emerald-800">
                  Saldo Disponível Inicial
                </span>
              </section>
            )}
            <Table
              title="Lançamentos do extrato"
              columns={["Data", "Hora", "Historico", "Valor", "Natureza"]}
              rows={review.extratos}
              onView={setViewer}
            />
          </div>
        )}
        {reconciliationId && activeTab === "Comprovantes bancários" && (
          <Table
            title="Comprovantes bancários"
            columns={[
              "Data",
              "Hora",
              "Documento",
              "Favorecido",
              "Valor original",
              "Ajustes",
              "Valor pago",
              "Tipo",
            ]}
            rows={bankReceipts}
            onView={setViewer}
          />
        )}
        {reconciliationId && activeTab === machineTabLabel && (
          <div className="space-y-5">
            <section className="rounded-xl border border-slate-200 bg-white p-5">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div>
                  <h2 className="font-semibold">{isSantander ? "Getnet" : "Maquininhas"}</h2>
                  <p className="text-sm text-slate-500">
                    {isSantander ? "Extratos Getnet enviados no início do processo." : "Extratos de maquininha enviados no início do processo."}
                  </p>
                </div>
                <span className="rounded-full bg-red-50 px-3 py-1 text-xs font-semibold text-red-800">
                  {machineFiles.length} arquivo(s)
                </span>
              </div>
              {machineFiles.length > 0 && (
                <ul className="divide-y rounded-md border text-sm">
                  {machineFiles.map((file) => (
                    <li className="flex items-center justify-between gap-3 px-3 py-2" key={file.id}>
                      <span className="min-w-0 truncate">{file.nome}</span>
                      <span className="ml-auto shrink-0 text-slate-500">{documentTypeLabel(file.tipo, bank)} · {file.status}</span>
                      <button
                        onClick={() =>
                          setViewer({
                            arquivoId: file.id,
                            pagina: 1,
                            titulo: documentTypeLabel(file.tipo, bank),
                          })
                        }
                        title="Visualizar arquivo"
                        aria-label={`Visualizar ${file.nome}`}
                        className="shrink-0 rounded p-1 text-slate-700 hover:bg-slate-100"
                      >
                        <Eye size={15} />
                      </button>
                      <button
                        onClick={() => reprocessDocument(file.id)}
                        title="Reprocessar arquivo"
                        aria-label={`Reprocessar ${file.nome}`}
                        className="shrink-0 rounded p-1 text-teal-700 hover:bg-teal-50"
                      >
                        <RefreshCw size={15} />
                      </button>
                      <button
                        onClick={() => deleteDocument(file.id)}
                        title="Excluir arquivo"
                        aria-label={`Excluir ${file.nome}`}
                        className="shrink-0 rounded p-1 text-red-600 hover:bg-red-50"
                      >
                        <Trash2 size={15} />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>
            {isSantander && (
            <section className="rounded-xl border border-red-200 bg-white p-5">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div>
                  <h2 className="font-semibold">Juros sobre antecipações — Getnet</h2>
                  <p className="text-sm text-slate-500">Conferência pelo valor líquido Getnet contra os créditos Getnet no Santander.</p>
                </div>
                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">
                  {getnetAdjustments.length} competência(s)
                </span>
              </div>
              {getnetAdjustments.length ? (
                <div className="grid gap-3 lg:grid-cols-2">
                  {getnetAdjustments.map((adjustment) => {
                    const generated = Boolean(adjustment.lancamento);
                    const statusClass =
                      adjustment.situacao === "Ajuste lançado"
                        ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                        : adjustment.situacao === "Pendente em regras"
                          ? "border-rose-200 bg-rose-50 text-rose-800"
                        : adjustment.situacao === "Divergência para revisão"
                          ? "border-amber-200 bg-amber-50 text-amber-800"
                          : adjustment.situacao === "Dados insuficientes"
                            ? "border-slate-200 bg-slate-50 text-slate-600"
                            : "border-sky-200 bg-sky-50 text-sky-800";
                    return (
                      <article className="rounded-lg border border-slate-200 p-3" key={adjustment.competencia}>
                        <div className="mb-3 flex items-center justify-between gap-2">
                          <strong>{adjustment.competencia_label}</strong>
                          <span className={`rounded-full border px-2 py-1 text-[11px] font-semibold ${statusClass}`}>
                            {adjustment.situacao}
                          </span>
                        </div>
                        <div className="grid grid-cols-3 gap-2 text-xs">
                          <div>
                            <span className="block text-slate-500">Getnet líquido</span>
                            <strong>{formatMoney(adjustment.total_getnet)}</strong>
                          </div>
                          <div>
                            <span className="block text-slate-500">Santander</span>
                            <strong>{formatMoney(adjustment.total_santander)}</strong>
                          </div>
                          <div>
                            <span className="block text-slate-500">Diferença</span>
                            <strong>{formatMoney(adjustment.diferenca)}</strong>
                          </div>
                        </div>
                        {generated && adjustment.lancamento && (
                          <div className="mt-3 rounded-md border border-emerald-200 bg-emerald-50 p-2 text-xs text-emerald-900">
                            <div className="font-semibold">{adjustment.lancamento.data} · {adjustment.lancamento.historico}</div>
                            <div>{formatMoney(adjustment.lancamento.valor)} · {adjustment.lancamento.complemento}</div>
                          </div>
                        )}
                      </article>
                    );
                  })}
                </div>
              ) : (
                <div className="rounded-lg border border-dashed border-slate-200 px-3 py-6 text-center text-sm text-slate-500">
                  Nenhuma competência Getnet disponível.
                </div>
              )}
            </section>
            )}
            <Table
              title={isSantander ? "Registros Getnet" : "Registros de maquininha"}
              columns={[
                "Data",
                "Hora",
                "Documento",
                "Favorecido",
                "Valor original",
                "Ajustes",
                "Valor pago",
                "Tipo",
              ]}
              rows={machineReceipts}
              onView={setViewer}
            />
            <IndependentRulesPanel
              reconciliationId={reconciliationId}
              source="maquininha"
              title={isSantander ? "Getnet" : "Maquininha"}
              triggerLabel="Favorecido"
              onView={setViewer}
            />
          </div>
        )}
        {reconciliationId && activeTab === "Comprovantes RFB" && (
          <Table
            title="Comprovantes da Receita Federal"
            columns={[
              "Tipo",
              "Competencia apuracao",
              "Data arrecadacao",
              "Documento",
              "Banco",
              "Principal",
              "Multa juros",
              "Total",
              "Situacao",
            ]}
            rows={review.rfb}
            onView={setViewer}
          />
        )}
        {reconciliationId && activeTab === "Empréstimos/Financiamentos" && (
          <div className="space-y-5">
            <section className="rounded-xl border border-slate-200 bg-white p-5">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div>
                  <h2 className="font-semibold">Empréstimos/Financiamentos</h2>
                  <p className="text-sm text-slate-500">
                    Contratos enviados no início do processo e usados na conciliação.
                  </p>
                </div>
                <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-800">
                  {loanFiles.length} arquivo(s)
                </span>
              </div>
              {loanFiles.length > 0 ? (
                <ul className="divide-y rounded-md border text-sm">
                  {loanFiles.map((file) => (
                    <li className="flex items-center justify-between gap-3 px-3 py-2" key={file.id}>
                      <span className="min-w-0 truncate">{file.nome}</span>
                      <span className="ml-auto shrink-0 text-slate-500">{documentTypeLabel(file.tipo, bank)} · {file.status}</span>
                      <button
                        onClick={() =>
                          setViewer({
                            arquivoId: file.id,
                            pagina: 1,
                            titulo: documentTypeLabel(file.tipo, bank),
                          })
                        }
                        title="Visualizar arquivo"
                        aria-label={`Visualizar ${file.nome}`}
                        className="shrink-0 rounded p-1 text-slate-700 hover:bg-slate-100"
                      >
                        <Eye size={15} />
                      </button>
                      <button
                        onClick={() => reprocessDocument(file.id)}
                        title="Reprocessar arquivo"
                        aria-label={`Reprocessar ${file.nome}`}
                        className="shrink-0 rounded p-1 text-teal-700 hover:bg-teal-50"
                      >
                        <RefreshCw size={15} />
                      </button>
                      <button
                        onClick={() => deleteDocument(file.id)}
                        title="Excluir arquivo"
                        aria-label={`Excluir ${file.nome}`}
                        className="shrink-0 rounded p-1 text-red-600 hover:bg-red-50"
                      >
                        <Trash2 size={15} />
                      </button>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="rounded-lg border border-dashed border-slate-200 px-3 py-6 text-center text-sm text-slate-500">
                  Nenhum contrato enviado.
                </div>
              )}
            </section>
            <Table
              title="Registros de empréstimos/financiamentos"
              columns={[
                "Data",
                "Hora",
                "Documento",
                "Favorecido",
                "Valor original",
                "Ajustes",
                "Valor pago",
                "Tipo",
              ]}
              rows={loanReceipts}
              onView={setViewer}
            />
          </div>
        )}
        {reconciliationId && activeTab === "Conciliação Avançada" && (
          <div className="space-y-3">
            <AdvancedOverview
              reconciliationId={reconciliationId}
              version={rulesVersion}
            />
            <AdvancedRulesPanel
              reconciliationId={reconciliationId}
              version={rulesVersion}
              onView={setViewer}
              onRulesChanged={() => {
                setRulesVersion((version) => version + 1);
                setResultsVersion((version) => version + 1);
              }}
            />
          </div>
        )}
        {reconciliationId && activeTab === "Conciliação" && (
          <div className="space-y-5">
            <section className="grid gap-4 md:grid-cols-4">
              <div className="rounded-xl border border-sky-200 bg-sky-50 p-5">
                <p className="text-sm font-medium text-sky-900">
                  Lançamentos do extrato
                </p>
                <strong className="mt-2 block text-3xl text-sky-950">
                  {review.extratos.length}
                </strong>
                <p className="mt-1 text-sm text-sky-800">
                  registros disponíveis
                </p>
              </div>
              <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-5">
                <p className="text-sm font-medium text-emerald-900">
                  Comprovantes bancários
                </p>
                <strong className="mt-2 block text-3xl text-emerald-950">
                  {review.comprovantes.length}
                </strong>
                <p className="mt-1 text-sm text-emerald-800">
                  registros disponíveis
                </p>
              </div>
              <div className="rounded-xl border border-violet-200 bg-violet-50 p-5">
                <p className="text-sm font-medium text-violet-900">
                  Comprovantes RFB
                </p>
                <strong className="mt-2 block text-3xl text-violet-950">
                  {review.rfb.length}
                </strong>
                <p className="mt-1 text-sm text-violet-800">
                  registros disponíveis
                </p>
              </div>
              <div className="rounded-xl border border-amber-200 bg-amber-50 p-5">
                <p className="text-sm font-medium text-amber-900">
                  Empréstimos/Financiamentos
                </p>
                <strong className="mt-2 block text-3xl text-amber-950">
                  {loanReceipts.length}
                </strong>
                <p className="mt-1 text-sm text-amber-800">
                  registros disponíveis
                </p>
              </div>
            </section>
            {review.extratos.length > 0 && (
              <button
                onClick={reconcileDocuments}
                className="rounded-md bg-teal-700 px-4 py-2 font-medium text-white"
              >
                Conciliar documentos
              </button>
            )}
            {results && results.length > 0 && (
              <>
                <EditableResultTable rows={results} reconciliationId={reconciliationId} onView={setViewer} onSaved={() => {
                  setRulesVersion((version) => version + 1);
                  setResultsVersion((version) => version + 1);
                }} />
                <section className="grid gap-3 md:grid-cols-3">
                  <div className="rounded-xl border bg-white p-4 text-sm">
                    <strong>Resumo dos comprovantes bancários</strong>
                    <p>
                      Total: {unused.resumo.comprovantes.total ?? 0} |
                      Utilizados: {unused.resumo.comprovantes.utilizados ?? 0} |
                      Não utilizados:{" "}
                      {unused.resumo.comprovantes.nao_utilizados ?? 0} | Fora do
                      período: {unused.resumo.comprovantes.fora_periodo ?? 0}
                    </p>
                  </div>
                  <div className="rounded-xl border bg-white p-4 text-sm">
                    <strong>Resumo dos empréstimos/financiamentos</strong>
                    <p>
                      Total: {unused.resumo.emprestimos?.total ?? 0} |
                      Utilizados: {unused.resumo.emprestimos?.utilizados ?? 0} |
                      Não utilizados:{" "}
                      {unused.resumo.emprestimos?.nao_utilizados ?? 0} | Fora do
                      período: {unused.resumo.emprestimos?.fora_periodo ?? 0}
                    </p>
                  </div>
                  <div className="rounded-xl border bg-white p-4 text-sm">
                    <strong>Resumo dos comprovantes RFB</strong>
                    <p>
                      Total: {unused.resumo.rfb.total ?? 0} | Utilizados:{" "}
                      {unused.resumo.rfb.utilizados ?? 0} | Não utilizados:{" "}
                      {unused.resumo.rfb.nao_utilizados ?? 0} | Fora do período:{" "}
                      {unused.resumo.rfb.fora_periodo ?? 0}
                    </p>
                  </div>
                </section>
                <Table
                  title="Comprovantes bancários não utilizados"
                  columns={[
                    "Data",
                    "Hora",
                    "Favorecido",
                    "Valor pago",
                    "Tipo",
                    "Situacao",
                  ]}
                  rows={unused.comprovantes}
                  showOrigin={false}
                />
                <Table
                  title="Empréstimos/financiamentos não utilizados"
                  columns={[
                    "Data",
                    "Documento",
                    "Favorecido",
                    "Valor pago",
                    "Tipo",
                    "Situacao",
                  ]}
                  rows={unused.emprestimos ?? []}
                  showOrigin={false}
                />
                <Table
                  title="Comprovantes RFB não utilizados"
                  columns={[
                    "Tipo",
                    "Data arrecadacao",
                    "Documento",
                    "Banco",
                    "Total",
                    "Situacao",
                  ]}
                  rows={unused.rfb}
                  showOrigin={false}
                />
              </>
            )}
          </div>
        )}
        {viewer && <PdfModal viewer={viewer} onClose={() => setViewer(null)} />}
      </main>
    </>
  );
}
