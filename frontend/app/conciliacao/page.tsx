"use client";

import { ChangeEvent, Fragment, useEffect, useRef, useState } from "react";
import {
  BookOpenCheck,
  CheckCircle2,
  Copy,
  Download,
  Eye,
  FileText,
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
const banks = [
  "Banco do Brasil",
  "Santander",
  "BASA",
  "Bradesco",
  "Caixa",
  "Conta Caixa",
  "Vendas com Cartão",
  "Comissões Getnet",
  "Apropriações",
  "Empréstimos/Financeiro",
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
  origem: string;
  status: string;
};
type ResultRow = Row & { lancamentos?: AccountingItem[] };
type Review = {
  extratos: Row[];
  comprovantes: Row[];
  rfb: Row[];
  arquivos: {
    id: string;
    nome: string;
    tipo: string;
    status: string;
    erro: string | null;
  }[];
};
type Unused = {
  comprovantes: Row[];
  rfb: Row[];
  resumo: { comprovantes: Record<string, number>; rfb: Record<string, number> };
};
type Viewer = { arquivoId: string; pagina: number; titulo: string };

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
  debit,
  credit,
  current,
}: {
  label: string;
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
    ["Anterior", 0, "border-slate-200 bg-slate-50"],
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

function OtherSummary({ debit, credit, total }: { debit: number; credit: number; total: number }) {
  const money = (value: number) => value.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return <div className="flex items-center gap-3"><div className="w-12 shrink-0 text-xs font-semibold text-violet-700">Outros</div><div className="grid flex-1 grid-cols-3 gap-1"><div className="flex items-baseline justify-center gap-1 rounded-md border border-indigo-200 bg-indigo-50 px-2 py-1 text-center text-indigo-800"><span className="text-[9px] uppercase text-indigo-600">Débito:</span><strong className="text-xs">{money(debit)}</strong></div><div className="flex items-baseline justify-center gap-1 rounded-md border border-fuchsia-200 bg-fuchsia-50 px-2 py-1 text-center text-fuchsia-800"><span className="text-[9px] uppercase text-fuchsia-600">Crédito:</span><strong className="text-xs">{money(credit)}</strong></div><div className="flex items-baseline justify-center gap-1 rounded-md border border-violet-300 bg-violet-100 px-2 py-1 text-center text-violet-900"><span className="text-[9px] uppercase text-violet-700">Total:</span><strong className="text-xs">{money(total)}</strong></div></div></div>;
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
      extrato: { debito: string; credito: string; outros: string; outros_debito: string; outros_credito: string };
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
          debit={Number(summary?.extrato.debito ?? 0)}
          credit={Number(summary?.extrato.credito ?? 0)}
          current={
            Number(summary?.extrato.credito ?? 0) -
            Number(summary?.extrato.debito ?? 0)
          }
        />
        <AdvancedSummary
          label="Razão"
          debit={Number(summary?.razao.debito ?? 0)}
          credit={Number(summary?.razao.credito ?? 0)}
          current={
            Number(summary?.razao.credito ?? 0) -
            Number(summary?.razao.debito ?? 0)
          }
        />
        <OtherSummary debit={Number(summary?.razao.outros_debito ?? 0)} credit={Number(summary?.razao.outros_credito ?? 0)} total={Number(summary?.razao.outros ?? 0)} />
      </div>
      <div className="text-right text-[10px] text-slate-500">
        Gera o CSV pronto para importar no ERP.
        {csvBlocked ? <span title={`Revise os lançamentos incompletos: ${data.integridade.movimentos_incompletos.map((item) => item.data).join(", ")}`} className="mt-1 flex cursor-not-allowed items-center rounded bg-slate-300 px-2 py-1 text-[10px] font-semibold text-slate-600"><Download className="mr-1" size={12} />CSV bloqueado</span> : <><a href={`${API}/api/conciliacoes/${reconciliationId}/lancamentos-contabeis.csv`} className="mt-1 flex items-center rounded bg-teal-700 px-2 py-1 text-[10px] font-semibold text-white"><Download className="mr-1" size={12} />Gerar CSV</a><a href={`${API}/api/conciliacoes/${reconciliationId}/lancamentos-contabeis-outros.csv`} className="mt-1 flex items-center rounded border border-violet-300 bg-violet-50 px-2 py-1 text-[10px] font-semibold text-violet-800"><Download className="mr-1" size={12} />CSV Outros</a><a href={`${API}/api/conciliacoes/${reconciliationId}/lancamentos-contabeis.pdf`} className="mt-1 flex items-center rounded border border-slate-300 bg-white px-2 py-1 text-[10px] font-semibold text-slate-700"><FileText className="mr-1" size={12} />Gerar PDF</a></>}
      </div>
    </section>
  );
}

type PendingRule = {
  id: string;
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
  comprovante_confere?: boolean;
  regra_compartilhada?: {
    id: string;
    banco_origem: string;
    gatilho: string;
  } | null;
};
type SavedRule = {
  id: string;
  gatilho: string;
  gatilho_comprovante?: string;
  natureza: string;
  natureza_contabil?: string;
  tipo_componente?: string;
  conta_debito: string;
  conta_credito: string;
  historico: string;
  complemento: string;
  cobertos: number;
  movimentos?: { data: string; historico: string; texto_extrato?: string; texto_comprovante?: string; tem_comprovante?: boolean; valor: string; natureza: string; natureza_contabil: string }[];
};

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
  onView,
  onRulesChanged,
}: {
  reconciliationId: string;
  onView: (viewer: Viewer) => void;
  onRulesChanged: () => void;
}) {
  const [pending, setPending] = useState<PendingRule[]>([]);
  const [saved, setSaved] = useState<SavedRule[]>([]);
  const [account, setAccount] = useState("");
  const [drafts, setDrafts] = useState<Record<string, Record<string, string>>>(
    {},
  );
  const [view, setView] = useState<"pending" | "saved">("pending");
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
  const [busyRuleId, setBusyRuleId] = useState<string | null>(null);
  const [confirmClearAll, setConfirmClearAll] = useState(false);
  const [csvPermitted, setCsvPermitted] = useState(true);
  const [catalog, setCatalog] = useState<{
    contas: string[];
    historicos: string[];
  }>({ contas: [], historicos: [] });
  async function load() {
    const [rulesResponse, accountResponse] = await Promise.all([
      fetch(`${API}/api/conciliacoes/${reconciliationId}/regras-contabeis`, { cache: "no-store" }),
      fetch(`${API}/api/conciliacoes/${reconciliationId}/conta-bancaria`, { cache: "no-store" }),
    ]);
    if (!rulesResponse.ok || !accountResponse.ok)
      return setMessage("Não foi possível carregar as regras.");
    const rules = await rulesResponse.json();
    const bankAccount = await accountResponse.json();
    setPending(
      rules.pendentes.map((item: PendingRule) => ({
        ...item,
        historico: cleanHistory(item.historico),
      })),
    );
    setSaved(
      rules.salvas.map((item: SavedRule) => ({
        ...item,
        historico: cleanHistory(item.historico),
      })),
    );
    setCsvPermitted(rules.integridade?.csv_permitido !== false);
    setAccount(bankAccount.conta_contabil || "");
  }
  useEffect(() => {
    load();
    fetch(`${API}/api/documentos-importantes/catalogo`)
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => {
        if (data) setCatalog(data);
      });
  }, [reconciliationId]);
  const value = (id: string, name: string, fallback = "") =>
    drafts[id]?.[name] ?? fallback;
  const change = (id: string, name: string, input: string) =>
    setDrafts((items) => ({ ...items, [id]: { ...items[id], [name]: input } }));
  const defaults = (item: PendingRule | SavedRule) =>
    "gatilho" in item
      ? {
           gatilho: item.gatilho,
           gatilhoComprovante: item.gatilho_comprovante || "",
          debito: item.conta_debito,
          credito: item.conta_credito,
          historico: item.historico,
          complemento: item.complemento,
        }
      : {
           gatilho: "",
           gatilhoComprovante: "",
          debito: item.natureza_contabil === "Débito" ? account : "",
          credito: item.natureza_contabil === "Crédito" ? account : "",
          historico: "",
          complemento: "Conforme extrato bancário",
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
  async function saveRule(item: PendingRule | SavedRule, existing = false) {
    if (busyRuleId) return;
    setBusyRuleId(item.id);
    const fields = defaults(item);
    const body = {
      gatilho: value(item.id, "gatilho", fields.gatilho),
      gatilho_comprovante: value(item.id, "gatilhoComprovante", fields.gatilhoComprovante),
      natureza: item.natureza_contabil || item.natureza,
      tipo_componente: item.tipo_componente || "",
      conta_debito: value(item.id, "debito", fields.debito),
      conta_credito: value(item.id, "credito", fields.credito),
      historico: value(item.id, "historico", fields.historico),
      complemento: value(item.id, "complemento", fields.complemento),
    };
    const url = existing
      ? `${API}/api/conciliacoes/${reconciliationId}/regras-contabeis/${item.id}`
      : `${API}/api/conciliacoes/${reconciliationId}/regras-contabeis`;
    try {
      const response = await fetch(url, {
        method: existing ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!response.ok) {
        const error = await response.json();
        return setMessage(error.detail ?? "Não foi possível salvar a regra.");
      }
      setMessage(
        existing
          ? "Regra atualizada e reaplicada."
          : "Regra salva e aplicada aos lançamentos compatíveis.",
      );
      setDrafts((items) => ({ ...items, [item.id]: {} }));
      await load();
      onRulesChanged();
    } finally {
      setBusyRuleId(null);
    }
  }
  async function remove(id: string) {
    if (busyRuleId) return;
    setBusyRuleId(id);
    try {
      const response = await fetch(`${API}/api/regras-contabeis/${id}`, {
        method: "DELETE",
      });
      if (!response.ok) return setMessage("Não foi possível excluir a regra.");
      await load();
      onRulesChanged();
    } finally {
      setBusyRuleId(null);
    }
  }
  async function clearAllRules() {
    if (busyRuleId) return;
    setBusyRuleId("all");
    try {
      const response = await fetch(`${API}/api/conciliacoes/${reconciliationId}/regras-contabeis`, { method: "DELETE" });
      if (!response.ok) return setMessage("Não foi possível limpar as regras.");
      setConfirmClearAll(false);
      setMessage("Todas as regras deste banco foram limpas e os lançamentos foram recalculados.");
      await load();
      onRulesChanged();
    } finally {
      setBusyRuleId(null);
    }
  }
  function legacyEditor(item: PendingRule | SavedRule, existing = false) {
    const fields = defaults(item);
    const pendingItem = "data" in item ? item : null;
    const isDebit = (item.natureza_contabil || item.natureza) === "Débito";
    const words = pendingItem?.historico.match(/[\p{L}\p{N}]+/gu) ?? [];
    const keyword = value(item.id, "gatilho", fields.gatilho);
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
          {"data" in item ? item.data : `${item.cobertos} cobertos`}
        </td>
        <td className="max-w-64 px-2 py-2">
          <p>{"gatilho" in item ? item.gatilho : item.historico}</p>
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
              onClick={() => remove(item.id)}
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
    })[component] ?? component;
  function editor(
    item: PendingRule | SavedRule,
    existing = false,
    compact = false,
    simple = false,
    showAction = true,
  ) {
    const fields = defaults(item);
    const pendingItem = "data" in item ? item : null;
    const isDebit = (item.natureza_contabil || item.natureza) === "Débito";
    const words = pendingItem?.historico.match(/[\p{L}\p{N}]+/gu) ?? [];
    const keyword = value(item.id, "gatilho", fields.gatilho);
    const receiptKeyword = value(item.id, "gatilhoComprovante", fields.gatilhoComprovante);
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
      <tr
        className={`border-t align-top ${compact ? "bg-inherit" : simple ? "border-y border-l-4 border-emerald-200 border-l-emerald-300 bg-emerald-50/70" : ""}`}
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
              {"data" in item ? item.data : `${item.cobertos} cobertos`}
            </td>
            <td className={`${existing ? "w-[14%]" : "w-64 max-w-64"} px-2 py-2`}>
              <p className="line-clamp-2 break-words leading-4" title={"gatilho" in item ? item.gatilho : item.historico}>{"gatilho" in item ? item.gatilho : item.historico}</p>
              {"gatilho" in item && item.gatilho_comprovante && <p className={`mt-1 text-[10px] text-violet-700 ${existing ? "break-words" : "max-w-64 truncate"}`} title={item.gatilho_comprovante}>Comprovante: {item.gatilho_comprovante}</p>}
              {pendingItem?.tarifa_no_extrato && <p className="mt-1 text-[10px] text-sky-700">Tarifa do comprovante está presente no extrato.</p>}
              {pendingItem?.tarifa_referente_ao_comprovante && <p className="mt-1 text-[10px] text-slate-500">Esta tarifa é referente ao comprovante de {pendingItem.tarifa_referencia_nome}, R$ {Number(pendingItem.tarifa_referencia_valor || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 })} em {pendingItem.tarifa_referencia_data}.</p>}
              {pendingItem?.composicao_simples && <p className="mt-1 whitespace-pre-line text-[10px] text-slate-500">{pendingItem.composicao_simples}</p>}
              {pendingItem?.regra_compartilhada && (
                <p className="mt-1 text-[10px] font-medium text-amber-800">
                  Regra compartilhada: {pendingItem.regra_compartilhada.gatilho}{" "}
                  (origem: {pendingItem.regra_compartilhada.banco_origem}). Não
                  crie uma duplicada.
                </p>
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
              <span
                className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${isDebit ? "bg-blue-100 text-blue-800" : "bg-red-100 text-red-800"}`}
              >
                {isDebit ? "Débito" : "Crédito"}
              </span>
          {pendingItem?.tipo_componente && !simple && (
                <span className="ml-1 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold text-slate-700">
                  {componentLabel(pendingItem.tipo_componente)}
                </span>
              )}
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
            {(pendingItem?.comprovante_arquivo_id || pendingItem?.comprovante_rfb_arquivo_id) && (
              <div className="relative mt-1 flex items-center gap-1">
                <input className="w-20 rounded border border-violet-200 px-1.5 py-1" placeholder="comprovante..." value={receiptKeyword} onChange={(event) => change(item.id, "gatilhoComprovante", event.target.value)} />
                <button title="Usar comprovante completo" onClick={() => change(item.id, "gatilhoComprovante", (pendingItem.palavras_comprovante ?? []).join(" "))} className="rounded border border-violet-200 bg-violet-50 p-1 text-violet-700 hover:border-violet-500">
                  <Copy size={13} />
                </button>
                <button title="Selecionar palavras do comprovante" onClick={() => setReceiptWordPicker(receiptWordPicker === item.id ? null : item.id)} className="rounded border border-violet-200 bg-violet-50 p-1 text-violet-700 hover:border-violet-500">
                  <Tags size={13} />
                </button>
                {receiptWordPicker === item.id && (
                  <div className="absolute left-0 top-8 z-30 w-56 rounded-lg border border-violet-200 bg-white p-2 shadow-xl">
                    <div className="mb-2 flex items-center justify-between border-b pb-1 text-[10px] font-semibold text-violet-800">Palavras dos comprovantes<button onClick={() => setReceiptWordPicker(null)} className="text-sm leading-none text-slate-500">✕</button></div>
                    {[["Banco", pendingItem.palavras_comprovante_banco ?? []], ["RFB", pendingItem.palavras_comprovante_rfb ?? []]].map(([source, words]) => Array.isArray(words) && words.length > 0 && <div className="mb-2" key={source as string}><p className="mb-1 text-[9px] font-semibold uppercase text-violet-500">{source as string}</p><div className="flex flex-wrap gap-1">{words.map((word, index) => { const selected = receiptKeyword.toUpperCase().split(/\s+/).includes(word); return <button onClick={() => change(item.id, "gatilhoComprovante", selected ? receiptKeyword.split(/\s+/).filter(part => part !== word).join(" ") : [receiptKeyword, word].filter(Boolean).join(" "))} className={`rounded px-1.5 py-0.5 text-[10px] ${selected ? "bg-violet-700 text-white" : "bg-violet-50 text-violet-800"}`} key={`${source}-${word}-${index}`}>{word}</button>; })}</div></div>)}
                  </div>
                )}
              </div>
            )}
            {keyword && (
              <div className="mt-1 w-48 text-[10px] leading-4 text-emerald-700">
                <span className="font-semibold">
                  {keywordMode[item.id] === "full"
                    ? "Histórico completo"
                    : "Palavras selecionadas"}
                </span>
                <br />✓ Este gatilho vai cobrir {coveredCount} lançamento(s)
                <br />
                <span className="text-slate-500">«{keyword}»</span>
              </div>
            )}
          </div>
        </td>
        <td className={`${existing ? "w-[10%]" : ""} px-2 py-1`}>
          <input
            list="catalogo-contas"
            title={value(item.id, "debito", fields.debito)}
            className={`${existing ? "w-full min-w-0" : "w-20"} rounded border px-1.5 py-1 pr-5 text-[10px]`}
            placeholder="Selecionar"
            value={value(item.id, "debito", fields.debito)}
            onChange={(event) => change(item.id, "debito", event.target.value)}
          />
        </td>
        <td className={`${existing ? "w-[10%]" : ""} px-2 py-1`}>
          <input
            list="catalogo-contas"
            title={value(item.id, "credito", fields.credito)}
            className={`${existing ? "w-full min-w-0" : "w-20"} rounded border px-1.5 py-1 pr-5 text-[10px]`}
            placeholder="Selecionar"
            value={value(item.id, "credito", fields.credito)}
            onChange={(event) => change(item.id, "credito", event.target.value)}
          />
        </td>
        <td className={`${existing ? "w-[14%]" : ""} px-2 py-1`}>
          <input
            list="catalogo-historicos"
            title={value(item.id, "historico", fields.historico)}
            className={`${existing ? "w-full min-w-0" : "w-28"} rounded border px-1.5 py-1 pr-5 text-[10px]`}
            placeholder="Selecionar"
            value={value(item.id, "historico", fields.historico)}
            onChange={(event) =>
              change(item.id, "historico", event.target.value)
            }
          />
        </td>
        <td className={`${existing ? "w-[13%]" : ""} px-2 py-1`}>
          <input
            className={`${existing ? "w-full min-w-0" : "w-28"} rounded border px-1.5 py-1`}
            value={value(item.id, "complemento", fields.complemento)}
            onChange={(event) =>
              change(item.id, "complemento", event.target.value)
            }
          />
        </td>
        {showAction && <td className={`${existing ? "w-[6%]" : "w-px"} whitespace-nowrap px-2 py-1`}>
          {!pendingItem?.regra_compartilhada && (
            <>
              <button title={existing ? "Atualizar regra" : "Salvar regra"} aria-label={existing ? "Atualizar regra" : "Salvar regra"} disabled={busyRuleId === item.id} onClick={() => saveRule(item, existing)} className="rounded bg-teal-700 px-2 py-1 text-white disabled:cursor-wait disabled:opacity-60">
                {busyRuleId === item.id ? <RefreshCw className="animate-spin" size={14} /> : existing ? <RefreshCw size={14} /> : <CheckCircle2 size={14} />}
              </button>
              {existing && <button title="Excluir regra" aria-label="Excluir regra" disabled={busyRuleId === item.id} onClick={() => remove(item.id)} className="ml-1 rounded border border-red-200 px-2 py-1 text-red-700 disabled:cursor-wait disabled:opacity-60"><Trash2 size={14} /></button>}
            </>
          )}
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
  const displayedItems = view === "pending" ? visible : visibleSaved;
  const showActions = displayedItems.some(
    (item) => !("data" in item && item.regra_compartilhada),
  );
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
        {csvPermitted ? <><a href={`${API}/api/conciliacoes/${reconciliationId}/lancamentos-contabeis.csv`} className="rounded bg-teal-700 px-2 py-1 text-[11px] font-semibold text-white">Gerar CSV</a><a href={`${API}/api/conciliacoes/${reconciliationId}/lancamentos-contabeis-outros.csv`} className="rounded border border-violet-300 bg-violet-50 px-2 py-1 text-[11px] font-semibold text-violet-800">CSV Outros</a><a href={`${API}/api/conciliacoes/${reconciliationId}/lancamentos-contabeis.pdf`} className="rounded border border-slate-300 bg-white px-2 py-1 text-[11px] font-semibold text-slate-700">Gerar PDF</a></> : <span className="cursor-not-allowed rounded bg-slate-200 px-2 py-1 text-[11px] font-semibold text-slate-500">CSV bloqueado</span>}
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
        {saved.length > 0 && <button onClick={() => setConfirmClearAll(true)} className="rounded-md border border-red-200 px-3 py-1.5 text-xs font-semibold text-red-700">Limpar todas</button>}
        <div className="ml-auto flex flex-wrap items-center gap-1.5 rounded-md bg-slate-50 p-1.5">
          <label className="flex items-center gap-1 text-[11px] font-medium text-slate-600">
            <span className="whitespace-nowrap">Conta deste banco</span>
            <input list="catalogo-contas" value={account} onChange={(e) => setAccount(e.target.value)} className="w-52 rounded border bg-white px-2 py-1 text-xs" placeholder="Ex.: 33 - Banco Santander S/A" />
          </label>
          <button title="Salvar conta" aria-label="Salvar conta" onClick={saveAccount} className="rounded border border-teal-700 p-1.5 text-teal-800"><CheckCircle2 size={14}/></button>
          {csvPermitted ? <><a title="Gerar CSV" aria-label="Gerar CSV" href={`${API}/api/conciliacoes/${reconciliationId}/lancamentos-contabeis.csv`} className="rounded bg-teal-700 p-1.5 text-white"><Download size={14}/></a><a title="CSV Outros" aria-label="CSV Outros" href={`${API}/api/conciliacoes/${reconciliationId}/lancamentos-contabeis-outros.csv`} className="rounded border border-violet-300 bg-violet-50 p-1.5 text-violet-800"><Download size={14}/></a><a title="Gerar PDF" aria-label="Gerar PDF" href={`${API}/api/conciliacoes/${reconciliationId}/lancamentos-contabeis.pdf`} className="rounded border border-slate-300 bg-white p-1.5 text-slate-700"><FileText size={14}/></a></> : <span title="CSV bloqueado por integridade" className="cursor-not-allowed rounded bg-slate-200 p-1.5 text-slate-500"><Download size={14}/></span>}
        </div>
      </div>
      {message && <p className="text-xs text-teal-800">{message}</p>}
      <div className="max-h-[calc(100dvh-330px)] overflow-auto rounded border overscroll-contain">
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
                              const principal = movement.componentes_cobertos?.find((item) => ["PRINCIPAL", "VALOR_COBRADO"].includes(item.componente));
                              const missing = items.reduce((total, item) => total + Number(item.valor || 0), 0);
                              const money = (value: string | number) => Number(value || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 });
                              return <span>Principal já lançado: R$ {money(principal?.valor || 0)} | Faltando: R$ {money(missing)} | Valor total do documento: R$ {money(movement.valor_documento || 0)}</span>;
                            })()}
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })
               : visibleSaved.map((item) => (
                  <Fragment key={item.id}>
                    {editor(item, true, false, false, showActions)}
                    {item.movimentos?.length ? (
                      <tr className="bg-slate-50">
                        <td colSpan={showActions ? 10 : 9} className="px-3 pb-3 pt-1">
                          <p className="mb-1 text-[10px] font-semibold uppercase text-slate-500">Lançamentos cobertos</p>
                          <div className="divide-y divide-slate-200 border-y border-slate-200 text-[11px] leading-[1.25] text-slate-600">
                            {item.movimentos.map((movement, index) => (
                              <div className="grid grid-cols-[72px_minmax(220px,1fr)_max-content_64px] gap-x-3 gap-y-1 py-1.5 max-sm:grid-cols-1 max-sm:gap-y-1" key={`${movement.data}-${index}`}>
                                <strong className="whitespace-nowrap text-slate-700">{movement.data}</strong>
                                <div className="min-w-0 space-y-0.5 whitespace-normal break-words [overflow-wrap:anywhere]">
                                  <p><span className="text-[10px] font-semibold text-slate-500">Texto Extrato: </span>{movement.texto_extrato || movement.historico}</p>
                                  {movement.tem_comprovante && <p><span className="text-[10px] font-semibold text-slate-500">Texto Comprovante: </span>{movement.texto_comprovante || "Não identificado"}</p>}
                                </div>
                                <span className="whitespace-nowrap text-slate-700">R$ {Number(movement.valor).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</span>
                                <span className="whitespace-nowrap text-slate-700">{movement.natureza_contabil}</span>
                              </div>
                            ))}
                          </div>
                        </td>
                      </tr>
                    ) : null}
                  </Fragment>
                ))}
          </tbody>
        </table>
      </div>
      {confirmClearAll && <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-4">
        <div className="w-full max-w-md rounded-xl bg-white p-5 shadow-xl">
          <h3 className="text-sm font-semibold text-slate-900">Limpar todas as regras?</h3>
          <p className="mt-2 text-xs leading-5 text-slate-600">As regras salvas deste banco serão desativadas e seus lançamentos aplicados serão removidos. Os movimentos e comprovantes não serão apagados; as sugestões voltarão para Regras a criar.</p>
          <div className="mt-4 flex justify-end gap-2">
            <button disabled={busyRuleId === "all"} onClick={() => setConfirmClearAll(false)} className="rounded border px-3 py-1.5 text-xs font-semibold text-slate-700">Cancelar</button>
            <button disabled={busyRuleId === "all"} onClick={clearAllRules} className="rounded bg-red-700 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-60">{busyRuleId === "all" ? "Limpando..." : "Sim, limpar todas"}</button>
          </div>
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
  const eye = (file: string | null, page: string | null, title: string) =>
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
  const [error, setError] = useState("");
  const value = (
    rowId: string,
    item: AccountingItem,
    field: "conta_debito" | "conta_credito" | "historico",
  ) => drafts[rowId]?.[item.id]?.[field] ?? item[field];
  const change = (
    rowId: string,
    item: AccountingItem,
    field: "conta_debito" | "conta_credito" | "historico",
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
  async function save(row: ResultRow, selected?: AccountingItem) {
    const rowId = String(row.id);
    const items = selected ? [selected] : itemsFor(row);
    const payload = items.map((item) => {
      const valor = decimal(drafts[rowId]?.[item.id]?.valor ?? item.valor);
      return (
        valor && {
          componente: item.componente,
          valor,
          efeito_no_total: item.efeito_no_total,
          conta_debito: value(rowId, item, "conta_debito"),
          conta_credito: value(rowId, item, "conta_credito"),
          historico: value(rowId, item, "historico"),
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
              return (
                <Fragment key={rowId}>
                  <tr className="border-t align-top">
                    <td className="whitespace-nowrap px-3 py-3 font-medium">
                      {row.data}
                    </td>
                    <td className="px-3 py-3">{row.tipo_pagamento}</td>
                    <td className="whitespace-pre-line px-3 py-3">
                      {row.extrato}
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
                      <button
                        onClick={() =>
                          setExpanded(expanded === rowId ? null : rowId)
                        }
                        className="rounded border border-slate-300 bg-white/70 px-2 py-1"
                      >
                        {expanded === rowId ? "Fechar" : "Configurar"}
                      </button>
                    </td>
                  </tr>
                  {expanded === rowId && (
                    <tr className="border-t bg-slate-50">
                      <td colSpan={6} className="px-3 py-3">
                        <p className="text-slate-600">
                          Confiança: {row.confianca} | Total dos lançamentos:{" "}
                          {row.total_lancamentos} | Diferença: {row.diferenca}
                        </p>
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
                        {itemsFor(row).length ? (
                          <div className="mt-3 overflow-x-auto rounded border bg-white">
                            <div className="flex items-center justify-between border-b bg-slate-50 px-3 py-2">
                              <h3 className="text-xs font-semibold text-slate-700">
                                Detalhamento dos lançamentos
                              </h3>
                              <div className="flex gap-2">
                                <button
                                  onClick={() =>
                                    setExtras((current) => ({
                                      ...current,
                                      [rowId]: [
                                        ...(current[rowId] ?? []),
                                        {
                                          id: `novo-${Date.now()}`,
                                          componente: "OUTRO",
                                          categoria: "OUTRO",
                                          tributo: "",
                                          codigo_receita: "",
                                          descricao: "Lançamento manual",
                                          efeito_no_total: "SOMA",
                                          valor: "R$ 0,00",
                                          conta_debito: "",
                                          conta_credito: "",
                                          historico: "",
                                          origem: "manual",
                                          status: "novo",
                                        },
                                      ],
                                    }))
                                  }
                                  className="rounded border border-teal-700 px-2 py-1 text-xs font-semibold text-teal-800"
                                >
                                  Adicionar lançamento
                                </button>
                                <button
                                  disabled={saving === rowId}
                                  onClick={() => save(row)}
                                  className="rounded bg-teal-700 px-2 py-1 text-xs font-semibold text-white disabled:opacity-60"
                                >
                                  {saving === rowId
                                    ? "Salvando..."
                                    : "Salvar todos"}
                                </button>
                              </div>
                            </div>
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
                                {itemsFor(row).map((item) => (
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
                                        onChange={(event) =>
                                          change(
                                            rowId,
                                            item,
                                            "conta_debito",
                                            event.target.value,
                                          )
                                        }
                                        className="w-32 rounded border px-1.5 py-1"
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
                                        onChange={(event) =>
                                          change(
                                            rowId,
                                            item,
                                            "conta_credito",
                                            event.target.value,
                                          )
                                        }
                                        className="w-32 rounded border px-1.5 py-1"
                                      />
                                    </td>
                                    <td className="px-3 py-1">
                                      <input
                                        list="catalogo-historicos"
                                        value={value(rowId, item, "historico")}
                                        onChange={(event) =>
                                          change(
                                            rowId,
                                            item,
                                            "historico",
                                            event.target.value,
                                          )
                                        }
                                        className="w-48 rounded border px-1.5 py-1"
                                      />
                                    </td>
                                    <td className="px-3 py-1">
                                      <button
                                        disabled={saving === rowId}
                                        onClick={() => save(row, item)}
                                        className="rounded border border-teal-700 px-2 py-1 text-teal-800"
                                      >
                                        Salvar
                                      </button>
                                    </td>
                                    <th className="px-3 py-2">Ação</th>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        ) : null}
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
  const [bank, setBank] = useState(initialBank || banks[0]),
    [start, setStart] = useState(""),
    [end, setEnd] = useState(""),
    [reconciliationId, setReconciliationId] = useState("");
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
    [resultsVersion, setResultsVersion] = useState(0);
  const resultRequest = useRef(0);
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const requestedProcess = params.get("process");
    const requestedBank = params.get("bank");
    const fallbackBank =
      requestedBank ||
      initialBank ||
      localStorage.getItem("conciliai_banco") ||
      banks[0];
    fetch(`${API}/api/clientes`)
      .then((r) => r.json())
      .then(setClients)
      .catch(() => setMessage("Backend indisponível."));
    setBank(fallbackBank);
    setClientId(
      params.get("client") ||
        initialClientId ||
        localStorage.getItem("conciliai_cliente_id") ||
        "",
    );
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
        if (!reconciliation)
          return setMessage("Este processo não possui bancos vinculados.");
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
    fetch(`${API}/api/conciliacoes/${reconciliationId}/revisao`)
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => {
        if (data) setReview(data);
      });
  }, [reconciliationId]);
  useEffect(() => {
    if (!message) return;
    const timeout = window.setTimeout(() => setMessage(""), 6000);
    return () => window.clearTimeout(timeout);
  }, [message]);
  useEffect(() => {
    if (
      !reconciliationId ||
      !["Conciliação", "Conciliação Avançada"].includes(activeTab)
    )
      return;
    const request = ++resultRequest.current;
    Promise.all([
      fetch(`${API}/api/conciliacoes/${reconciliationId}/resultado`).then(
        (response) => (response.ok ? response.json() : []),
      ),
      fetch(
        `${API}/api/conciliacoes/${reconciliationId}/documentos-nao-utilizados`,
      ).then((response) => (response.ok ? response.json() : null)),
    ]).then(([storedResults, storedUnused]) => {
      if (request !== resultRequest.current) return;
      setResults(Array.isArray(storedResults) ? storedResults : []);
      if (storedUnused) setUnused(storedUnused);
    });
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
    if (!processId || selectedBank === bank || isSwitchingBank) return;
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
            : "Comprovantes RFB";
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
  function downloadCsv() {
    if (!reconciliationId) return;
    window.location.assign(
      `${API}/api/conciliacoes/${reconciliationId}/lancamentos-contabeis.csv`,
    );
  }
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
      <main className="workspace-main mx-auto max-w-[90rem] px-3 py-3 sm:px-4">
        <div className="mb-5 flex justify-center overflow-x-auto border-b text-sm">
          {[
            "Início",
            ...(review.arquivos.length
              ? [
                  "Extrato",
                  "Comprovantes bancários",
                  "Comprovantes RFB",
                  "Conciliação",
                  "Conciliação Avançada",
                ]
              : []),
          ].map((item) => (
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
                  <span className="block text-xs text-slate-500">Banco</span>
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
                <button
                  onClick={createReconciliation}
                  className={`rounded-md px-4 py-2 font-medium text-white ${bank === "Banco do Brasil" ? "bg-amber-600" : bank === "Santander" || bank === "Bradesco" ? "bg-red-700" : bank === "BASA" ? "bg-lime-700" : bank === "Caixa" ? "bg-sky-700" : bank === "Conta Caixa" ? "bg-cyan-800" : "bg-emerald-800"}`}
                >
                  Iniciar conciliação
                </button>
              </div>
            </section>
            {reconciliationId && (
              <section className="my-6 grid gap-4 md:grid-cols-3">
                {[
                  ["extrato", "Extrato bancário", false],
                  ["comprovante", "Comprovantes bancários", true],
                  ["rfb", "Comprovantes da Receita Federal", true],
                ].map(([type, label, multiple]) => (
                  <label
                    className="cursor-pointer rounded-xl border-2 border-dashed border-slate-300 bg-white p-5 text-center hover:border-teal-600"
                    key={String(type)}
                  >
                    <Upload className="mx-auto mb-2 text-teal-700" />
                    <strong className="block">{String(label)}</strong>
                    <input
                      className="hidden"
                      type="file"
                      accept="application/pdf"
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
                      {file.tipo} · {file.status}
                    </span>
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
        {reconciliationId && activeTab === "Extrato" && (
          <Table
            title="Lançamentos do extrato"
            columns={["Data", "Hora", "Historico", "Valor", "Natureza"]}
            rows={review.extratos}
            onView={setViewer}
          />
        )}
        {reconciliationId && activeTab === "Comprovantes bancários" && (
          <Table
            title="Comprovantes bancários"
            columns={[
              "Data",
              "Hora",
              "Favorecido",
              "Valor original",
              "Ajustes",
              "Valor pago",
              "Tipo",
            ]}
            rows={review.comprovantes}
            onView={setViewer}
          />
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
        {reconciliationId && activeTab === "Conciliação Avançada" && (
          <div className="space-y-3">
            <AdvancedOverview
              reconciliationId={reconciliationId}
              version={rulesVersion}
            />
            <AdvancedRulesPanel
              reconciliationId={reconciliationId}
              onView={setViewer}
              onRulesChanged={() => setRulesVersion((version) => version + 1)}
            />
          </div>
        )}
        {reconciliationId && activeTab === "Conciliação" && (
          <div className="space-y-5">
            <section className="grid gap-4 md:grid-cols-3">
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
                <LegacyResultTable rows={results} onView={setViewer} />
                <section className="grid gap-3 md:grid-cols-2">
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
