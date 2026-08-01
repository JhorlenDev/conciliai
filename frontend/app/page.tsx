"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, Building2, Clock3, FileText, Plus, RefreshCw, Trash2, Users, X } from "lucide-react";

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
type BankReconciliation = { id: string; banco: string; status: string };
type Process = {
  id: string;
  cliente_id: string;
  cliente_nome: string;
  data_inicio: string;
  data_fim: string;
  criado_em: string;
  status: string;
  bancos: BankReconciliation[];
};

export default function EntryPage() {
  const [clients, setClients] = useState<Client[]>([]),
    [processes, setProcesses] = useState<Process[]>([]);
  const [clientId, setClientId] = useState(""),
    [start, setStart] = useState(""),
    [end, setEnd] = useState(""),
    [bank, setBank] = useState(banks[0]),
    [message, setMessage] = useState(""),
    [processToDelete, setProcessToDelete] = useState<Process | null>(null),
    [isDeleting, setIsDeleting] = useState(false),
    [now, setNow] = useState<Date | null>(null);
  async function load() {
    try {
      const [clientResponse, processResponse] = await Promise.all([
        fetch(`${API}/api/clientes`),
        fetch(`${API}/api/processos-conciliacao`),
      ]);
      if (!clientResponse.ok || !processResponse.ok) throw new Error();
      setClients(await clientResponse.json());
      setProcesses(await processResponse.json());
    } catch {
      setMessage("Não foi possível carregar a Central de Conciliações.");
    }
  }
  useEffect(() => {
    load();
  }, []);
  useEffect(() => {
    const update = () => setNow(new Date());
    update();
    const timer = window.setInterval(update, 1_000);
    return () => window.clearInterval(timer);
  }, []);
  async function create(event: FormEvent) {
    event.preventDefault();
    setMessage("");
    const response = await fetch(`${API}/api/processos-conciliacao`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        cliente_id: clientId,
        data_inicio: start,
        data_fim: end,
        banco: bank,
      }),
    });
    if (!response.ok)
      return setMessage(
        (await response.json()).detail ??
          "Preencha cliente e período corretamente.",
      );
    const process = (await response.json()) as Process;
    window.location.assign(`/conciliacao?process=${process.id}`);
  }
  function open(process: Process) {
    window.location.assign(`/conciliacao?process=${process.id}`);
  }
  async function removeProcess() {
    if (!processToDelete) return;
    setIsDeleting(true);
    setMessage("");
    try {
      const response = await fetch(`${API}/api/processos-conciliacao/${processToDelete.id}`, { method: "DELETE" });
      if (!response.ok) throw new Error((await response.json()).detail ?? "Não foi possível excluir o processo.");
      setProcesses((items) => items.filter((item) => item.id !== processToDelete.id));
      setProcessToDelete(null);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Não foi possível excluir o processo.");
    } finally {
      setIsDeleting(false);
    }
  }
  const date = (value: string) =>
    new Date(`${value}T00:00:00`).toLocaleDateString("pt-BR");
  const month = (value: string) => {
    const label = new Date(`${value}T00:00:00`).toLocaleDateString("pt-BR", { month: "long", year: "numeric" });
    return label.charAt(0).toUpperCase() + label.slice(1);
  };
  const orderedProcesses = [...processes].sort((left, right) =>
    left.data_inicio.localeCompare(right.data_inicio),
  );
  const dateTime = (value: string) =>
    new Date(value).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
  return (
    <main className="min-h-screen bg-slate-100 text-slate-800">
      <header className="border-b border-emerald-900 bg-emerald-800 px-6 py-5 text-white">
        <div className="mx-auto flex max-w-6xl items-center gap-3">
          <Building2 />
          <div>
            <h1 className="text-xl font-bold">Central de Conciliações</h1>
            <p className="text-sm text-emerald-100">
              Processos por cliente e período, com progresso persistente por
              banco.
            </p>
          </div>
          <nav className="ml-auto flex items-center gap-2 text-sm" aria-label="Navegação principal">
            <Link href="/clientes" className="inline-flex items-center gap-1 rounded px-2 py-1 hover:bg-emerald-700"><Users size={15}/>Clientes</Link>
            <Link href="/documentos" className="inline-flex items-center gap-1 rounded px-2 py-1 hover:bg-emerald-700"><FileText size={15}/>Documentos</Link>
          </nav>
          {now && <div className="hidden items-center gap-2 rounded-md border border-emerald-700 bg-emerald-900/30 px-3 py-1.5 text-right leading-tight text-emerald-50 sm:flex"><Clock3 size={20}/><span><strong className="block text-sm font-semibold">{now.toLocaleDateString("pt-BR", { weekday: "short", day: "numeric", month: "short", year: "numeric" })}</strong><span className="text-xs">{now.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</span></span></div>}
        </div>
      </header>
      <div className="mx-auto grid max-w-6xl gap-6 px-5 py-7 lg:grid-cols-[360px_1fr]">
        <form
          onSubmit={create}
          className="h-fit rounded-xl border border-emerald-200 bg-white p-5 shadow-sm"
        >
          <h2 className="flex items-center gap-2 font-bold text-emerald-900">
            <Plus size={18} />
            Nova conciliação
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Crie um processo e inicie pelo primeiro banco.
          </p>
          <label className="mt-4 block text-sm font-medium">
            Cliente
            <select
              required
              value={clientId}
              onChange={(event) => setClientId(event.target.value)}
              className="mt-1 w-full rounded border p-2"
            >
              <option value="">Selecionar cliente</option>
              {clients.map((client) => (
                <option value={client.id} key={client.id}>
                  {client.nome}
                </option>
              ))}
            </select>
          </label>
          <div className="mt-3 grid grid-cols-2 gap-3">
            <label className="text-sm font-medium">
              Início
              <input
                required
                type="date"
                value={start}
                onChange={(event) => setStart(event.target.value)}
                className="mt-1 w-full rounded border p-2"
              />
            </label>
            <label className="text-sm font-medium">
              Fim
              <input
                required
                type="date"
                value={end}
                onChange={(event) => setEnd(event.target.value)}
                className="mt-1 w-full rounded border p-2"
              />
            </label>
          </div>
          <label className="mt-3 block text-sm font-medium">
            Primeiro banco
            <select
              value={bank}
              onChange={(event) => setBank(event.target.value)}
              className="mt-1 w-full rounded border p-2"
            >
              {banks.map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>
          </label>
          <button className="mt-5 w-full rounded bg-emerald-800 px-4 py-2 font-semibold text-white">
            Criar e continuar
          </button>
          {message && <p className="mt-3 text-sm text-red-700">{message}</p>}
        </form>
        <section>
          <div className="mb-3 flex items-center justify-between">
            <div>
              <h2 className="font-bold">Processos ativos e concluídos</h2>
              <p className="text-sm text-slate-500">
                Abra um processo para retomar exatamente de onde parou.
              </p>
            </div>
            <button
              aria-label="Atualizar processos"
              onClick={load}
              className="rounded border bg-white p-2"
            >
              <RefreshCw size={16} />
            </button>
          </div>
           <div className="grid gap-2 md:grid-cols-2">
             {orderedProcesses.map((process) => (
                <article className="flex min-w-0 items-center rounded-lg border bg-white shadow-sm transition hover:border-emerald-700 hover:shadow-md" key={process.id}>
                  <button type="button" onClick={() => open(process)} className="flex min-w-0 flex-1 items-center justify-between p-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-700 focus-visible:ring-inset">
                   <div>
                     <h3 className="text-sm font-semibold">{process.cliente_nome}</h3>
                     <p className="mt-0.5 text-xs font-medium text-emerald-800">{month(process.data_inicio)}</p>
                     <p className="text-xs text-slate-500">
                       {date(process.data_inicio)} - {date(process.data_fim)}
                     </p>
                     <p className="mt-0.5 text-[10px] text-slate-400">Criado em: {dateTime(process.criado_em)}</p>
                   </div>
                   <ArrowRight size={16} className="shrink-0 text-emerald-800" aria-hidden="true" />
                   </button>
                  <button type="button" onClick={() => setProcessToDelete(process)} aria-label={`Excluir processo de ${process.cliente_nome}`} title="Excluir processo" className="mr-2 rounded-md p-1.5 text-slate-500 hover:bg-red-50 hover:text-red-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-600"><Trash2 size={15}/></button>
                </article>
            ))}
            {!processes.length && (
              <div className="rounded-xl border border-dashed bg-white p-10 text-center text-sm text-slate-500">
                Nenhum processo ainda. Crie a primeira conciliação.
              </div>
            )}
          </div>
        </section>
      </div>
      {processToDelete && <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4" role="presentation"><section role="dialog" aria-modal="true" aria-labelledby="delete-process-title" className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl"><div className="flex items-start justify-between gap-4"><div><h2 id="delete-process-title" className="text-lg font-bold text-slate-900">Excluir processo?</h2><p className="mt-2 text-sm text-slate-600">Tem certeza que deseja excluir o processo de <strong>{processToDelete.cliente_nome}</strong>?</p><p className="mt-2 text-sm font-semibold text-red-700">Esta operação não poderá ser desfeita.</p></div><button type="button" onClick={() => setProcessToDelete(null)} disabled={isDeleting} aria-label="Fechar confirmação" className="rounded p-1 text-slate-500 hover:bg-slate-100"><X size={20}/></button></div><div className="mt-6 flex justify-end gap-3"><button type="button" onClick={() => setProcessToDelete(null)} disabled={isDeleting} className="rounded-md border px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">Cancelar</button><button type="button" onClick={removeProcess} disabled={isDeleting} className="rounded-md bg-red-700 px-4 py-2 text-sm font-semibold text-white hover:bg-red-800 disabled:cursor-wait disabled:opacity-60">{isDeleting ? "Excluindo..." : "Excluir processo"}</button></div></section></div>}
    </main>
  );
}
