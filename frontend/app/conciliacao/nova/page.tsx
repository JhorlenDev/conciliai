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
  Eye,
  FileSpreadsheet,
  FileText,
  FolderOpen,
  LayoutDashboard,
  Loader2,
  PlayCircle,
  RotateCcw,
  Save,
  Trash2,
  UploadCloud,
  WandSparkles,
  X,
} from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Client = { id: string; nome: string };
type BankProgress = { total: number; cobertos: number; percentual: number };
type Reconciliation = { id: string; banco: string; status?: string; progresso_regras?: BankProgress };
type Process = { id: string; cliente_id?: string; cliente_nome?: string; data_inicio?: string; data_fim?: string; bancos: Reconciliation[] };
type UploadStatus = Record<string, { status: "uploading" | "done" | "error" | "processed"; message: string }>;
type Viewer = { arquivoId: string; pagina: number; titulo: string };
type Review = {
  extratos?: unknown[];
  comprovantes?: unknown[];
  maquininhas?: unknown[];
  emprestimos?: unknown[];
  folhas?: unknown[];
  notas?: unknown[];
  rfb?: unknown[];
  arquivos?: { id: string; nome: string; tipo: string; status: string; erro: string | null }[];
};
type RulesPayload = {
  pendentes?: unknown[];
  classificados?: unknown[];
  salvas?: unknown[];
  ignoradas?: unknown[];
  resumo?: { total?: number; classificados?: number; pendentes?: number };
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
  extrato_arquivo_id?: string | null;
  extrato_pagina?: number | null;
  comprovante_arquivo_id?: string | null;
  comprovante_pagina?: number | null;
  rfb_arquivo_id?: string | null;
  rfb_pagina?: number | null;
};
type RuleForm = {
  gatilho: string;
  gatilho_comprovante: string;
  texto_exclusao: string;
  natureza: string;
  conta_debito: string;
  conta_credito: string;
  historico: string;
  complemento: string;
  tipo_componente: string;
  aplicar_existentes: boolean;
};
type RulePreview = {
  quantidade: number;
  motivo?: string;
  lancamentos?: { data?: string; historico?: string; componente?: string; fonte?: string }[];
};
type RuleSuggestion = { id: string; label: string; value: string; target: "extrato" | "comprovante" | "exclusao" };
type FlowType = "bancos" | "notas" | "despesas" | "folha";

const defaultRuleForm: RuleForm = { gatilho: "", gatilho_comprovante: "", texto_exclusao: "", natureza: "Crédito", conta_debito: "", conta_credito: "", historico: "", complemento: "Conforme extrato bancário", tipo_componente: "PRINCIPAL", aplicar_existentes: true };

const flowConfigs: Record<FlowType, { title: string; area: string; support: string[]; step2: string; step2Desc: string; summary: string }> = {
  bancos: {
    title: "Conciliador de Bancos",
    area: "Banco do Brasil",
    support: ["Conta Caixa", "Apropriações", "Empréstimos/Financiamentos"],
    step2: "Definir banco",
    step2Desc: "Bancos e áreas",
    summary: "Extratos, comprovantes, RFB, maquininhas e financiamentos por banco.",
  },
  notas: {
    title: "Conciliador de Notas",
    area: "Notas",
    support: [],
    step2: "Notas fiscais",
    step2Desc: "Upload e regras de NFS-e",
    summary: "Notas extraídas, regras próprias e CSV independente.",
  },
  despesas: {
    title: "Conciliador de Despesas Gerais",
    area: "Apropriações",
    support: [],
    step2: "Despesas gerais",
    step2Desc: "Documentos avulsos e regras",
    summary: "Documentos gerais fora do fluxo bancário, com regras e exportação próprios.",
  },
  folha: {
    title: "Conciliador de Folha de Pagamento",
    area: "Folha de Pagamento",
    support: [],
    step2: "Folha de pagamento",
    step2Desc: "Relatórios e regras",
    summary: "Relatórios de folha com conferência, regras próprias e exportação separada.",
  },
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
  { name: "Banco do Brasil", code: "001", hint: "Extrato, comprovantes, RFB e empréstimos.", logo: "/bancos/banco-do-brasil.png" },
  { name: "Santander", code: "033", hint: "Extrato, comprovantes, Getnet e financiamentos.", logo: "/bancos/santander.png" },
  { name: "BASA", code: "021", hint: "Extrato e comprovantes do Banco da Amazônia.", logo: "/bancos/basa.png" },
  { name: "Bradesco", code: "237", hint: "Extrato e comprovantes Bradesco.", logo: "/bancos/bradesco.png" },
  { name: "Caixa", code: "104", hint: "Extrato, comprovantes e boletos Caixa.", logo: "/bancos/caixa.png" },
];

const supportOptions = [
  { name: "Conta Caixa", hint: "Movimentos em espécie fora do banco.", icon: Banknote },
  { name: "Apropriações", hint: "Lançamentos de provisão e ajustes.", icon: ClipboardList },
  { name: "Empréstimos/Financiamentos", hint: "Contratos, PDFs e planilhas de amortização.", icon: FileSpreadsheet },
  { name: "Folha de Pagamento", hint: "Líquido da folha para conciliar com o banco.", icon: FileSpreadsheet },
];

const bankNames = bankOptions.map((bank) => bank.name);
const loanAccept = "application/pdf,.pdf,.xlsx,.xlsm,.csv,text/csv";

function uploadDocumentsFor(area: string, support: string[] = []) {
  if (area === "Notas") return [{ type: "nota", label: "NFS-e", accept: "application/pdf,.pdf", multiple: true }];
  if (area === "Apropriações") return [{ type: "comprovante", label: "Despesas gerais", accept: "application/pdf,.pdf", multiple: true }];
  if (area === "Folha de Pagamento") return [{ type: "folha_pagamento", label: "Folha de pagamento", accept: "application/pdf,.pdf", multiple: true }];
  if (bankNames.includes(area)) {
    const documents = [
      { type: "extrato", label: "Extrato", accept: "application/pdf,.pdf" },
      { type: "comprovante", label: "Comprovantes", accept: "application/pdf,.pdf", multiple: true },
      { type: "rfb", label: "Receita Federal", accept: "application/pdf,.pdf", multiple: true },
      { type: "maquininha_extrato", label: area === "Santander" ? "Extrato Getnet" : "Maquininhas", accept: "application/pdf,.pdf", multiple: true },
    ];
    if (support.includes("Empréstimos/Financiamentos")) documents.push({ type: "emprestimo", label: "Emprést./Fin.", accept: loanAccept, multiple: true });
    if (support.includes("Folha de Pagamento")) documents.push({ type: "folha_pagamento", label: "Folha", accept: "application/pdf,.pdf", multiple: true });
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

function samePeriod(process: Process, clientId: string, start: string, end: string) {
  return process.cliente_id === clientId && process.data_inicio === start && process.data_fim === end;
}

function bankHasGuidedLock(reconciliation?: Reconciliation) {
  if (!reconciliation) return false;
  const progress = reconciliation.progresso_regras;
  const hasClassifiedMovements = !!progress && (progress.total > 0 || progress.cobertos > 0 || progress.percentual > 0);
  return hasClassifiedMovements || ["conciliado", "concluido", "finalizado"].includes(String(reconciliation.status ?? "").toLowerCase());
}

function progressColor(percent: number) {
  if (percent >= 60) return "text-emerald-700";
  if (percent >= 10) return "text-orange-600";
  return "text-red-700";
}

function displayAreaName(area: string, flowType: FlowType) {
  return area === "Apropriações" && flowType === "despesas" ? "Despesas Gerais" : area;
}

export default function GuidedReconciliationPage() {
  const [flowType, setFlowType] = useState<FlowType>("bancos");
  const [clients, setClients] = useState<Client[]>([]);
  const [processes, setProcesses] = useState<Process[]>([]);
  const [clientId, setClientId] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [selectedBanks, setSelectedBanks] = useState<string[]>(["Banco do Brasil"]);
  const [selectedSupport, setSelectedSupport] = useState<string[]>(flowConfigs.bancos.support);
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
  const [viewer, setViewer] = useState<Viewer | null>(null);
  const [ruleForm, setRuleForm] = useState<RuleForm>(defaultRuleForm);
  const [rulePreview, setRulePreview] = useState<RulePreview | null>(null);
  const [ruleBusy, setRuleBusy] = useState("");
  const [rulesTab, setRulesTab] = useState<"pending" | "saved" | "hidden">("pending");
  const [ruleSuggestions, setRuleSuggestions] = useState<RuleSuggestion[]>([]);
  const [selectedRuleSuggestions, setSelectedRuleSuggestions] = useState<string[]>([]);
  const [editingRuleId, setEditingRuleId] = useState("");
  const [expandedRuleId, setExpandedRuleId] = useState("");

  useEffect(() => {
    const param = new URLSearchParams(window.location.search).get("tipo");
    const nextType: FlowType = param === "notas" || param === "despesas" || param === "folha" ? param : "bancos";
    const config = flowConfigs[nextType];
    setFlowType(nextType);
    setSelectedBanks([config.area]);
    setActiveArea(config.area);
    setSelectedSupport(config.support);
  }, []);

  useEffect(() => {
    Promise.all([
      fetch(`${API}/api/clientes`).then((response) => {
        if (!response.ok) throw new Error();
        return response.json();
      }),
      fetch(`${API}/api/processos-conciliacao`, { cache: "no-store" }).then((response) => {
        if (!response.ok) throw new Error();
        return response.json();
      }),
    ])
      .then(([nextClients, nextProcesses]) => {
        setClients(nextClients);
        setProcesses(nextProcesses);
      })
      .catch(() => setMessage("Não foi possível carregar os clientes."));
  }, []);

  const selectedClient = clients.find((client) => client.id === clientId);
  const flowConfig = flowConfigs[flowType];
  const displayedSteps = useMemo(() => steps.map((step) => step.id === 2 ? { ...step, title: flowConfig.step2, desc: flowConfig.step2Desc } : step), [flowConfig]);
  const selectedBlocks = useMemo(() => Array.from(new Set([...selectedBanks.map((item) => item === "Apropriações" && flowType === "despesas" ? "Despesas Gerais" : item), ...selectedSupport])), [selectedBanks, selectedSupport, flowType]);
  const matchingProcess = useMemo(() => processes.find((item) => samePeriod(item, clientId, start, end)) ?? null, [processes, clientId, start, end]);
  const activeReconciliation = process?.bancos.find((item) => item.banco === activeArea) ?? process?.bancos[0] ?? null;
  const activeDocuments = uploadDocumentsFor(activeArea, selectedSupport);
  const activeUploadDocument = activeDocuments.find((item) => item.type === uploadTab) ?? activeDocuments[0];
  const selectedExistingBank = matchingProcess?.bancos.find((item) => item.banco === selectedBanks[0]);
  const selectedBankLocked = bankHasGuidedLock(selectedExistingBank);
  const isNotesRules = activeArea === "Notas";

  useEffect(() => {
    if (activeDocuments.length && !activeDocuments.some((item) => item.type === uploadTab)) setUploadTab(activeDocuments[0].type);
  }, [activeDocuments, uploadTab]);

  useEffect(() => {
    if (!matchingProcess) return;
    const currentBank = selectedBanks[0];
    const current = matchingProcess.bancos.find((item) => item.banco === currentBank);
    if (!bankHasGuidedLock(current)) return;
    if (flowType !== "bancos") return;
    const available = bankOptions.find((bank) => !bankHasGuidedLock(matchingProcess.bancos.find((item) => item.banco === bank.name)));
    if (available) selectBank(available.name);
  }, [matchingProcess, selectedBanks, flowType]);

  useEffect(() => {
    if (!activeReconciliation || ![4, 5, 6, 7].includes(activeStep)) return;
    let cancelled = false;
    setPanelLoading(true);
    const rulesUrl = activeReconciliation.banco === "Notas"
      ? `${API}/api/conciliacoes/${activeReconciliation.id}/regras-fonte/nota`
      : `${API}/api/conciliacoes/${activeReconciliation.id}/regras-contabeis`;
    Promise.all([
      fetch(`${API}/api/conciliacoes/${activeReconciliation.id}/revisao`, { cache: "no-store" }).then((response) => (response.ok ? response.json() : {})),
      fetch(`${API}/api/conciliacoes/${activeReconciliation.id}/resultado`, { cache: "no-store" }).then((response) => (response.ok ? response.json() : [])),
      fetch(rulesUrl, { cache: "no-store" }).then((response) => (response.ok ? response.json() : {})),
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
    const existing = matchingProcess?.bancos.find((item) => item.banco === bank);
    if (bankHasGuidedLock(existing)) return;
    setSelectedBanks([bank]);
    setActiveArea(bank);
  }

  async function loadProcess(processId: string) {
    const response = await fetch(`${API}/api/processos-conciliacao/${processId}`, { cache: "no-store" });
    if (!response.ok) throw new Error("Não foi possível carregar o processo.");
    return (await response.json()) as Process;
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
    if (flowType === "bancos" && selectedBankLocked && matchingProcess) {
      setProcess(matchingProcess);
      setActiveArea(selectedExistingBank?.banco ?? matchingProcess.bancos[0]?.banco ?? selectedBanks[0]);
      setMessage("Este banco já foi iniciado neste período. Abra pela conciliação normal para preservar o trabalho feito.");
      return;
    }
    setLoading(true);
    try {
      const targetProcess = matchingProcess ?? await (async () => {
        const response = await fetch(`${API}/api/processos-conciliacao`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ cliente_id: clientId, data_inicio: start, data_fim: end }),
        });
        if (!response.ok) throw new Error((await response.json()).detail ?? "Não foi possível criar o processo.");
        return (await response.json()) as Process;
      })();
      await Promise.all(
        selectedBanks.map(async (area) => {
          if (targetProcess.bancos.some((item) => item.banco === area)) return null;
          const areaResponse = await fetch(`${API}/api/processos-conciliacao/${targetProcess.id}/bancos`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ banco: area }),
          });
          if (!areaResponse.ok) throw new Error((await areaResponse.json()).detail ?? `Não foi possível criar ${area}.`);
          return areaResponse.json();
        }),
      );
      const updated = await loadProcess(targetProcess.id);
      setProcess({ ...updated, bancos: updated.bancos.filter((item) => selectedBanks.includes(item.banco)) });
      setProcesses((current) => [updated, ...current.filter((item) => item.id !== updated.id)]);
      setActiveArea(selectedBanks[0]);
      setActiveStep(3);
      setMessage(matchingProcess ? "Período existente retomado. O módulo selecionado está dentro da mesma competência." : "Processo criado. Envie os arquivos para continuar.");
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

  async function deleteDocument(fileId: string) {
    if (!activeReconciliation) return;
    const key = `${activeReconciliation.id}:delete`;
    setUploadStatus((current) => ({ ...current, [key]: { status: "uploading", message: "Excluindo arquivo..." } }));
    try {
      const response = await fetch(`${API}/api/arquivos/${fileId}`, { method: "DELETE" });
      if (!response.ok) throw new Error((await response.json()).detail ?? "Não foi possível excluir o arquivo.");
      const reviewResponse = await fetch(`${API}/api/conciliacoes/${activeReconciliation.id}/revisao`, { cache: "no-store" });
      if (reviewResponse.ok) setReview(await reviewResponse.json());
      await refreshRules();
      setResults([]);
      setUploadStatus((current) => ({ ...current, [key]: { status: "done", message: "Arquivo excluído." } }));
      setMessage("Arquivo excluído. Processe novamente quando terminar os envios.");
    } catch (error) {
      const fallback = error instanceof Error ? error.message : "Não foi possível excluir o arquivo.";
      setUploadStatus((current) => ({ ...current, [key]: { status: "error", message: fallback } }));
      setMessage(fallback);
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

  function buildRuleSuggestions(row: Record<string, unknown>) {
    const fields: { label: string; value: unknown; target: RuleSuggestion["target"] }[] = [
      { label: "Histórico contém", value: row.historico ?? row.gatilho_sugerido ?? row.texto, target: "extrato" },
      { label: "Comprovante contém", value: row.texto_comprovante ?? row.favorecido ?? row.beneficiario ?? row.documento, target: "comprovante" },
      { label: "Forma de pagamento", value: row.tipo_pagamento_label ?? row.forma_pagamento, target: isNotesRules ? "extrato" : "comprovante" },
      { label: "Documento", value: row.documento, target: "comprovante" },
      { label: "Valor", value: row.valor, target: "extrato" },
    ];
    const seen = new Set<string>();
    return fields
      .map((item) => ({ ...item, value: String(item.value ?? "").trim() }))
      .filter((item) => item.value && item.value !== "—" && item.value !== "Não identificado")
      .filter((item) => {
        const key = `${item.target}:${item.label}:${item.value}`.toLowerCase();
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      })
      .slice(0, 8)
      .map((item, index) => ({ id: `${item.target}-${index}`, label: item.label, value: item.value, target: item.target }));
  }

  function applyRuleSuggestion(suggestion: RuleSuggestion, checked: boolean) {
    setSelectedRuleSuggestions((current) => checked ? Array.from(new Set([...current, suggestion.id])) : current.filter((item) => item !== suggestion.id));
    if (!checked) return;
    if (suggestion.target === "extrato") updateRuleForm({ gatilho: suggestion.value });
    if (suggestion.target === "comprovante") updateRuleForm({ gatilho_comprovante: suggestion.value });
    if (suggestion.target === "exclusao") updateRuleForm({ texto_exclusao: suggestion.value });
  }

  function selectPendingRule(raw: unknown) {
    const row = raw as Record<string, unknown>;
    const paymentTrigger = isNotesRules && row.tipo_pagamento_label && row.tipo_pagamento_label !== "Não identificado" ? String(row.tipo_pagamento_label) : "";
    const history = paymentTrigger || String(row.historico ?? row.gatilho_sugerido ?? row.texto ?? "");
    const suggestions = buildRuleSuggestions(row);
    const primary = suggestions.find((item) => item.target === "extrato")?.id;
    setRuleSuggestions(suggestions);
    setSelectedRuleSuggestions(primary ? [primary] : []);
    setRulePreview(null);
    setRuleForm({
      ...defaultRuleForm,
      gatilho: history,
      gatilho_comprovante: "",
      texto_exclusao: "",
      natureza: String(row.natureza_contabil ?? row.natureza ?? "Crédito"),
      conta_debito: "",
      conta_credito: "",
      historico: history,
      complemento: isNotesRules ? String(row.documento && row.documento !== "—" ? row.documento : "Conforme nota fiscal") : "Conforme extrato bancário",
      tipo_componente: String(row.tipo_componente ?? row.tipo_lancamento ?? "PRINCIPAL"),
      aplicar_existentes: true,
    });
  }

  function editSavedRule(raw: unknown) {
    const row = raw as Record<string, unknown>;
    setEditingRuleId(String(row.id ?? ""));
    setExpandedRuleId(String(row.id ?? ""));
    setRuleSuggestions([]);
    setSelectedRuleSuggestions([]);
    setRulePreview(null);
    setRuleForm({
      ...defaultRuleForm,
      gatilho: String(row.gatilho ?? ""),
      gatilho_comprovante: String(row.gatilho_comprovante ?? ""),
      texto_exclusao: String(row.texto_exclusao ?? ""),
      natureza: String(row.natureza ?? "Crédito"),
      conta_debito: String(row.conta_debito ?? ""),
      conta_credito: String(row.conta_credito ?? ""),
      historico: String(row.historico ?? ""),
      complemento: String(row.complemento ?? ""),
      tipo_componente: String(row.tipo_componente ?? "PRINCIPAL"),
      aplicar_existentes: true,
    });
    setActiveStep(5);
  }

  function newGuidedRule() {
    setEditingRuleId("");
    setRulePreview(null);
    setRuleSuggestions([]);
    setSelectedRuleSuggestions([]);
    setRuleForm(defaultRuleForm);
    setActiveStep(5);
  }

  function updateRuleForm(next: Partial<RuleForm>) {
    setRulePreview(null);
    setRuleForm((current) => ({ ...current, ...next }));
  }

  async function calculateRuleCoverage(showMessage = true) {
    if (!activeReconciliation) return 0;
    if (!ruleForm.gatilho.trim() && !ruleForm.gatilho_comprovante.trim()) {
      setRulePreview({ quantidade: 0, motivo: "Informe pelo menos uma condição para validar a regra.", lancamentos: [] });
      setMessage("Informe pelo menos uma condição para validar a regra.");
      return 0;
    }
    setRuleBusy("preview");
    try {
      const response = await fetch(`${API}/api/conciliacoes/${activeReconciliation.id}/${isNotesRules ? "regras-fonte/nota/previa" : "regras-contabeis/previa"}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          gatilho: ruleForm.gatilho,
          gatilho_comprovante: ruleForm.gatilho_comprovante,
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
      const url = isNotesRules
        ? `${API}/api/conciliacoes/${activeReconciliation.id}/regras-fonte/nota`
        : `${API}/api/conciliacoes/${activeReconciliation.id}/regras-contabeis${editingRuleId ? `/${editingRuleId}` : ""}`;
      const response = await fetch(url, {
        method: editingRuleId && !isNotesRules ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(ruleForm),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.detail ?? "Não foi possível salvar a regra.");
      if (result.regras) setRules(result.regras);
      setRulePreview(null);
      setEditingRuleId("");
      setRulesTab("saved");
      setMessage(isNotesRules ? "Regra de notas salva." : editingRuleId ? "Regra atualizada." : `Regra salva e aplicada a ${result.movimentos_aplicados ?? 0} lançamento(s).`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Não foi possível salvar a regra.");
    } finally {
      setRuleBusy("");
    }
  }

  async function refreshRules() {
    if (!activeReconciliation) return;
    const response = await fetch(`${API}/api/conciliacoes/${activeReconciliation.id}/${isNotesRules ? "regras-fonte/nota" : "regras-contabeis"}`, { cache: "no-store" });
    if (response.ok) setRules(await response.json());
  }

  async function removeRule(ruleId: string, scope: "periodo" | "global") {
    if (!activeReconciliation) return;
    setRuleBusy(ruleId);
    try {
      const response = await fetch(
        isNotesRules
          ? `${API}/api/conciliacoes/${activeReconciliation.id}/regras-fonte/nota/${ruleId}`
          : `${API}/api/conciliacoes/${activeReconciliation.id}/regras-contabeis/${ruleId}${scope === "periodo" ? "/periodo" : ""}`,
        { method: "DELETE" },
      );
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
  const activeMeta = displayedSteps.find((step) => step.id === activeStep) ?? displayedSteps[0];
  const areaLabel = displayAreaName(activeArea, flowType);
  const contextItems = [
    ["Fluxo", flowConfig.title],
    ["Etapa", `${activeStep}/7 · ${activeMeta.title}`],
    ["Cliente", selectedClient?.nome ?? "Não selecionado"],
    ["Período", monthRange(start, end)],
    [flowType === "bancos" ? "Banco" : "Área", areaLabel],
    ["Documento", activeStep >= 3 ? activeUploadDocument?.label ?? "Selecione um arquivo" : "Aguardando upload"],
  ];

  return (
    <main className="guided-compact min-h-screen bg-slate-100 text-slate-900">
      <div className="grid min-h-screen lg:grid-cols-[232px_1fr]">
        <aside className="hidden max-h-screen overflow-y-auto bg-slate-950 p-2.5 text-slate-200 lg:flex lg:flex-col">
          <Link href="/" className="mb-2 flex items-center gap-2 rounded-md border-b border-slate-800 px-2 py-1.5 text-sm font-bold text-white">
            <span className="rounded bg-teal-600 p-1"><Building2 size={15} /></span>
            ConcilIA
          </Link>
          <div className="mb-2 rounded-md border border-slate-800 bg-slate-900 p-2 text-[11px]">
            <span className="block font-semibold text-slate-400">Contexto ativo</span>
            <strong className="mt-1 block text-white">{selectedClient?.nome ?? "Selecione um cliente"}</strong>
            <span className="mt-1 block text-slate-400">{flowConfig.title} · {areaLabel} · {monthRange(start, end)}</span>
          </div>
          <nav className="space-y-1 text-xs">
            <Link href="/" className="flex items-center gap-2 rounded-md px-2 py-1.5 text-slate-300 hover:bg-slate-900"><LayoutDashboard size={14} />Central</Link>
            <Link href="/conciliacao" className="mb-2 flex items-center gap-2 rounded-md px-2 py-1.5 text-slate-300 hover:bg-slate-900"><FolderOpen size={14} />Conciliação atual</Link>
            {displayedSteps.map((step) => {
              const Icon = step.icon;
              return (
                <button type="button" key={step.id} onClick={() => setActiveStep(step.id)} className={`flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left ${activeStep === step.id ? "bg-teal-500 font-semibold text-slate-950" : "text-slate-300 hover:bg-slate-900"}`}>
                  <span className={`grid h-5 w-5 place-items-center rounded-full text-[10px] ${activeStep === step.id ? "bg-white" : "bg-slate-900 text-slate-400"}`}>{step.id}</span>
                  <Icon size={14} />
                  <span className="min-w-0"><span className="block leading-tight">{step.title}</span><span className={`block truncate text-[10px] ${activeStep === step.id ? "text-teal-950" : "text-slate-500"}`}>{step.desc}</span></span>
                </button>
              );
            })}
          </nav>
        </aside>

        <section className="min-w-0">
          <header className="border-b border-slate-200 bg-white px-4 py-2.5">
            <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3">
              <div>
                <div className="mb-1 flex flex-wrap items-center gap-1.5 text-[11px] font-bold text-slate-500">
                  <span className="rounded-full bg-teal-50 px-2 py-0.5 text-teal-800">{flowConfig.title}</span>
                  <span>/</span>
                  <span>{areaLabel}</span>
                  <span>/</span>
                  <span>{monthRange(start, end)}</span>
                </div>
                <p className="text-[11px] font-semibold uppercase tracking-wide text-teal-700">Etapa {activeStep} de 7</p>
                <h1 className="text-base font-bold leading-tight">{activeMeta.title}</h1>
                <p className="text-xs text-slate-500">{activeMeta.desc}</p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {process && (
                  <select value={activeArea} onChange={(event) => setActiveArea(event.target.value)} className="rounded-md border border-slate-300 px-2.5 py-1.5 text-xs font-semibold">
                    {process.bancos.map((item) => <option value={item.banco} key={item.id}>{item.banco}</option>)}
                  </select>
                )}
                <Link href="/" className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 px-2.5 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"><RotateCcw size={14} />Voltar</Link>
              </div>
            </div>
          </header>

          <div className="mx-auto max-w-7xl space-y-2.5 px-3 py-3">
            {message && <p className="rounded-md bg-teal-50 px-2.5 py-1.5 text-xs font-semibold text-teal-800">{message}</p>}
            <ContextMap items={contextItems} existing={!!matchingProcess} />

            {activeStep === 1 && (
              <form onSubmit={(event) => { event.preventDefault(); setActiveStep(2); }} className="grid gap-3 xl:grid-cols-[1fr_310px]">
                <section className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
                  <div className="mb-2 flex items-center gap-2 text-teal-800"><Building2 size={18} /><h2 className="font-bold">Cadastro</h2></div>
                  <div className="mb-3 flex flex-wrap gap-1.5">
                    {["clientes", "bancos", "plano", "historico"].map((tab) => (
                      <button type="button" key={tab} onClick={() => setCadTab(tab)} className={`rounded-full border px-3 py-1 text-[11px] font-bold capitalize ${cadTab === tab ? "border-slate-900 bg-slate-900 text-white" : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"}`}>{tab}</button>
                    ))}
                  </div>
                  {cadTab === "clientes" && (
                    <div className="space-y-3">
                      <div className="grid gap-3 md:grid-cols-[1fr_160px_160px]">
                        <label className="text-xs font-semibold">Cliente
                          <select required value={clientId} onChange={(event) => setClientId(event.target.value)} className="mt-1 w-full rounded-md border border-slate-300 px-2.5 py-1.5 font-normal">
                            <option value="">Selecionar cliente</option>
                            {clients.map((client) => <option value={client.id} key={client.id}>{client.nome}</option>)}
                          </select>
                        </label>
                        <label className="text-xs font-semibold">Início
                          <input required type="date" value={start} onChange={(event) => setStart(event.target.value)} className="mt-1 w-full rounded-md border border-slate-300 px-2.5 py-1.5 font-normal" />
                        </label>
                        <label className="text-xs font-semibold">Fim
                          <input required type="date" value={end} onChange={(event) => setEnd(event.target.value)} className="mt-1 w-full rounded-md border border-slate-300 px-2.5 py-1.5 font-normal" />
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
                  <div className="mt-3 flex justify-end">
                    <button className="inline-flex items-center gap-2 rounded-md bg-teal-700 px-3 py-1.5 text-xs font-bold text-white hover:bg-teal-800">Próxima<ArrowRight size={15} /></button>
                  </div>
                </section>
                <SummaryCard selectedClient={selectedClient} start={start} end={end} selectedAreas={selectedBlocks} matchingProcess={matchingProcess} title={flowConfig.title} summary={flowConfig.summary} />
              </form>
            )}

            {activeStep === 2 && (
              <section className="grid gap-3 xl:grid-cols-[1fr_310px]">
                <div className="space-y-3">
                  <section className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
                    <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2 text-teal-800"><Banknote size={16} /><h2 className="font-bold">Bancos</h2></div>
                      {matchingProcess && <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-bold text-amber-900">Período existente</span>}
                    </div>
                    {flowType === "bancos" ? <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-5">
                      {bankOptions.map((bank) => {
                        const active = selectedBanks.includes(bank.name);
                        const existing = matchingProcess?.bancos.find((item) => item.banco === bank.name);
                        const locked = bankHasGuidedLock(existing);
                        const progress = existing?.progresso_regras ?? { total: 0, cobertos: 0, percentual: 0 };
                        const created = !!existing;
                        return (
                          <div
                            role={locked ? undefined : "button"}
                            tabIndex={locked ? undefined : 0}
                            onClick={() => !locked && selectBank(bank.name)}
                            onKeyDown={(event) => {
                              if (!locked && (event.key === "Enter" || event.key === " ")) selectBank(bank.name);
                            }}
                            className={`rounded-md border p-2 text-left ${locked ? "border-slate-200 bg-slate-50 opacity-90" : active ? "cursor-pointer border-teal-600 bg-teal-50" : "cursor-pointer border-slate-200 bg-white hover:border-slate-300"}`}
                            key={bank.name}
                          >
                            <div className="flex items-center gap-2">
                              <div className="flex h-8 w-12 shrink-0 items-center justify-center rounded-md border border-slate-200 bg-white px-1">
                                <img src={bank.logo} alt={bank.name} className="max-h-6 max-w-full object-contain" />
                              </div>
                              <div className="min-w-0 flex-1">
                                <div className="flex items-center gap-1.5">
                                  <span className="font-mono text-[10px] font-bold text-slate-500">{bank.code}</span>
                                  {active && <Check size={12} className="text-teal-700" />}
                                </div>
                                <strong className="block truncate text-xs leading-tight" title={bank.name}>{bank.name}</strong>
                              </div>
                            </div>
                            <span className="mt-1.5 flex items-center justify-between gap-2 rounded bg-white/70 px-1.5 py-0.5">
                              <span className={`truncate text-[11px] font-bold ${locked ? "text-slate-600" : created ? "text-teal-700" : "text-slate-500"}`}>{locked ? "Já iniciado" : created ? "Continuar" : "Disponível"}</span>
                              <span className={`text-xs font-black tabular-nums ${progressColor(progress.percentual)}`}>{progress.percentual}%</span>
                            </span>
                            {locked && matchingProcess && (
                              <Link href={`/conciliacao?process=${matchingProcess.id}`} className="mt-1.5 inline-flex w-full items-center justify-center rounded-md bg-slate-900 px-2 py-1 text-[11px] font-bold text-white hover:bg-slate-800">
                                Abrir
                              </Link>
                            )}
                          </div>
                        );
                      })}
                    </div> : (
                      <div className="rounded-md border border-teal-200 bg-teal-50 p-3">
                        <span className="text-xs font-bold uppercase tracking-wide text-teal-700">{flowConfig.title}</span>
                        <h3 className="mt-1 text-base font-black text-slate-900">{displayAreaName(flowConfig.area, flowType)}</h3>
                        <p className="mt-1 text-xs font-medium text-slate-600">{flowConfig.summary}</p>
                        {matchingProcess && (
                          <p className="mt-2 text-[11px] font-semibold text-amber-800">
                            Se este fluxo já tiver sido iniciado neste período, continue pela conciliação normal para revisar regras e exportações.
                          </p>
                        )}
                      </div>
                    )}
                    {matchingProcess && (
                      <p className="mt-2 rounded-md bg-slate-50 px-2.5 py-1.5 text-[11px] font-semibold text-slate-600">
                        Bancos já trabalhados ficam protegidos no acesso guiado. Para revisar regras, editar ou excluir lançamentos, abra pela conciliação normal.
                      </p>
                    )}
                  </section>
                  {flowType === "bancos" && <section className="rounded-lg border border-slate-200 bg-white p-2.5 shadow-sm">
                    <div className="mb-2 flex items-center gap-2 text-teal-800"><FileText size={16} /><h2 className="font-bold">Áreas auxiliares</h2></div>
                    <div className="grid gap-1.5 md:grid-cols-4">
                      {supportOptions.map((option) => {
                        const Icon = option.icon;
                        const active = selectedSupport.includes(option.name);
                        return (
                          <button type="button" onClick={() => toggle(option.name, selectedSupport, setSelectedSupport)} className={`flex min-h-8 items-center gap-2 rounded-md border px-2 py-1.5 text-left ${active ? "border-teal-600 bg-teal-50" : "border-slate-200 bg-white hover:border-slate-300"}`} key={option.name} title={option.hint}>
                            <Icon size={15} className={active ? "text-teal-700" : "text-slate-500"} />
                            <strong className="block truncate text-xs">{option.name}</strong>
                          </button>
                        );
                      })}
                    </div>
                  </section>}
                  <div className="flex justify-end">
                    <button disabled={loading || (flowType === "bancos" && selectedBankLocked)} onClick={ensureProcess} className="inline-flex items-center gap-2 rounded-md bg-teal-700 px-3 py-1.5 text-xs font-bold text-white hover:bg-teal-800 disabled:cursor-not-allowed disabled:opacity-70">
                      {loading ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
                      {matchingProcess ? "Continuar" : "Criar e enviar"}
                    </button>
                  </div>
                </div>
                <SummaryCard selectedClient={selectedClient} start={start} end={end} selectedAreas={selectedBlocks} matchingProcess={matchingProcess} title={flowConfig.title} summary={flowConfig.summary} />
              </section>
            )}

            {activeStep === 3 && (
              <GuidedPanel title="Upload de arquivos" action={<button onClick={processActive} disabled={!activeReconciliation || uploadStatus[`${activeReconciliation.id}:processar`]?.status === "uploading"} className="inline-flex items-center gap-2 rounded-md bg-slate-900 px-3 py-1.5 text-xs font-bold text-white hover:bg-slate-800 disabled:cursor-wait disabled:opacity-70"><PlayCircle size={15} />Processar</button>}>
                {!process ? (
                  <EmptyAction text="Crie o processo antes de enviar arquivos." onClick={() => setActiveStep(1)} />
                ) : (
                  <div>
                    <div className="mb-3 flex flex-wrap gap-1.5">
                      {activeDocuments.map((doc) => (
                        <button type="button" key={doc.type} onClick={() => setUploadTab(doc.type)} className={`rounded-full border px-2.5 py-1 text-[11px] font-bold ${uploadTab === doc.type ? "border-slate-900 bg-slate-900 text-white" : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"}`}>{doc.label}</button>
                      ))}
                    </div>
                    {activeUploadDocument ? (() => {
                      const doc = activeUploadDocument;
                      const key = `${activeReconciliation?.id}:${doc.type}`;
                      const status = uploadStatus[key];
                      const busy = status?.status === "uploading";
                      return (
                        <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-3 text-center">
                          <UploadCloud className="mx-auto text-teal-700" size={20} />
                          <h3 className="mt-1.5 text-xs font-bold">{doc.label} — {activeArea}</h3>
                          <p className="mt-1 text-xs text-slate-500">{doc.accept.includes("xlsx") ? "PDF, XLSX ou CSV" : "PDF"}{doc.multiple ? " · múltiplos arquivos" : ""}</p>
                          <label className={`mt-2 inline-flex cursor-pointer items-center gap-1.5 rounded-md px-2.5 py-1 text-[11px] font-bold ${busy ? "bg-slate-300 text-slate-600" : "bg-teal-700 text-white hover:bg-teal-800"}`}>
                            {busy ? <Loader2 size={14} className="animate-spin" /> : <UploadCloud size={14} />}
                            Selecionar arquivo
                            <input type="file" className="hidden" accept={doc.accept} multiple={doc.multiple} disabled={busy || !activeReconciliation} onChange={(event) => activeReconciliation && uploadFile(activeReconciliation.id, doc.type, event)} />
                          </label>
                          {status && <p className={`mt-3 text-xs font-semibold ${status.status === "error" ? "text-red-700" : "text-teal-700"}`}>{status.message}</p>}
                          {uploadStatus[`${activeReconciliation?.id}:delete`]?.message && <p className={`mt-2 text-xs font-semibold ${uploadStatus[`${activeReconciliation?.id}:delete`]?.status === "error" ? "text-red-700" : "text-teal-700"}`}>{uploadStatus[`${activeReconciliation?.id}:delete`]?.message}</p>}
                          <div className="mt-3 rounded-md border border-slate-200 bg-white text-left">
                            {(review.arquivos ?? []).filter((file) => file.tipo === doc.type).slice(0, 8).map((file) => (
                              <div className="flex items-center justify-between gap-2 border-b border-slate-100 px-2.5 py-1.5 last:border-b-0" key={file.id}>
                                <span className="min-w-0 truncate text-xs font-semibold">{file.nome}</span>
                                <span className={`rounded px-2 py-1 text-[11px] font-bold ${file.status === "concluido" ? "bg-teal-100 text-teal-800" : file.status === "erro" ? "bg-red-100 text-red-700" : "bg-amber-100 text-amber-800"}`}>{file.status}</span>
                                <button type="button" onClick={() => setViewer({ arquivoId: file.id, pagina: 1, titulo: file.nome })} title="Visualizar arquivo" aria-label={`Visualizar ${file.nome}`} className="rounded p-1 text-slate-700 hover:bg-slate-100"><Eye size={15} /></button>
                                <button type="button" onClick={() => deleteDocument(file.id)} title="Excluir arquivo" aria-label={`Excluir ${file.nome}`} className="rounded p-1 text-red-600 hover:bg-red-50"><Trash2 size={15} /></button>
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
              <GuidedPanel title="Conciliação" loading={panelLoading} action={<button onClick={processActive} disabled={!activeReconciliation} className="inline-flex items-center gap-2 rounded-md bg-teal-700 px-3 py-1.5 text-xs font-bold text-white hover:bg-teal-800 disabled:opacity-60"><PlayCircle size={15} />Reprocessar</button>}>
                <StatsGrid items={isNotesRules ? [["Notas extraídas", count(review.notas)], ["Regras criadas", count(rules.salvas)], ["Pendentes", count(rules.pendentes)]] : [["Extrato", count(review.extratos)], ["Comprovantes", count(review.comprovantes)], ["Folha", count(review.folhas)], ["RFB", count(review.rfb)], ["Resultados", results.length]]} />
                {isNotesRules ? <NotesReviewTable rows={review.notas ?? []} onView={setViewer} /> : <MiniTable rows={results} onView={setViewer} onCreateRule={(row) => { selectPendingRule(row); setRulesTab("pending"); setActiveStep(5); }} />}
              </GuidedPanel>
            )}

            {activeStep === 5 && (
              <GuidedPanel title="Criar regras" loading={panelLoading}>
                <div className="mb-2 flex flex-wrap items-center justify-between gap-2 rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1.5">
                  <div className="flex flex-wrap gap-1.5">
                    <button type="button" onClick={() => setRulesTab("pending")} className={`rounded-full px-2.5 py-1 text-[11px] font-bold ${rulesTab === "pending" ? "bg-slate-900 text-white" : "border border-slate-200 bg-white text-slate-700"}`}>A criar · {count(rules.pendentes)}</button>
                    <button type="button" onClick={() => setRulesTab("saved")} className={`rounded-full px-2.5 py-1 text-[11px] font-bold ${rulesTab === "saved" ? "bg-teal-700 text-white" : "border border-teal-200 bg-white text-teal-800"}`}>Salvas · {count(rules.salvas)}</button>
                    <button type="button" onClick={() => setRulesTab("hidden")} className={`rounded-full px-2.5 py-1 text-[11px] font-bold ${rulesTab === "hidden" ? "bg-violet-700 text-white" : "border border-violet-200 bg-white text-violet-800"}`}>Ocultas · {count(rules.ignoradas)}</button>
                  </div>
                  <span className="text-[11px] font-semibold text-slate-500">Selecione uma pendência, valide a cobertura e salve a regra.</span>
                </div>
                {rulesTab === "pending" && <div className="grid gap-2.5 xl:grid-cols-[minmax(0,1fr)_410px]">
                  <PendingRules rows={rules.pendentes ?? []} onSelect={selectPendingRule} onView={setViewer} showNotePayment={isNotesRules} />
                  <form onSubmit={saveGuidedRule} className="h-fit rounded-lg border border-slate-200 bg-white p-2.5 shadow-sm">
                    <div className="flex items-center justify-between gap-2 border-b border-slate-100 pb-1.5">
                      <div>
                        <span className="rounded bg-teal-50 px-1.5 py-0.5 text-[10px] font-black uppercase tracking-wide text-teal-800">Regra contábil</span>
                        <h3 className="mt-1 text-xs font-black text-slate-900">{editingRuleId ? "Editar regra" : "Nova regra"}</h3>
                      </div>
                      {editingRuleId && <button type="button" onClick={newGuidedRule} className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-bold text-slate-700 hover:bg-slate-50">Nova</button>}
                    </div>
                    <div className="mt-2 grid gap-2">
                      {!!ruleSuggestions.length && (
                        <div className="rounded-md border border-slate-200 bg-slate-50 p-2">
                          <div className="mb-1.5 flex items-center justify-between gap-2">
                            <span className="text-[10px] font-black uppercase tracking-wide text-slate-500">Condições sugeridas</span>
                            <span className="rounded-full bg-white px-2 py-0.5 text-[10px] font-bold text-slate-500">use só o que fizer sentido</span>
                          </div>
                          <div className="grid gap-1">
                            {ruleSuggestions.map((suggestion) => (
                              <label key={suggestion.id} className="flex cursor-pointer items-center gap-2 rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-700 hover:border-teal-200 hover:bg-teal-50">
                                <input type="checkbox" checked={selectedRuleSuggestions.includes(suggestion.id)} onChange={(event) => applyRuleSuggestion(suggestion, event.target.checked)} className="h-3.5 w-3.5 accent-teal-700" />
                                <span className="shrink-0 text-slate-500">{suggestion.label}</span>
                                <strong className="min-w-0 truncate text-slate-900" title={suggestion.value}>{suggestion.value}</strong>
                              </label>
                            ))}
                          </div>
                        </div>
                      )}
                      <div className="grid grid-cols-[1fr_1fr] gap-2">
                      <RuleField label="Palavra-chave no extrato">
                        <input value={ruleForm.gatilho} onChange={(event) => updateRuleForm({ gatilho: event.target.value })} className="w-full rounded-md border border-slate-300 px-2.5 py-1.5 text-xs font-semibold text-slate-800" placeholder="palavra chave..." />
                      </RuleField>
                      <RuleField label="Palavra-chave no comprovante">
                        <input value={ruleForm.gatilho_comprovante} onChange={(event) => updateRuleForm({ gatilho_comprovante: event.target.value })} className="w-full rounded-md border border-slate-300 px-2.5 py-1.5 text-xs font-semibold text-slate-800" placeholder="favorecido, doc, CPF..." />
                      </RuleField>
                      </div>
                      <RuleField label="Não contém">
                        <input value={ruleForm.texto_exclusao} onChange={(event) => updateRuleForm({ texto_exclusao: event.target.value })} className="w-full rounded-md border border-slate-300 px-2.5 py-1.5 text-xs font-semibold text-slate-800" placeholder="texto de exclusão..." />
                      </RuleField>
                      <div className="grid grid-cols-[1fr_1fr_auto] gap-2">
                        <RuleField label="Natureza">
                          <select value={ruleForm.natureza} onChange={(event) => updateRuleForm({ natureza: event.target.value })} className="w-full rounded-md border border-slate-300 px-2.5 py-1.5 text-xs font-semibold text-slate-800"><option>Crédito</option><option>Débito</option></select>
                        </RuleField>
                        <RuleField label="Tipo">
                          <input value={ruleForm.tipo_componente} onChange={(event) => updateRuleForm({ tipo_componente: event.target.value })} className="w-full rounded-md border border-slate-300 px-2.5 py-1.5 text-xs font-semibold text-slate-800" />
                        </RuleField>
                        <button type="button" title="Desdobrar lançamento" className="mt-4 inline-flex h-8 items-center justify-center rounded-md border border-slate-200 bg-white px-2 text-[11px] font-bold text-slate-700 hover:bg-slate-50">Desd. Lancto</button>
                      </div>
                      <div className="rounded-md border border-slate-200 bg-slate-50 p-2">
                        <div className="mb-1.5 flex items-center justify-between">
                          <span className="text-[10px] font-black uppercase tracking-wide text-slate-500">Lançamento</span>
                          <span className="rounded-full bg-white px-2 py-0.5 text-[10px] font-bold text-slate-500">D → C</span>
                        </div>
                        <div className="grid grid-cols-[1fr_auto_1fr] items-end gap-2">
                          <RuleField label="Débito">
                            <input required value={ruleForm.conta_debito} onChange={(event) => updateRuleForm({ conta_debito: event.target.value })} className="w-full rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-800" placeholder="Selecionar" />
                          </RuleField>
                          <span className="mb-1.5 text-slate-400"><ArrowRight size={15} /></span>
                          <RuleField label="Crédito">
                            <input required value={ruleForm.conta_credito} onChange={(event) => updateRuleForm({ conta_credito: event.target.value })} className="w-full rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-800" placeholder="Selecionar" />
                          </RuleField>
                        </div>
                      </div>
                      <RuleField label="Histórico contábil">
                        <input required value={ruleForm.historico} onChange={(event) => updateRuleForm({ historico: event.target.value })} className="w-full rounded-md border border-slate-300 px-2.5 py-1.5 text-xs font-semibold text-slate-800" />
                      </RuleField>
                      <RuleField label="Complemento">
                        <input value={ruleForm.complemento} onChange={(event) => updateRuleForm({ complemento: event.target.value })} className="w-full rounded-md border border-slate-300 px-2.5 py-1.5 text-xs font-semibold text-slate-800" />
                      </RuleField>
                      <label className="flex items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-2 py-1.5 text-[11px] font-bold text-slate-700">
                        <input type="checkbox" checked={ruleForm.aplicar_existentes} readOnly className="h-3.5 w-3.5 accent-teal-700" />
                        Aplicar esta regra aos lançamentos existentes
                      </label>
                      <div className="rounded-md border border-teal-100 bg-teal-50 p-2">
                        <div className="flex items-center justify-between gap-3">
                          <strong className="text-xs text-teal-950">Cobertura</strong>
                          <button type="button" disabled={ruleBusy === "preview"} onClick={() => calculateRuleCoverage()} className="rounded-full bg-slate-900 px-2.5 py-1 text-[11px] font-bold text-white disabled:cursor-wait disabled:opacity-60">{ruleBusy === "preview" ? "Validando..." : "Ver cobertura"}</button>
                        </div>
                        {rulePreview ? (
                          <div className="mt-3">
                            <p className={`text-xs font-bold ${rulePreview.quantidade > 0 ? "text-teal-700" : "text-red-700"}`}>
                              {rulePreview.quantidade > 0 ? `Vai cobrir ${rulePreview.quantidade} lançamento(s).` : rulePreview.motivo || "Não cobre lançamentos elegíveis."}
                            </p>
                            {!!rulePreview.lancamentos?.length && (
                              <div className="mt-1.5 max-h-24 overflow-y-auto rounded border border-teal-100 bg-white">
                                {rulePreview.lancamentos.slice(0, 5).map((item, index) => (
                                  <div className="border-b border-slate-100 px-2 py-1 text-[11px] last:border-b-0" key={index}>
                                    <strong>{item.data ?? "—"}</strong> · {item.historico ?? "—"} · {item.componente ?? "PRINCIPAL"}
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        ) : <p className="mt-2 text-xs text-slate-500">Valide antes de salvar.</p>}
                      </div>
                      <button disabled={ruleBusy === "save"} className="inline-flex items-center justify-center gap-1.5 rounded-md bg-teal-700 px-2.5 py-1.5 text-xs font-bold text-white hover:bg-teal-800 disabled:cursor-wait disabled:opacity-60">{ruleBusy === "save" ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}{editingRuleId ? "Atualizar" : "Salvar"}</button>
                    </div>
                  </form>
                </div>}
                {rulesTab === "saved" && <SavedRules rows={rules.salvas ?? []} expandedRuleId={expandedRuleId} busyId={ruleBusy} onToggle={setExpandedRuleId} onEdit={isNotesRules ? () => setMessage("Para alterar regra de notas, exclua e crie novamente com o novo gatilho.") : editSavedRule} onRemovePeriod={(id) => removeRule(id, "periodo")} onRemoveGlobal={(id) => removeRule(id, "global")} />}
                {rulesTab === "hidden" && (isNotesRules ? <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">Notas não usam regras ocultas por período.</div> : <HiddenRules rows={rules.ignoradas ?? []} busyId={ruleBusy} onRestore={restoreRule} />)}
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
      {viewer && <PdfModal viewer={viewer} onClose={() => setViewer(null)} />}
      <style jsx global>{`
        .guided-compact {
          font-size: 13px;
        }
        .guided-compact h2 {
          font-size: 15px;
        }
        .guided-compact h3 {
          font-size: 13px;
        }
        .guided-compact input,
        .guided-compact select {
          min-height: 30px;
          padding-top: 0.32rem;
          padding-bottom: 0.32rem;
          font-size: 12px;
        }
        .guided-compact table {
          font-size: 12px;
        }
        .guided-compact th {
          padding: 0.45rem 0.65rem;
          font-size: 10px;
          letter-spacing: 0.03em;
        }
        .guided-compact td {
          padding: 0.45rem 0.65rem;
        }
        .guided-compact button,
        .guided-compact a,
        .guided-compact label {
          letter-spacing: 0;
        }
        .guided-compact .shadow-sm {
          box-shadow: 0 1px 2px rgb(15 23 42 / 0.04);
        }
      `}</style>
    </main>
  );
}

function PdfModal({ viewer, onClose }: { viewer: Viewer; onClose: () => void }) {
  const url = `${API}/api/arquivos/${viewer.arquivoId}/visualizar#page=${viewer.pagina}`;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4">
      <section className="flex h-[90vh] w-full max-w-6xl flex-col overflow-hidden rounded-xl bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-200 px-4 py-2">
          <div>
            <strong className="text-sm text-slate-900">{viewer.titulo}</strong>
            <p className="text-xs text-slate-500">Página {viewer.pagina}</p>
          </div>
          <button type="button" onClick={onClose} title="Fechar" aria-label="Fechar visualizador" className="rounded p-1 text-slate-600 hover:bg-slate-100"><X size={20} /></button>
        </div>
        <iframe src={url} className="min-h-0 flex-1" title={viewer.titulo} />
      </section>
    </div>
  );
}

function SummaryCard({ selectedClient, start, end, selectedAreas, matchingProcess, title, summary }: { selectedClient?: Client; start: string; end: string; selectedAreas: string[]; matchingProcess?: Process | null; title: string; summary: string }) {
  return (
    <aside className="rounded-lg border border-teal-200 bg-white p-2.5 shadow-sm">
      <div className="mb-1.5 flex items-center gap-1.5 text-teal-800"><CalendarDays size={14} /><h2 className="font-bold">Resumo</h2></div>
      <dl className="space-y-1.5 text-[11px]">
        <div><dt className="font-semibold uppercase tracking-wide text-slate-400">Fluxo</dt><dd className="mt-0.5 font-medium">{title}</dd><dd className="mt-0.5 text-slate-500">{summary}</dd></div>
        <div><dt className="font-semibold uppercase tracking-wide text-slate-400">Cliente</dt><dd className="mt-0.5 font-medium">{selectedClient?.nome ?? "Selecione um cliente"}</dd></div>
        <div><dt className="font-semibold uppercase tracking-wide text-slate-400">Período</dt><dd className="mt-0.5 font-medium">{monthRange(start, end)}</dd></div>
        {matchingProcess && <div><dt className="font-semibold uppercase tracking-wide text-slate-400">Situação</dt><dd className="mt-0.5 font-medium text-amber-800">Período existente reaproveitado.</dd></div>}
        <div><dt className="font-semibold uppercase tracking-wide text-slate-400">Blocos</dt><dd className="mt-1 flex flex-wrap gap-1">{selectedAreas.map((area) => <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[11px] font-semibold" key={area}>{area}</span>)}</dd></div>
      </dl>
    </aside>
  );
}

function ContextMap({ items, existing }: { items: string[][]; existing: boolean }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-2 shadow-sm">
      <div className="grid gap-1.5 md:grid-cols-3 xl:grid-cols-6">
        {items.map(([label, value]) => {
          const isPeriod = label === "Período";
          return (
            <div className={`min-w-0 rounded-md border px-2 py-1.5 ${isPeriod ? "border-emerald-300 bg-emerald-50" : "border-slate-200 bg-slate-50"}`} key={label}>
              <dt className={`text-[10px] font-black uppercase tracking-wide ${isPeriod ? "text-emerald-800" : "text-slate-400"}`}>{label}</dt>
              <dd className={`mt-0.5 truncate text-xs font-bold ${isPeriod ? "text-emerald-950" : "text-slate-800"}`} title={value}>{value}</dd>
            </div>
          );
        })}
      </div>
      {existing && (
        <p className="mt-1.5 rounded-md bg-amber-50 px-2 py-1 text-[11px] font-semibold text-amber-900">
          Período já existente: novos bancos ou áreas entram no mesmo processo. Itens já iniciados devem ser revisados pela conciliação normal.
        </p>
      )}
    </section>
  );
}

function GuidedPanel({ title, action, loading, children }: { title: string; action?: ReactNode; loading?: boolean; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-2.5 shadow-sm">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-bold">{title}</h2>
        <div className="flex items-center gap-2">{loading && <Loader2 size={16} className="animate-spin text-slate-500" />}{action}</div>
      </div>
      {children}
    </section>
  );
}

function EmptyAction({ text, onClick, href }: { text: string; onClick?: () => void; href?: string }) {
  const className = "inline-flex items-center gap-2 rounded-md bg-teal-700 px-3 py-1.5 text-xs font-bold text-white hover:bg-teal-800";
  return (
    <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-3 text-center text-sm text-slate-600">
      <p className="mb-2 font-semibold">{text}</p>
      {href ? <Link href={href} className={className}><FolderOpen size={15} />Abrir</Link> : <button onClick={onClick} className={className}>Começar</button>}
    </div>
  );
}

function StatsGrid({ items }: { items: [string, number][] }) {
  return (
    <div className="mb-2 grid gap-1.5 md:grid-cols-3 xl:grid-cols-5">
      {items.map(([label, value]) => (
        <div className="rounded-md border border-slate-200 bg-slate-50 px-2 py-1.5" key={label}>
          <div className="text-base font-bold leading-tight text-slate-900">{value}</div>
          <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">{label}</div>
        </div>
      ))}
    </div>
  );
}

function RuleField({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block text-[10px] font-black uppercase tracking-wide text-slate-500">
      {label}
      <div className="mt-1">{children}</div>
    </label>
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

function MiniTable({ rows, onView, onCreateRule }: { rows: ResultRow[]; onView: (viewer: Viewer) => void; onCreateRule: (row: ResultRow) => void }) {
  if (!rows.length) return <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">Nenhum resultado processado ainda.</div>;
  return (
    <div className="max-h-[calc(100dvh-285px)] overflow-auto rounded-lg border border-slate-200">
      <table className="min-w-full text-xs">
        <thead className="sticky top-0 z-10 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
          <tr><th className="px-3 py-2">Data</th><th className="px-3 py-2">Tipo</th><th className="px-3 py-2">Extrato</th><th className="px-3 py-2">Valor</th><th className="px-3 py-2">Situação</th><th className="px-3 py-2">Regra</th><th className="px-3 py-2">Ações</th></tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr className="border-t border-slate-100" key={index}>
              <td className="whitespace-nowrap px-2 py-1.5 font-mono text-[11px]">{row.data ?? "—"}</td>
              <td className="px-2 py-1.5">{row.tipo_pagamento ?? "—"}</td>
              <td className="max-w-[520px] px-2 py-1.5 text-[11px] text-slate-600">{String(row.extrato ?? "—").split("\n").slice(0, 2).join(" · ")}</td>
              <td className="whitespace-nowrap px-2 py-1.5 font-semibold">{row.valor ?? "—"}</td>
              <td className="px-2 py-1.5 font-semibold">{row.situacao ?? "—"}</td>
              <td className="px-2 py-1.5">{row.fonte_regra ?? "—"} · {row.lancamentos?.length ?? 0} linha(s)</td>
              <td className="whitespace-nowrap px-2 py-1.5">
                {row.extrato_arquivo_id && <button type="button" onClick={() => onView({ arquivoId: row.extrato_arquivo_id!, pagina: Number(row.extrato_pagina || 1), titulo: "Extrato" })} title="Visualizar extrato" aria-label="Visualizar extrato" className="rounded p-1 text-slate-700 hover:bg-slate-100"><Eye size={14} /></button>}
                {row.comprovante_arquivo_id && <button type="button" onClick={() => onView({ arquivoId: row.comprovante_arquivo_id!, pagina: Number(row.comprovante_pagina || 1), titulo: "Comprovante" })} title="Visualizar comprovante" aria-label="Visualizar comprovante" className="rounded p-1 text-teal-700 hover:bg-teal-50"><Eye size={14} /></button>}
                {row.rfb_arquivo_id && <button type="button" onClick={() => onView({ arquivoId: row.rfb_arquivo_id!, pagina: Number(row.rfb_pagina || 1), titulo: "Comprovante RFB" })} title="Visualizar RFB" aria-label="Visualizar RFB" className="rounded p-1 text-violet-700 hover:bg-violet-50"><Eye size={14} /></button>}
                <button type="button" onClick={() => onCreateRule(row)} title="Criar regra a partir deste lançamento" aria-label="Criar regra a partir deste lançamento" className="ml-1 rounded bg-slate-900 px-1.5 py-0.5 text-[10px] font-bold text-white hover:bg-slate-800">Regra</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function NotesReviewTable({ rows, onView }: { rows: unknown[]; onView: (viewer: Viewer) => void }) {
  if (!rows.length) return <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">Nenhuma nota extraída ainda.</div>;
  return (
    <div className="max-h-[calc(100dvh-285px)] overflow-auto rounded-lg border border-slate-200">
      <table className="min-w-full text-sm">
        <thead className="sticky top-0 z-10 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
          <tr><th className="px-3 py-2">Emissão</th><th className="px-3 py-2">Tomador</th><th className="px-3 py-2">Nota</th><th className="px-3 py-2">Pagamento</th><th className="px-3 py-2">Valor</th><th className="px-3 py-2">Doc.</th></tr>
        </thead>
        <tbody>
          {rows.map((raw, index) => {
            const row = raw as Record<string, unknown>;
            const data = row.dados_originais && typeof row.dados_originais === "object" ? row.dados_originais as Record<string, unknown> : {};
            return (
              <tr className="border-t border-slate-100" key={String(row.id ?? index)}>
                <td className="whitespace-nowrap px-3 py-2 font-mono text-xs">{String(row.data_emissao ?? data.data_emissao ?? "—")}</td>
                <td className="max-w-[420px] px-3 py-2 text-xs font-semibold text-slate-700">{String(row.fornecedor ?? row.tomador ?? "—")}</td>
                <td className="whitespace-nowrap px-3 py-2">{String(row.numero_nota ?? data.numero_nota ?? "—")}</td>
                <td className="px-3 py-2">{String(row.tipo_pagamento_label ?? row.tipo_pagamento ?? row.forma_pagamento ?? data.tipo_pagamento_label ?? data.forma_pagamento ?? "—")}</td>
                <td className="whitespace-nowrap px-3 py-2 font-semibold">{String(row.valor_total ?? data.valor_total ?? "—")}</td>
                <td className="whitespace-nowrap px-3 py-2">{Boolean(row.arquivo_id) && <button type="button" onClick={() => onView({ arquivoId: String(row.arquivo_id), pagina: Number(row.pagina || 1), titulo: "Nota fiscal" })} title="Visualizar nota" aria-label="Visualizar nota" className="rounded p-1 text-slate-700 hover:bg-slate-100"><Eye size={14} /></button>}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function PendingRules({ rows, onSelect, onView, showNotePayment = false }: { rows: unknown[]; onSelect: (row: unknown) => void; onView: (viewer: Viewer) => void; showNotePayment?: boolean }) {
  if (!rows.length) return <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">Nenhuma regra pendente para este banco.</div>;
  return (
    <div className="max-h-[calc(100dvh-310px)] space-y-1.5 overflow-y-auto pr-1">
      {rows.slice(0, 24).map((raw, index) => {
        const row = raw as Record<string, unknown>;
        const history = String(row.historico ?? row.gatilho ?? row.texto ?? "—");
        const date = String(row.data ?? row.data_emissao ?? "—");
        const payment = String(row.tipo_pagamento_label ?? row.forma_pagamento ?? "");
        const countText = row.cobertos ? `${String(row.cobertos)} cobertos` : "pendente";
        return (
          <article className="grid gap-2 rounded-lg border border-slate-200 bg-white p-2.5 shadow-sm transition hover:border-teal-300 hover:bg-slate-50 lg:grid-cols-[minmax(0,1fr)_96px_82px]" key={String(row.id ?? index)}>
            <div className="min-w-0">
              <span className="mb-1 inline-flex rounded bg-amber-50 px-1.5 py-0.5 text-[10px] font-black uppercase tracking-wide text-amber-800">{countText}</span>
              <h3 className="line-clamp-2 text-[11px] font-black leading-4 text-slate-800" title={history}>{date} · {history}</h3>
              <p className="mt-0.5 text-[10px] font-semibold text-slate-500">
                Tipo: {String(row.tipo_componente ?? row.tipo_lancamento_label ?? "Principal")}
                {showNotePayment && payment && payment !== "—" ? ` · Pagamento: ${payment}` : ""}
              </p>
            </div>
            <div className="flex items-center justify-between gap-2 rounded-md border border-slate-100 bg-slate-50 px-2 py-1 lg:block">
              <span className="text-[10px] font-black uppercase tracking-wide text-slate-400">Valor</span>
              <strong className="block text-[11px] text-slate-900 lg:mt-0.5">{String(row.valor ?? "—")}</strong>
            </div>
            <div className="flex items-center justify-end gap-1.5">
              {Boolean(row.arquivo_id) && <button type="button" onClick={() => onView({ arquivoId: String(row.arquivo_id), pagina: Number(row.pagina || 1), titulo: "Documento" })} title="Visualizar documento" aria-label="Visualizar documento" className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-slate-200 text-slate-700 hover:bg-slate-50"><Eye size={13} /></button>}
              <button type="button" onClick={() => onSelect(raw)} className="inline-flex h-7 items-center justify-center gap-1 rounded-md bg-slate-900 px-2 text-[11px] font-bold text-white hover:bg-slate-800">
                <WandSparkles size={13} />
                Criar
              </button>
            </div>
          </article>
        );
      })}
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
