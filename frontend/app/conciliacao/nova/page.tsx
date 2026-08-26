"use client";

import { ChangeEvent, FormEvent, ReactNode, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  Banknote,
  Building2,
  CalendarDays,
  Check,
  ClipboardList,
  Download,
  FileSpreadsheet,
  FileText,
  FolderOpen,
  LayoutDashboard,
  Loader2,
  PlayCircle,
  ReceiptText,
  RotateCcw,
  Save,
  UploadCloud,
  WandSparkles,
} from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Client = { id: string; nome: string };
type Reconciliation = { id: string; banco: string; status?: string };
type Process = { id: string; bancos: Reconciliation[] };
type UploadStatus = Record<string, { status: "uploading" | "done" | "error" | "processed"; message: string }>;
type Review = {
  extratos?: unknown[];
  comprovantes?: unknown[];
  maquininhas?: unknown[];
  emprestimos?: unknown[];
  notas?: unknown[];
  rfb?: unknown[];
  arquivos?: { id: string; nome: string; tipo: string; status: string; erro: string | null }[];
};
type RulesPayload = {
  pendentes?: unknown[];
  salvas?: unknown[];
  ignoradas?: unknown[];
  integridade?: { csv_permitido?: boolean };
};
type ResultRow = {
  data?: string;
  tipo_pagamento?: string;
  valor?: string;
  extrato?: string;
  situacao?: string;
  fonte_regra?: string;
  lancamentos?: unknown[];
};
type RuleForm = {
  gatilho: string;
  texto_exclusao: string;
  natureza: string;
  conta_debito: string;
  conta_credito: string;
  historico: string;
  complemento: string;
  tipo_componente: string;
};
type RulePreview = {
  quantidade: number;
  motivo?: string;
  lancamentos?: { data?: string; historico?: string; componente?: string; fonte?: string }[];
};

const steps = [
  { id: 1, title: "Cadastro", desc: "Cliente e período", icon: Building2 },
  { id: 2, title: "Definir banco", desc: "Bancos e áreas", icon: Banknote },
  { id: 3, title: "Upload", desc: "Arquivos por tipo", icon: UploadCloud },
  { id: 4, title: "Conciliação", desc: "Cruzamento", icon: PlayCircle },
  { id: 5, title: "Criar regras", desc: "Pendências", icon: WandSparkles },
  { id: 6, title: "Central de regras", desc: "Regras salvas", icon: ClipboardList },
  { id: 7, title: "Exportar CSV", desc: "Arquivos finais", icon: Download },
];

const bankOptions = [
  { name: "Banco do Brasil", code: "001", hint: "Extrato, comprovantes, RFB e empréstimos." },
  { name: "Santander", code: "033", hint: "Extrato, comprovantes, Getnet e financiamentos." },
  { name: "BASA", code: "021", hint: "Extrato e comprovantes do Banco da Amazônia." },
  { name: "Bradesco", code: "237", hint: "Extrato e comprovantes Bradesco." },
  { name: "Caixa", code: "104", hint: "Extrato, comprovantes e boletos Caixa." },
];

const supportOptions = [
  { name: "Notas", hint: "NFS-e e regras independentes de notas.", icon: ReceiptText },
  { name: "Conta Caixa", hint: "Movimentos em espécie fora do banco.", icon: Banknote },
  { name: "Apropriações", hint: "Lançamentos de provisão e ajustes.", icon: ClipboardList },
  { name: "Empréstimos/Financiamentos", hint: "Contratos, PDFs e planilhas de amortização.", icon: FileSpreadsheet },
];

const bankNames = bankOptions.map((bank) => bank.name);
const loanAccept = "application/pdf,.pdf,.xlsx,.xlsm,.csv,text/csv";

function uploadDocumentsFor(area: string, support: string[] = []) {
  if (bankNames.includes(area)) {
    const documents = [
      { type: "extrato", label: "Extrato", accept: "application/pdf,.pdf" },
      { type: "comprovante", label: "Comprovantes", accept: "application/pdf,.pdf", multiple: true },
      { type: "rfb", label: "Receita Federal", accept: "application/pdf,.pdf", multiple: true },
      { type: "maquininha_extrato", label: area === "Santander" ? "Extrato Getnet" : "Maquininhas", accept: "application/pdf,.pdf", multiple: true },
    ];
    if (support.includes("Notas")) documents.push({ type: "nota", label: "NFS-e", accept: "application/pdf,.pdf", multiple: true });
    if (support.includes("Empréstimos/Financiamentos")) documents.push({ type: "emprestimo", label: "Emprést./Fin.", accept: loanAccept, multiple: true });
    return documents;
  }
  return [];
}

function monthRange(start: string, end: string) {
  if (!start || !end) return "Período não definido";
  const startDate = new Date(`${start}T00:00:00`);
  const endDate = new Date(`${end}T00:00:00`);
  const label = startDate.toLocaleDateString("pt-BR", { month: "long", year: "numeric" });
  return `${label.charAt(0).toUpperCase()}${label.slice(1)} · ${startDate.toLocaleDateString("pt-BR")} a ${endDate.toLocaleDateString("pt-BR")}`;
}

function count(value: unknown[] | undefined) {
  return value?.length ?? 0;
}

export default function GuidedReconciliationPage() {
  const [clients, setClients] = useState<Client[]>([]);
  const [clientId, setClientId] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [selectedBanks, setSelectedBanks] = useState<string[]>(["Banco do Brasil"]);
  const [selectedSupport, setSelectedSupport] = useState<string[]>(["Notas", "Empréstimos/Financiamentos"]);
  const [process, setProcess] = useState<Process | null>(null);
  const [activeStep, setActiveStep] = useState(1);
  const [activeArea, setActiveArea] = useState("Banco do Brasil");
  const [cadTab, setCadTab] = useState("clientes");
  const [uploadTab, setUploadTab] = useState("extrato");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<UploadStatus>({});
  const [review, setReview] = useState<Review>({});
  const [rules, setRules] = useState<RulesPayload>({});
  const [results, setResults] = useState<ResultRow[]>([]);
  const [panelLoading, setPanelLoading] = useState(false);
  const [ruleForm, setRuleForm] = useState<RuleForm>({ gatilho: "", texto_exclusao: "", natureza: "Crédito", conta_debito: "", conta_credito: "", historico: "", complemento: "Conforme extrato bancário", tipo_componente: "PRINCIPAL" });
  const [rulePreview, setRulePreview] = useState<RulePreview | null>(null);
  const [ruleBusy, setRuleBusy] = useState("");
  const [editingRuleId, setEditingRuleId] = useState("");
  const [expandedRuleId, setExpandedRuleId] = useState("");

  useEffect(() => {
    fetch(`${API}/api/clientes`)
      .then((response) => {
        if (!response.ok) throw new Error();
        return response.json();
      })
      .then(setClients)
      .catch(() => setMessage("Não foi possível carregar os clientes."));
  }, []);

  const selectedClient = clients.find((client) => client.id === clientId);
  const selectedBlocks = useMemo(() => Array.from(new Set([...selectedBanks, ...selectedSupport])), [selectedBanks, selectedSupport]);
  const activeReconciliation = process?.bancos.find((item) => item.banco === activeArea) ?? process?.bancos[0] ?? null;
  const activeDocuments = uploadDocumentsFor(activeArea, selectedSupport);
  const activeUploadDocument = activeDocuments.find((item) => item.type === uploadTab) ?? activeDocuments[0];

  useEffect(() => {
    if (activeDocuments.length && !activeDocuments.some((item) => item.type === uploadTab)) setUploadTab(activeDocuments[0].type);
  }, [activeDocuments, uploadTab]);

  useEffect(() => {
    if (!activeReconciliation || ![4, 5, 6, 7].includes(activeStep)) return;
    let cancelled = false;
    setPanelLoading(true);
    Promise.all([
      fetch(`${API}/api/conciliacoes/${activeReconciliation.id}/revisao`, { cache: "no-store" }).then((response) => (response.ok ? response.json() : {})),
      fetch(`${API}/api/conciliacoes/${activeReconciliation.id}/resultado`, { cache: "no-store" }).then((response) => (response.ok ? response.json() : [])),
      fetch(`${API}/api/conciliacoes/${activeReconciliation.id}/regras-contabeis`, { cache: "no-store" }).then((response) => (response.ok ? response.json() : {})),
    ])
      .then(([nextReview, nextResults, nextRules]) => {
        if (cancelled) return;
        setReview(nextReview);
        setResults(Array.isArray(nextResults) ? nextResults : []);
        setRules(nextRules);
      })
      .catch(() => !cancelled && setMessage("Não foi possível atualizar os dados desta etapa."))
      .finally(() => !cancelled && setPanelLoading(false));
    return () => {
      cancelled = true;
    };
  }, [activeReconciliation, activeStep]);

  const toggle = (value: string, values: string[], setter: (next: string[]) => void) => {
    setter(values.includes(value) ? values.filter((item) => item !== value) : [...values, value]);
  };

  function selectBank(bank: string) {
    setSelectedBanks([bank]);
    setActiveArea(bank);
  }

  async function ensureProcess(event?: FormEvent | React.MouseEvent<HTMLButtonElement>) {
    event?.preventDefault();
    setMessage("");
    if (process) {
      setActiveStep(3);
      return;
    }
    if (!clientId || !start || !end) {
      setMessage("Informe cliente e período para continuar.");
      setActiveStep(1);
      return;
    }
    if (!selectedBanks.length) {
      setMessage("Selecione pelo menos um banco.");
      setActiveStep(2);
      return;
    }
    setLoading(true);
    try {
      const response = await fetch(`${API}/api/processos-conciliacao`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cliente_id: clientId, data_inicio: start, data_fim: end }),
      });
      if (!response.ok) throw new Error((await response.json()).detail ?? "Não foi possível criar o processo.");
      const created = (await response.json()) as Process;
      const reconciliations = await Promise.all(
        selectedBanks.map(async (area) => {
          const areaResponse = await fetch(`${API}/api/processos-conciliacao/${created.id}/bancos`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ banco: area }),
          });
          if (!areaResponse.ok) throw new Error((await areaResponse.json()).detail ?? `Não foi possível criar ${area}.`);
          return (await areaResponse.json()) as Reconciliation;
        }),
      );
      setProcess({ ...created, bancos: reconciliations });
      setActiveArea(reconciliations[0]?.banco ?? selectedBanks[0]);
      setActiveStep(3);
      setMessage("Processo criado. Envie os arquivos para continuar.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Não foi possível criar o processo.");
    } finally {
      setLoading(false);
    }
  }

  async function uploadFile(reconciliationId: string, type: string, event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (!files.length) return;
    const key = `${reconciliationId}:${type}`;
    setUploadStatus((current) => ({ ...current, [key]: { status: "uploading", message: `Enviando ${files.length} arquivo(s)...` } }));
    try {
      for (const file of files) {
        const body = new FormData();
        body.append("file", file);
        const response = await fetch(`${API}/api/conciliacoes/${reconciliationId}/arquivos?tipo_documento=${type}`, { method: "POST", body });
        if (!response.ok) throw new Error((await response.json()).detail ?? "Falha no envio.");
        const result = await response.json();
        if (result.status === "erro") throw new Error("Arquivo enviado, mas a extração retornou erro.");
      }
      setUploadStatus((current) => ({ ...current, [key]: { status: "done", message: `${files.length} arquivo(s) extraído(s).` } }));
      const reviewResponse = await fetch(`${API}/api/conciliacoes/${reconciliationId}/revisao`, { cache: "no-store" });
      if (reviewResponse.ok) setReview(await reviewResponse.json());
    } catch (error) {
      setUploadStatus((current) => ({ ...current, [key]: { status: "error", message: error instanceof Error ? error.message : "Falha no envio." } }));
    }
  }

  async function processActive() {
    if (!activeReconciliation) return;
    const key = `${activeReconciliation.id}:processar`;
    setUploadStatus((current) => ({ ...current, [key]: { status: "uploading", message: "Processando conciliação..." } }));
    try {
      const response = await fetch(`${API}/api/conciliacoes/${activeReconciliation.id}/conciliar`, { method: "POST" });
      if (!response.ok) throw new Error((await response.json()).detail ?? "Não foi possível processar.");
      setUploadStatus((current) => ({ ...current, [key]: { status: "processed", message: "Conciliação processada." } }));
      setActiveStep(4);
    } catch (error) {
      setUploadStatus((current) => ({ ...current, [key]: { status: "error", message: error instanceof Error ? error.message : "Não foi possível processar." } }));
    }
  }

  function selectPendingRule(raw: unknown) {
    const row = raw as Record<string, unknown>;
    const history = String(row.historico ?? row.gatilho_sugerido ?? "");
    setRulePreview(null);
    setRuleForm({
      gatilho: history,
      texto_exclusao: "",
      natureza: String(row.natureza_contabil ?? row.natureza ?? "Crédito"),
      conta_debito: "",
      conta_credito: "",
      historico: history,
      complemento: "Conforme extrato bancário",
      tipo_componente: String(row.tipo_componente ?? "PRINCIPAL"),
    });
  }

  function editSavedRule(raw: unknown) {
    const row = raw as Record<string, unknown>;
    setEditingRuleId(String(row.id ?? ""));
    setExpandedRuleId(String(row.id ?? ""));
    setRulePreview(null);
    setRuleForm({
      gatilho: String(row.gatilho ?? ""),
      texto_exclusao: String(row.texto_exclusao ?? ""),
      natureza: String(row.natureza ?? "Crédito"),
      conta_debito: String(row.conta_debito ?? ""),
      conta_credito: String(row.conta_credito ?? ""),
      historico: String(row.historico ?? ""),
      complemento: String(row.complemento ?? ""),
      tipo_componente: String(row.tipo_componente ?? "PRINCIPAL"),
    });
    setActiveStep(5);
  }

  function newGuidedRule() {
    setEditingRuleId("");
    setRulePreview(null);
    setRuleForm({ gatilho: "", texto_exclusao: "", natureza: "Crédito", conta_debito: "", conta_credito: "", historico: "", complemento: "Conforme extrato bancário", tipo_componente: "PRINCIPAL" });
    setActiveStep(5);
  }

  function updateRuleForm(next: Partial<RuleForm>) {
    setRulePreview(null);
    setRuleForm((current) => ({ ...current, ...next }));
  }

  async function calculateRuleCoverage(showMessage = true) {
    if (!activeReconciliation) return 0;
    if (!ruleForm.gatilho.trim()) {
      setRulePreview({ quantidade: 0, motivo: "Informe um gatilho para validar a regra.", lancamentos: [] });
      setMessage("Informe um gatilho para validar a regra.");
      return 0;
    }
    setRuleBusy("preview");
    try {
      const response = await fetch(`${API}/api/conciliacoes/${activeReconciliation.id}/regras-contabeis/previa`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          gatilho: ruleForm.gatilho,
          gatilho_comprovante: "",
          texto_exclusao: ruleForm.texto_exclusao,
          natureza: ruleForm.natureza,
          tipo_componente: ruleForm.tipo_componente,
          regra_id: editingRuleId,
        }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail ?? "Não foi possível calcular a cobertura.");
      setRulePreview(result);
      if (showMessage) setMessage(result.quantidade ? `Essa regra vai cobrir ${result.quantidade} lançamento(s).` : result.motivo || "Essa regra não cobre lançamentos elegíveis.");
      return Number(result.quantidade ?? 0);
    } catch (error) {
      setRulePreview({ quantidade: 0, motivo: error instanceof Error ? error.message : "Não foi possível calcular a cobertura.", lancamentos: [] });
      setMessage(error instanceof Error ? error.message : "Não foi possível calcular a cobertura.");
      return 0;
    } finally {
      setRuleBusy("");
    }
  }

  async function saveGuidedRule(event: FormEvent) {
    event.preventDefault();
    if (!activeReconciliation) return;
    const coverage = await calculateRuleCoverage(false);
    if (coverage <= 0) {
      setMessage("Essa regra não cobre nenhum lançamento elegível. Ajuste o gatilho antes de salvar.");
      return;
    }
    setMessage("Salvando regra...");
    setRuleBusy("save");
    try {
      const response = await fetch(`${API}/api/conciliacoes/${activeReconciliation.id}/regras-contabeis${editingRuleId ? `/${editingRuleId}` : ""}`, {
        method: editingRuleId ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(ruleForm),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.detail ?? "Não foi possível salvar a regra.");
      if (result.regras) setRules(result.regras);
      setRulePreview(null);
      setEditingRuleId("");
      setMessage(editingRuleId ? "Regra atualizada." : `Regra salva e aplicada a ${result.movimentos_aplicados ?? 0} lançamento(s).`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Não foi possível salvar a regra.");
    } finally {
      setRuleBusy("");
    }
  }

  async function refreshRules() {
    if (!activeReconciliation) return;
    const response = await fetch(`${API}/api/conciliacoes/${activeReconciliation.id}/regras-contabeis`, { cache: "no-store" });
    if (response.ok) setRules(await response.json());
  }

  async function removeRule(ruleId: string, scope: "periodo" | "global") {
    if (!activeReconciliation) return;
    setRuleBusy(ruleId);
    try {
      const response = await fetch(`${API}/api/conciliacoes/${activeReconciliation.id}/regras-contabeis/${ruleId}${scope === "periodo" ? "/periodo" : ""}`, { method: "DELETE" });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.detail ?? "Não foi possível remover a regra.");
      if (result.regras) setRules(result.regras);
      setMessage(result.message ?? "Regra removida.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Não foi possível remover a regra.");
    } finally {
      setRuleBusy("");
    }
  }

  async function restoreRule(ruleId: string) {
    if (!activeReconciliation) return;
    setRuleBusy(ruleId);
    try {
      const response = await fetch(`${API}/api/conciliacoes/${activeReconciliation.id}/regras-contabeis/${ruleId}/periodo/excecao`, { method: "DELETE" });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.detail ?? "Não foi possível restaurar a regra.");
      if (result.regras) setRules(result.regras);
      setMessage(result.message ?? "Regra restaurada.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Não foi possível restaurar a regra.");
    } finally {
      setRuleBusy("");
    }
  }

  async function restoreCoveredHiddenRules() {
    if (!activeReconciliation) return;
    setRuleBusy("restore-hidden");
    try {
      const response = await fetch(`${API}/api/conciliacoes/${activeReconciliation.id}/regras-contabeis/ocultas/restaurar-com-cobertura`, { method: "POST" });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.detail ?? "Não foi possível buscar regras existentes.");
      if (result.regras) setRules(result.regras);
      setMessage(result.message ?? "Busca concluída.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Não foi possível buscar regras existentes.");
    } finally {
      setRuleBusy("");
    }
  }

  const reconciled = results.filter((item) => item.situacao?.toLowerCase().includes("conciliado")).length;
  const pending = Math.max(results.length - reconciled, 0);
  const csvPermitted = rules.integridade?.csv_permitido !== false;
  const activeMeta = steps.find((step) => step.id === activeStep) ?? steps[0];

  return (
    <main className="min-h-screen bg-slate-100 text-slate-900">
      <div className="grid min-h-screen lg:grid-cols-[278px_1fr]">
        <aside className="hidden bg-slate-950 p-4 text-slate-200 lg:flex lg:flex-col">
          <Link href="/" className="mb-4 flex items-center gap-2 rounded-lg px-2 py-2 text-sm font-bold text-white">
            <span className="rounded-md bg-teal-600 p-1.5"><Building2 size={16} /></span>
            ConcilIA
          </Link>
          <div className="mb-4 rounded-lg border border-slate-800 bg-slate-900 p-3 text-xs">
            <span className="block font-semibold text-slate-400">Contexto ativo</span>
            <strong className="mt-1 block text-white">{selectedClient?.nome ?? "Selecione um cliente"}</strong>
            <span className="mt-1 block text-slate-400">{activeArea} · {monthRange(start, end)}</span>
          </div>
          <nav className="space-y-1 text-sm">
            <Link href="/" className="flex items-center gap-2 rounded-lg px-3 py-2 text-slate-300 hover:bg-slate-900"><LayoutDashboard size={16} />Central</Link>
            <Link href="/conciliacao" className="mb-3 flex items-center gap-2 rounded-lg px-3 py-2 text-slate-300 hover:bg-slate-900"><FolderOpen size={16} />Conciliação atual</Link>
            {steps.map((step) => {
              const Icon = step.icon;
              return (
                <button type="button" key={step.id} onClick={() => setActiveStep(step.id)} className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left ${activeStep === step.id ? "bg-teal-500 font-semibold text-slate-950" : "text-slate-300 hover:bg-slate-900"}`}>
                  <span className={`grid h-6 w-6 place-items-center rounded-full text-xs ${activeStep === step.id ? "bg-white" : "bg-slate-900 text-slate-400"}`}>{step.id}</span>
                  <Icon size={15} />
                  <span className="min-w-0"><span className="block">{step.title}</span><span className={`block text-[11px] ${activeStep === step.id ? "text-teal-950" : "text-slate-500"}`}>{step.desc}</span></span>
                </button>
              );
            })}
          </nav>
        </aside>

        <section className="min-w-0">
          <header className="border-b border-slate-200 bg-white px-5 py-4">
            <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-teal-700">Etapa {activeStep} de 7</p>
                <h1 className="text-xl font-bold">{activeMeta.title}</h1>
                <p className="text-sm text-slate-500">{activeMeta.desc}</p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {process && (
                  <select value={activeArea} onChange={(event) => setActiveArea(event.target.value)} className="rounded-md border border-slate-300 px-3 py-2 text-sm font-semibold">
                    {process.bancos.map((item) => <option value={item.banco} key={item.id}>{item.banco}</option>)}
                  </select>
                )}
                <Link href="/" className="inline-flex items-center gap-2 rounded-md border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"><RotateCcw size={16} />Voltar</Link>
              </div>
            </div>
          </header>

          <div className="mx-auto max-w-7xl space-y-4 px-5 py-5">
            {message && <p className="rounded-md bg-teal-50 px-3 py-2 text-sm font-semibold text-teal-800">{message}</p>}

            {activeStep === 1 && (
              <form onSubmit={(event) => { event.preventDefault(); setActiveStep(2); }} className="grid gap-4 xl:grid-cols-[1fr_360px]">
                <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                  <div className="mb-4 flex items-center gap-2 text-teal-800"><Building2 size={18} /><h2 className="font-bold">Cadastro</h2></div>
                  <div className="mb-4 flex flex-wrap gap-2">
                    {["clientes", "bancos", "plano", "historico"].map((tab) => (
                      <button type="button" key={tab} onClick={() => setCadTab(tab)} className={`rounded-full border px-4 py-2 text-xs font-bold capitalize ${cadTab === tab ? "border-slate-900 bg-slate-900 text-white" : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"}`}>{tab}</button>
                    ))}
                  </div>
                  {cadTab === "clientes" && (
                    <div className="space-y-4">
                      <div className="grid gap-3 md:grid-cols-[1fr_180px_180px]">
                        <label className="text-sm font-semibold">Cliente
                          <select required value={clientId} onChange={(event) => setClientId(event.target.value)} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 font-normal">
                            <option value="">Selecionar cliente</option>
                            {clients.map((client) => <option value={client.id} key={client.id}>{client.nome}</option>)}
                          </select>
                        </label>
                        <label className="text-sm font-semibold">Início
                          <input required type="date" value={start} onChange={(event) => setStart(event.target.value)} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 font-normal" />
                        </label>
                        <label className="text-sm font-semibold">Fim
                          <input required type="date" value={end} onChange={(event) => setEnd(event.target.value)} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 font-normal" />
                        </label>
                      </div>
                      <div className="rounded-lg border border-slate-200">
                        <table className="w-full text-sm">
                          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-3 py-2">Razão social</th><th className="px-3 py-2">Status</th></tr></thead>
                          <tbody>{clients.slice(0, 8).map((client) => <tr className="border-t" key={client.id}><td className="px-3 py-2">{client.nome}</td><td className="px-3 py-2"><span className="rounded bg-teal-100 px-2 py-1 text-xs font-bold text-teal-800">Ativo</span></td></tr>)}</tbody>
                        </table>
                      </div>
                    </div>
                  )}
                  {cadTab === "bancos" && <CadastroTable rows={bankOptions.map((bank) => [bank.code, bank.name, bank.hint])} headers={["Código", "Banco", "Documentos"]} />}
                  {cadTab === "plano" && <CadastroTable rows={[["219", "Banco Brasil"], ["232", "Clientes Diversos"], ["258", "Leandro Barbosa Figueiro"], ["387", "Anuidades"]]} headers={["Código", "Conta"]} />}
                  {cadTab === "historico" && <CadastroTable rows={[["52", "Tarifa Bancária"], ["307", "Pagto. de Duplic. Fornecedor"], ["310", "Transferência entre contas"], ["467", "Recebimento via PIX conforme extrato."]]} headers={["Código", "Histórico"]} />}
                  <div className="mt-4 flex justify-end">
                    <button className="inline-flex items-center gap-2 rounded-md bg-teal-700 px-4 py-2 text-sm font-bold text-white hover:bg-teal-800">Próxima etapa<ArrowRight size={16} /></button>
                  </div>
                </section>
                <SummaryCard selectedClient={selectedClient} start={start} end={end} selectedAreas={selectedBlocks} />
              </form>
            )}

            {activeStep === 2 && (
              <section className="grid gap-4 xl:grid-cols-[1fr_360px]">
                <div className="space-y-4">
                  <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                    <div className="mb-4 flex items-center gap-2 text-teal-800"><Banknote size={18} /><h2 className="font-bold">Bancos</h2></div>
                    <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-5">
                      {bankOptions.map((bank) => {
                        const active = selectedBanks.includes(bank.name);
                        return (
                          <button type="button" onClick={() => selectBank(bank.name)} className={`rounded-lg border p-3 text-left ${active ? "border-teal-600 bg-teal-50" : "border-slate-200 bg-white hover:border-slate-300"}`} key={bank.name}>
                            <span className="flex items-center justify-between gap-2 text-xs font-mono text-slate-500">{bank.code}{active && <Check size={14} className="text-teal-700" />}</span>
                            <strong className="mt-1 block text-sm">{bank.name}</strong>
                            <span className="mt-1 block text-xs text-slate-500">{bank.hint}</span>
                          </button>
                        );
                      })}
                    </div>
                  </section>
                  <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                    <div className="mb-4 flex items-center gap-2 text-teal-800"><FileText size={18} /><h2 className="font-bold">Áreas auxiliares</h2></div>
                    <div className="grid gap-2 md:grid-cols-2">
                      {supportOptions.map((option) => {
                        const Icon = option.icon;
                        const active = selectedSupport.includes(option.name);
                        return (
                          <button type="button" onClick={() => toggle(option.name, selectedSupport, setSelectedSupport)} className={`flex items-start gap-3 rounded-lg border p-3 text-left ${active ? "border-teal-600 bg-teal-50" : "border-slate-200 bg-white hover:border-slate-300"}`} key={option.name}>
                            <Icon size={17} className={active ? "text-teal-700" : "text-slate-500"} />
                            <span><strong className="block text-sm">{option.name}</strong><span className="text-xs text-slate-500">{option.hint}</span></span>
                          </button>
                        );
                      })}
                    </div>
                  </section>
                  <div className="flex justify-end">
                    <button disabled={loading} onClick={ensureProcess} className="inline-flex items-center gap-2 rounded-md bg-teal-700 px-4 py-2 text-sm font-bold text-white hover:bg-teal-800 disabled:cursor-wait disabled:opacity-70">
                      {loading ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
                      Criar processo e ir para upload
                    </button>
                  </div>
                </div>
                <SummaryCard selectedClient={selectedClient} start={start} end={end} selectedAreas={selectedBlocks} />
              </section>
            )}

            {activeStep === 3 && (
              <GuidedPanel title="Upload de arquivos" action={<button onClick={processActive} disabled={!activeReconciliation || uploadStatus[`${activeReconciliation.id}:processar`]?.status === "uploading"} className="inline-flex items-center gap-2 rounded-md bg-slate-900 px-3 py-2 text-sm font-bold text-white hover:bg-slate-800 disabled:cursor-wait disabled:opacity-70"><PlayCircle size={15} />Processar</button>}>
                {!process ? (
                  <EmptyAction text="Crie o processo antes de enviar arquivos." onClick={() => setActiveStep(1)} />
                ) : (
                  <div>
                    <div className="mb-4 flex flex-wrap gap-2">
                      {activeDocuments.map((doc) => (
                        <button type="button" key={doc.type} onClick={() => setUploadTab(doc.type)} className={`rounded-full border px-4 py-2 text-xs font-bold ${uploadTab === doc.type ? "border-slate-900 bg-slate-900 text-white" : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"}`}>{doc.label}</button>
                      ))}
                    </div>
                    {activeUploadDocument ? (() => {
                      const doc = activeUploadDocument;
                      const key = `${activeReconciliation?.id}:${doc.type}`;
                      const status = uploadStatus[key];
                      const busy = status?.status === "uploading";
                      return (
                        <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center">
                          <UploadCloud className="mx-auto text-teal-700" size={28} />
                          <h3 className="mt-3 text-base font-bold">{doc.label} — {activeArea}</h3>
                          <p className="mt-1 text-sm text-slate-500">{doc.accept.includes("xlsx") ? "PDF, XLSX ou CSV" : "PDF"}{doc.multiple ? " · múltiplos arquivos" : ""}</p>
                          <label className={`mt-4 inline-flex cursor-pointer items-center gap-2 rounded-md px-4 py-2 text-sm font-bold ${busy ? "bg-slate-300 text-slate-600" : "bg-teal-700 text-white hover:bg-teal-800"}`}>
                            {busy ? <Loader2 size={15} className="animate-spin" /> : <UploadCloud size={15} />}
                            Selecionar arquivo
                            <input type="file" className="hidden" accept={doc.accept} multiple={doc.multiple} disabled={busy || !activeReconciliation} onChange={(event) => activeReconciliation && uploadFile(activeReconciliation.id, doc.type, event)} />
                          </label>
                          {status && <p className={`mt-3 text-xs font-semibold ${status.status === "error" ? "text-red-700" : "text-teal-700"}`}>{status.message}</p>}
                          <div className="mt-5 rounded-lg border border-slate-200 bg-white text-left">
                            {(review.arquivos ?? []).filter((file) => file.tipo === doc.type).slice(0, 8).map((file) => (
                              <div className="flex items-center justify-between gap-3 border-b border-slate-100 px-3 py-2 last:border-b-0" key={file.id}>
                                <span className="min-w-0 truncate text-xs font-semibold">{file.nome}</span>
                                <span className={`rounded px-2 py-1 text-[11px] font-bold ${file.status === "concluido" ? "bg-teal-100 text-teal-800" : file.status === "erro" ? "bg-red-100 text-red-700" : "bg-amber-100 text-amber-800"}`}>{file.status}</span>
                              </div>
                            ))}
                            {!(review.arquivos ?? []).some((file) => file.tipo === doc.type) && <p className="px-3 py-3 text-xs text-slate-500">Nenhum arquivo enviado nesta aba.</p>}
                          </div>
                        </div>
                      );
                    })() : <EmptyAction text="Selecione documentos auxiliares na etapa de definição." onClick={() => setActiveStep(2)} />}
                  </div>
                )}
              </GuidedPanel>
            )}

            {activeStep === 4 && (
              <GuidedPanel title="Conciliação" loading={panelLoading} action={<button onClick={processActive} disabled={!activeReconciliation} className="inline-flex items-center gap-2 rounded-md bg-teal-700 px-3 py-2 text-sm font-bold text-white hover:bg-teal-800 disabled:opacity-60"><PlayCircle size={15} />Reprocessar</button>}>
                <StatsGrid items={[["Extrato", count(review.extratos)], ["Comprovantes", count(review.comprovantes)], ["RFB", count(review.rfb)], ["Resultados", results.length]]} />
                <MiniTable rows={results.slice(0, 12)} />
              </GuidedPanel>
            )}

            {activeStep === 5 && (
              <GuidedPanel title="Criar regras" loading={panelLoading} action={<button onClick={() => setActiveStep(6)} className="inline-flex items-center gap-2 rounded-md bg-teal-700 px-3 py-2 text-sm font-bold text-white hover:bg-teal-800"><WandSparkles size={15} />Ver regras salvas</button>}>
                <StatsGrid items={[["Regras a criar", count(rules.pendentes)], ["Ocultas", count(rules.ignoradas)], ["Salvas", count(rules.salvas)]]} />
                <div className="grid gap-4 xl:grid-cols-[1fr_420px]">
                  <PendingRules rows={rules.pendentes ?? []} onSelect={selectPendingRule} />
                  <form onSubmit={saveGuidedRule} className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                    <div className="flex items-center justify-between gap-2">
                      <h3 className="font-bold">{editingRuleId ? "Editar regra" : "Nova regra"}</h3>
                      {editingRuleId && <button type="button" onClick={newGuidedRule} className="rounded border border-slate-200 bg-white px-2 py-1 text-xs font-bold text-slate-700">Cancelar edição</button>}
                    </div>
                    <div className="mt-3 grid gap-3">
                      <label className="text-xs font-bold text-slate-600">Gatilho<input required value={ruleForm.gatilho} onChange={(event) => updateRuleForm({ gatilho: event.target.value })} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm font-normal" /></label>
                      <label className="text-xs font-bold text-slate-600">Não contém<input value={ruleForm.texto_exclusao} onChange={(event) => updateRuleForm({ texto_exclusao: event.target.value })} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm font-normal" /></label>
                      <div className="grid gap-3 md:grid-cols-2">
                        <label className="text-xs font-bold text-slate-600">Natureza<select value={ruleForm.natureza} onChange={(event) => updateRuleForm({ natureza: event.target.value })} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm font-normal"><option>Crédito</option><option>Débito</option></select></label>
                        <label className="text-xs font-bold text-slate-600">Tipo<input value={ruleForm.tipo_componente} onChange={(event) => updateRuleForm({ tipo_componente: event.target.value })} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm font-normal" /></label>
                      </div>
                      <div className="grid gap-3 md:grid-cols-2">
                        <label className="text-xs font-bold text-slate-600">Débito<input required value={ruleForm.conta_debito} onChange={(event) => updateRuleForm({ conta_debito: event.target.value })} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm font-normal" /></label>
                        <label className="text-xs font-bold text-slate-600">Crédito<input required value={ruleForm.conta_credito} onChange={(event) => updateRuleForm({ conta_credito: event.target.value })} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm font-normal" /></label>
                      </div>
                      <label className="text-xs font-bold text-slate-600">Histórico<input required value={ruleForm.historico} onChange={(event) => updateRuleForm({ historico: event.target.value })} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm font-normal" /></label>
                      <label className="text-xs font-bold text-slate-600">Complemento<input value={ruleForm.complemento} onChange={(event) => updateRuleForm({ complemento: event.target.value })} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm font-normal" /></label>
                      <div className="rounded-lg border border-slate-200 bg-white p-3">
                        <div className="flex items-center justify-between gap-3">
                          <strong className="text-sm">Cobertura</strong>
                          <button type="button" disabled={ruleBusy === "preview"} onClick={() => calculateRuleCoverage()} className="rounded bg-slate-900 px-3 py-1.5 text-xs font-bold text-white disabled:cursor-wait disabled:opacity-60">{ruleBusy === "preview" ? "Validando..." : "Ver cobertura"}</button>
                        </div>
                        {rulePreview ? (
                          <div className="mt-3">
                            <p className={`text-xs font-bold ${rulePreview.quantidade > 0 ? "text-teal-700" : "text-red-700"}`}>
                              {rulePreview.quantidade > 0 ? `Vai cobrir ${rulePreview.quantidade} lançamento(s).` : rulePreview.motivo || "Não cobre lançamentos elegíveis."}
                            </p>
                            {!!rulePreview.lancamentos?.length && (
                              <div className="mt-2 max-h-36 overflow-y-auto rounded border border-slate-100">
                                {rulePreview.lancamentos.slice(0, 8).map((item, index) => (
                                  <div className="border-b border-slate-100 px-2 py-1.5 text-[11px] last:border-b-0" key={index}>
                                    <strong>{item.data ?? "—"}</strong> · {item.historico ?? "—"} · {item.componente ?? "PRINCIPAL"}
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        ) : <p className="mt-2 text-xs text-slate-500">Valide antes de salvar.</p>}
                      </div>
                      <button disabled={ruleBusy === "save"} className="inline-flex items-center justify-center gap-2 rounded-md bg-teal-700 px-4 py-2 text-sm font-bold text-white hover:bg-teal-800 disabled:cursor-wait disabled:opacity-60">{ruleBusy === "save" ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />}{editingRuleId ? "Atualizar regra" : "Salvar regra"}</button>
                    </div>
                  </form>
                </div>
              </GuidedPanel>
            )}

            {activeStep === 6 && (
              <GuidedPanel title="Central de regras" loading={panelLoading} action={<div className="flex flex-wrap gap-2"><button onClick={refreshRules} className="rounded-md border border-slate-200 px-3 py-2 text-sm font-bold text-slate-700 hover:bg-slate-50">Atualizar</button><button onClick={restoreCoveredHiddenRules} disabled={ruleBusy === "restore-hidden"} className="rounded-md border border-violet-200 bg-violet-50 px-3 py-2 text-sm font-bold text-violet-800 disabled:opacity-60">{ruleBusy === "restore-hidden" ? "Buscando..." : "Buscar ocultas"}</button><button onClick={() => setActiveStep(7)} className="inline-flex items-center gap-2 rounded-md border border-slate-200 px-3 py-2 text-sm font-bold text-slate-700 hover:bg-slate-50"><Download size={15} />Exportar</button></div>}>
                <StatsGrid items={[["Regras salvas", count(rules.salvas)], ["Regras ocultas", count(rules.ignoradas)], ["Pendentes", count(rules.pendentes)]]} />
                <SavedRules rows={rules.salvas ?? []} expandedRuleId={expandedRuleId} busyId={ruleBusy} onToggle={setExpandedRuleId} onEdit={editSavedRule} onRemovePeriod={(id) => removeRule(id, "periodo")} onRemoveGlobal={(id) => removeRule(id, "global")} />
                <HiddenRules rows={rules.ignoradas ?? []} busyId={ruleBusy} onRestore={restoreRule} />
              </GuidedPanel>
            )}

            {activeStep === 7 && (
              <GuidedPanel title="Exportar CSV" loading={panelLoading}>
                <StatsGrid items={[["Conciliados", reconciled], ["Pendentes", pending], ["Linhas", results.length]]} />
                <div className="grid gap-3 md:grid-cols-2">
                  <ExportCard label="Lançamentos contábeis CSV" href={activeReconciliation && csvPermitted ? `${API}/api/conciliacoes/${activeReconciliation.id}/lancamentos-contabeis.csv` : ""} blocked={!csvPermitted} />
                  <ExportCard label="Relatório PDF" href={activeReconciliation && csvPermitted ? `${API}/api/conciliacoes/${activeReconciliation.id}/lancamentos-contabeis.pdf` : ""} blocked={!csvPermitted} />
                </div>
              </GuidedPanel>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}

function SummaryCard({ selectedClient, start, end, selectedAreas }: { selectedClient?: Client; start: string; end: string; selectedAreas: string[] }) {
  return (
    <aside className="rounded-xl border border-teal-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center gap-2 text-teal-800"><CalendarDays size={18} /><h2 className="font-bold">Resumo</h2></div>
      <dl className="space-y-3 text-sm">
        <div><dt className="text-xs font-semibold uppercase tracking-wide text-slate-400">Cliente</dt><dd className="mt-0.5 font-medium">{selectedClient?.nome ?? "Selecione um cliente"}</dd></div>
        <div><dt className="text-xs font-semibold uppercase tracking-wide text-slate-400">Período</dt><dd className="mt-0.5 font-medium">{monthRange(start, end)}</dd></div>
        <div><dt className="text-xs font-semibold uppercase tracking-wide text-slate-400">Blocos</dt><dd className="mt-1 flex flex-wrap gap-1">{selectedAreas.map((area) => <span className="rounded bg-slate-100 px-2 py-1 text-xs font-semibold" key={area}>{area}</span>)}</dd></div>
      </dl>
    </aside>
  );
}

function GuidedPanel({ title, action, loading, children }: { title: string; action?: ReactNode; loading?: boolean; children: ReactNode }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-bold">{title}</h2>
        <div className="flex items-center gap-2">{loading && <Loader2 size={16} className="animate-spin text-slate-500" />}{action}</div>
      </div>
      {children}
    </section>
  );
}

function EmptyAction({ text, onClick, href }: { text: string; onClick?: () => void; href?: string }) {
  const className = "inline-flex items-center gap-2 rounded-md bg-teal-700 px-3 py-2 text-sm font-bold text-white hover:bg-teal-800";
  return (
    <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-5 text-center text-sm text-slate-600">
      <p className="mb-3 font-semibold">{text}</p>
      {href ? <Link href={href} className={className}><FolderOpen size={15} />Abrir</Link> : <button onClick={onClick} className={className}>Começar</button>}
    </div>
  );
}

function StatsGrid({ items }: { items: [string, number][] }) {
  return (
    <div className="mb-4 grid gap-3 md:grid-cols-3 xl:grid-cols-4">
      {items.map(([label, value]) => (
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-3" key={label}>
          <div className="text-2xl font-bold text-slate-900">{value}</div>
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</div>
        </div>
      ))}
    </div>
  );
}

function CadastroTable({ headers, rows }: { headers: string[]; rows: string[][] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200">
      <table className="min-w-full text-sm">
        <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
          <tr>{headers.map((header) => <th className="px-3 py-2" key={header}>{header}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, index) => <tr className="border-t border-slate-100" key={index}>{row.map((cell, cellIndex) => <td className="px-3 py-2" key={cellIndex}>{cell}</td>)}</tr>)}
        </tbody>
      </table>
    </div>
  );
}

function MiniTable({ rows }: { rows: ResultRow[] }) {
  if (!rows.length) return <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">Nenhum resultado processado ainda.</div>;
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200">
      <table className="min-w-full text-sm">
        <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
          <tr><th className="px-3 py-2">Data</th><th className="px-3 py-2">Tipo</th><th className="px-3 py-2">Extrato</th><th className="px-3 py-2">Valor</th><th className="px-3 py-2">Situação</th><th className="px-3 py-2">Regra</th></tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr className="border-t border-slate-100" key={index}>
              <td className="whitespace-nowrap px-3 py-2 font-mono text-xs">{row.data ?? "—"}</td>
              <td className="px-3 py-2">{row.tipo_pagamento ?? "—"}</td>
              <td className="max-w-[460px] px-3 py-2 text-xs text-slate-600">{String(row.extrato ?? "—").split("\n").slice(0, 2).join(" · ")}</td>
              <td className="whitespace-nowrap px-3 py-2 font-semibold">{row.valor ?? "—"}</td>
              <td className="px-3 py-2 font-semibold">{row.situacao ?? "—"}</td>
              <td className="px-3 py-2">{row.fonte_regra ?? "—"} · {row.lancamentos?.length ?? 0} linha(s)</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PendingRules({ rows, onSelect }: { rows: unknown[]; onSelect: (row: unknown) => void }) {
  if (!rows.length) return <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">Nenhuma regra pendente para este banco.</div>;
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200">
      <table className="min-w-full text-sm">
        <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
          <tr><th className="px-3 py-2">Histórico</th><th className="px-3 py-2">Valor</th><th className="px-3 py-2">Tipo</th><th className="px-3 py-2">Ação</th></tr>
        </thead>
        <tbody>
          {rows.slice(0, 12).map((raw, index) => {
            const row = raw as Record<string, unknown>;
            return (
              <tr className="border-t border-slate-100" key={String(row.id ?? index)}>
                <td className="max-w-[520px] px-3 py-2 text-xs font-semibold text-slate-700">{String(row.historico ?? row.gatilho ?? "—")}</td>
                <td className="whitespace-nowrap px-3 py-2">{String(row.valor ?? "—")}</td>
                <td className="px-3 py-2">{String(row.tipo_componente ?? "Principal")}</td>
                <td className="px-3 py-2"><button type="button" onClick={() => onSelect(raw)} className="rounded bg-amber-100 px-2 py-1 text-xs font-bold text-amber-900 hover:bg-amber-200">Criar regra</button></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function SavedRules({
  rows,
  expandedRuleId,
  busyId,
  onToggle,
  onEdit,
  onRemovePeriod,
  onRemoveGlobal,
}: {
  rows: unknown[];
  expandedRuleId: string;
  busyId: string;
  onToggle: (id: string) => void;
  onEdit: (row: unknown) => void;
  onRemovePeriod: (id: string) => void;
  onRemoveGlobal: (id: string) => void;
}) {
  if (!rows.length) return <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">Nenhuma regra salva para este banco.</div>;
  return (
    <div className="space-y-2">
      {rows.map((raw, index) => {
        const row = raw as Record<string, unknown>;
        const id = String(row.id ?? index);
        const movements = Array.isArray(row.movimentos) ? row.movimentos as Record<string, unknown>[] : [];
        const expanded = expandedRuleId === id;
        return (
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-3" key={id}>
            <div className="flex items-start justify-between gap-2">
              <strong className="text-sm">{String(row.gatilho ?? row.historico ?? "Regra")}</strong>
              <span className="rounded bg-teal-100 px-2 py-1 text-xs font-bold text-teal-800">{String(row.cobertos ?? 0)} cobertos</span>
            </div>
            <p className="mt-1 text-xs text-slate-600">{String(row.conta_debito ?? "—")} → {String(row.conta_credito ?? "—")}</p>
            <p className="mt-1 text-xs text-slate-500">{String(row.historico ?? "—")}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <button type="button" onClick={() => onToggle(expanded ? "" : id)} className="rounded border border-slate-200 bg-white px-2 py-1 text-xs font-bold text-slate-700">{expanded ? "Ocultar" : "Ver"}</button>
              <button type="button" onClick={() => onEdit(raw)} className="rounded bg-slate-900 px-2 py-1 text-xs font-bold text-white">Editar</button>
              <button type="button" disabled={busyId === id} onClick={() => onRemovePeriod(id)} className="rounded border border-violet-200 bg-violet-50 px-2 py-1 text-xs font-bold text-violet-800 disabled:opacity-60">{busyId === id ? "Removendo..." : "Remover período"}</button>
              <button type="button" disabled={busyId === id} onClick={() => onRemoveGlobal(id)} className="rounded border border-red-200 bg-red-50 px-2 py-1 text-xs font-bold text-red-700 disabled:opacity-60">{busyId === id ? "Excluindo..." : "Excluir geral"}</button>
            </div>
            {expanded && (
              <div className="mt-3 rounded border border-slate-200 bg-white">
                {movements.length ? movements.slice(0, 10).map((movement, movementIndex) => (
                  <div className="border-b border-slate-100 px-3 py-2 text-xs last:border-b-0" key={movementIndex}>
                    <strong>{String(movement.data ?? "—")}</strong> · {String(movement.historico ?? movement.texto_extrato ?? "—")} · {String(movement.valor ?? "—")}
                  </div>
                )) : <p className="px-3 py-3 text-xs text-slate-500">Sem lançamentos cobertos neste período.</p>}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function HiddenRules({ rows, busyId, onRestore }: { rows: unknown[]; busyId: string; onRestore: (id: string) => void }) {
  if (!rows.length) return null;
  return (
    <section className="mt-4 rounded-lg border border-violet-200 bg-violet-50 p-3">
      <h3 className="text-sm font-bold text-violet-950">Regras ocultas</h3>
      <div className="mt-2 space-y-2">
        {rows.map((raw, index) => {
          const row = raw as Record<string, unknown>;
          const id = String(row.id ?? index);
          return (
            <div className="flex items-center justify-between gap-3 rounded border border-violet-100 bg-white px-3 py-2 text-xs" key={id}>
              <span className="min-w-0 truncate"><strong>{String(row.gatilho ?? row.historico ?? "Regra")}</strong> · {String(row.tipo_componente ?? "Principal")}</span>
              <button type="button" disabled={busyId === id} onClick={() => onRestore(id)} className="rounded bg-violet-700 px-2 py-1 font-bold text-white disabled:opacity-60">{busyId === id ? "Restaurando..." : "Restaurar"}</button>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function ExportCard({ label, href, blocked }: { label: string; href: string; blocked?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 bg-slate-50 p-4">
      <div className="flex items-center gap-3">
        <span className="rounded-md bg-teal-100 p-2 text-teal-800"><FileText size={17} /></span>
        <strong className="text-sm">{label}</strong>
      </div>
      {blocked || !href ? <span className="rounded bg-slate-200 px-3 py-2 text-xs font-bold text-slate-500">Bloqueado</span> : <a href={href} className="inline-flex items-center gap-1 rounded-md bg-teal-700 px-3 py-2 text-xs font-bold text-white hover:bg-teal-800"><Download size={14} />Baixar</a>}
    </div>
  );
}
