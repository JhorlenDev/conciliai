"use client";

import { ChangeEvent, useEffect, useState } from "react";
import { Eye, FileText, Plus, Upload, X } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const banks = ["Banco do Brasil", "Bradesco", "Caixa Econômica Federal", "Itaú", "Santander", "Nubank", "Outro"];
type Client = { id: string; nome: string };
type Row = Record<string, string | null>;
type Review = { extratos: Row[]; comprovantes: Row[]; rfb: Row[]; arquivos: { id: string; nome: string; tipo: string; status: string; erro: string | null }[] };
type Unused = { comprovantes: Row[]; rfb: Row[]; resumo: { comprovantes: Record<string, number>; rfb: Record<string, number> } };
type Viewer = { arquivoId: string; pagina: number; titulo: string };

function PdfModal({ viewer, onClose }: { viewer: Viewer; onClose: () => void }) {
  const url = `${API}/api/arquivos/${viewer.arquivoId}/visualizar#page=${viewer.pagina}`;
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4"><section className="flex h-[90vh] w-full max-w-6xl flex-col overflow-hidden rounded-xl bg-white"><header className="flex items-center justify-between border-b px-4 py-3"><div><strong>{viewer.titulo}</strong><p className="text-xs text-slate-500">Página {viewer.pagina}</p></div><div className="flex gap-2"><a className="rounded border px-3 py-1 text-sm" href={url} target="_blank">Abrir em nova aba</a><button aria-label="Fechar visualizador" title="Fechar" onClick={onClose} className="rounded border p-1"><X size={18}/></button></div></header><iframe title="Documento original" className="min-h-0 flex-1" src={url}/></section></div>
}

function Table({ title, columns, rows, showOrigin = true, onView }: { title: string; columns: string[]; rows: Row[]; showOrigin?: boolean; onView?: (viewer: Viewer) => void }) {
  return <section className="overflow-hidden rounded-xl border border-slate-200 bg-white"><div className="flex items-center justify-between border-b px-5 py-4"><h2 className="font-semibold">{title}</h2><span className="rounded-full bg-slate-100 px-2 py-1 text-xs">{rows.length} registros</span></div><div className="overflow-x-auto"><table className="w-full min-w-[900px] text-left text-xs"><thead className="bg-slate-50 text-[10px] uppercase text-slate-500"><tr>{columns.map(column => <th className="px-2 py-2" key={column}>{column}</th>)}{showOrigin && <th className="px-2 py-2">Origem</th>}{onView && <th className="px-2 py-2">Ações</th>}</tr></thead><tbody>{rows.length ? rows.map((row, index) => <tr className="border-t align-top" key={row.id ?? index}>{columns.map(column => <td className="max-w-72 px-2 py-2" key={column}>{row[column.toLowerCase().replaceAll(" ", "_")] || "—"}</td>)}{showOrigin && <td className="px-2 py-2 text-slate-500">p. {row.pagina}</td>}{onView && <td className="px-2 py-2">{row.arquivo_id && <button aria-label="Visualizar documento original" title="Visualizar documento original" onClick={() => onView({ arquivoId: String(row.arquivo_id), pagina: Number(row.pagina || 1), titulo: title })}><Eye size={16}/></button>}</td>}</tr>) : <tr><td className="px-2 py-8 text-slate-500" colSpan={columns.length + Number(showOrigin) + Number(Boolean(onView))}>Nenhum registro extraído.</td></tr>}</tbody></table></div></section>
}

function ResultTable({ rows, onView }: { rows: Row[]; onView: (viewer: Viewer) => void }) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const reconciliationClass = (value: string | null) => String(value ?? "").startsWith("Conciliado") ? "bg-emerald-100 text-emerald-800" : String(value ?? "").startsWith("Extrato +") || String(value ?? "").includes("Possível") ? "bg-amber-100 text-amber-800" : "bg-red-100 text-red-800";
  const movementTag = (value: string | null) => {
    const text = String(value ?? "").toUpperCase();
    if (text.includes("TARIFA")) return ["Tarifa", "bg-slate-200 text-slate-700", "border-l-slate-400", "bg-slate-50"];
    if (text.includes("COBRANÇA")) return ["Cobrança", "bg-sky-100 text-sky-800", "border-l-sky-400", "bg-sky-50"];
    if (text.includes("SEG CRÉD") || text.includes("SEGURO")) return ["Seguro", "bg-violet-100 text-violet-800", "border-l-violet-400", "bg-violet-50"];
    if (text.includes("RENDE FÁCIL") || text.includes("RENDIMENTO")) return ["Rendimento", "bg-teal-100 text-teal-800", "border-l-teal-400", "bg-teal-50"];
    if (text.includes("PIX")) return ["PIX", "bg-emerald-100 text-emerald-800", "border-l-emerald-400", "bg-emerald-50"];
    if (text.includes("TED") || text.includes("TRANSFERÊNCIA")) return ["Transferência", "bg-orange-100 text-orange-800", "border-l-orange-400", "bg-orange-50"];
    if (text.includes("BOLETO")) return ["Boleto", "bg-amber-100 text-amber-800", "border-l-amber-400", "bg-amber-50"];
    if (text.includes("IMPOSTO") || text.includes("DAS")) return ["Imposto", "bg-rose-100 text-rose-800", "border-l-rose-400", "bg-rose-50"];
    if (text.includes("CARTÃO")) return ["Cartão", "bg-indigo-100 text-indigo-800", "border-l-indigo-400", "bg-indigo-50"];
    return null;
  };
  const eye = (file: string | null, page: string | null, title: string) => file && <button aria-label="Visualizar documento original" title="Visualizar documento original" onClick={() => onView({ arquivoId: file, pagina: Number(page || 1), titulo: title })} className="ml-2 inline-flex rounded border border-slate-300 bg-white/70 p-1"><Eye size={14}/></button>;
  return <section className="overflow-hidden rounded-xl border border-slate-200 bg-white"><div className="flex items-center justify-between border-b px-5 py-4"><h2 className="font-semibold">Resultado da conciliação</h2><span className="rounded-full bg-slate-100 px-2 py-1 text-xs">{rows.length} movimentos</span></div><div className="overflow-x-auto"><table className="w-full min-w-[1180px] text-left text-xs"><thead className="bg-slate-50 text-[10px] uppercase text-slate-500"><tr>{["Data", "Tipo de pagamento", "Extrato", "Comprovante bancário", "Comprovante RFB", "Valor", "Fonte", "Situação", ""].map(item => <th className="px-3 py-2" key={item}>{item}</th>)}</tr></thead><tbody>{rows.map(row => { const tag = movementTag(row.extrato); return <><tr className={`border-t border-l-4 align-top ${tag?.[3] ?? "bg-white"} ${tag?.[2] ?? "border-l-transparent"}`} key={String(row.id)}><td className="whitespace-nowrap px-3 py-3 font-medium">{row.data}</td><td className="px-3 py-3">{row.tipo_pagamento}</td><td className="whitespace-pre-line px-3 py-3">{row.extrato}{eye(row.extrato_arquivo_id, row.extrato_pagina, "Extrato bancário")}</td><td className="whitespace-pre-line px-3 py-3">{row.comprovante_bancario}{eye(row.comprovante_arquivo_id, row.comprovante_pagina, "Comprovante bancário")}</td><td className="whitespace-pre-line px-3 py-3">{row.comprovante_rfb}{eye(row.rfb_arquivo_id, row.rfb_pagina, "Comprovante RFB")}</td><td className="whitespace-nowrap px-3 py-3">{row.valor}</td><td className="px-3 py-3">{row.fonte_regra}</td><td className="px-3 py-3"><span className={`rounded-full px-2 py-1 text-[10px] font-medium ${reconciliationClass(row.situacao)}`}>{row.situacao}</span></td><td className="px-3 py-3"><button onClick={() => setExpanded(expanded === row.id ? null : String(row.id))} className="rounded border border-slate-300 bg-white/70 px-2 py-1">{expanded === row.id ? "Fechar" : "Detalhes"}</button></td></tr>{expanded === row.id && <tr className={`border-t ${tag?.[3] ?? "bg-white"}`} key={`${row.id}-details`}><td className="px-3 py-3 text-slate-600" colSpan={9}>Confiança: {row.confianca} | Total dos lançamentos: {row.total_lancamentos} | Diferença: {row.diferenca}</td></tr>}</>})}</tbody></table></div></section>
}

export default function Home() {
  const [clients, setClients] = useState<Client[]>([]), [clientId, setClientId] = useState(""), [newClient, setNewClient] = useState("");
  const [bank, setBank] = useState(banks[0]), [start, setStart] = useState(""), [end, setEnd] = useState(""), [reconciliationId, setReconciliationId] = useState("");
  const [review, setReview] = useState<Review>({ extratos: [], comprovantes: [], rfb: [], arquivos: [] }), [results, setResults] = useState<Row[]>([]), [unused, setUnused] = useState<Unused>({ comprovantes: [], rfb: [], resumo: { comprovantes: {}, rfb: {} } }), [viewer, setViewer] = useState<Viewer | null>(null), [message, setMessage] = useState("");
  useEffect(() => { fetch(`${API}/api/clientes`).then(r => r.json()).then(setClients).catch(() => setMessage("Backend indisponível.")); }, []);
  async function createClient() { const response = await fetch(`${API}/api/clientes`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ nome: newClient }) }); const client = await response.json(); setClients(items => [...items, client]); setClientId(client.id); setNewClient(""); }
  async function createReconciliation() { const response = await fetch(`${API}/api/conciliacoes`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ cliente_id: clientId, banco: bank, data_inicio: start, data_fim: end }) }); if (!response.ok) return setMessage("Preencha cliente e período corretamente."); const data = await response.json(); setReconciliationId(data.id); setMessage("Conciliação criada. Envie os documentos."); }
  async function upload(type: string, event: ChangeEvent<HTMLInputElement>) {
    const files = event.target.files;
    if (!files || !reconciliationId) return;
    try {
      for (const file of Array.from(files)) {
        const form = new FormData();
        form.append("file", file);
        const response = await fetch(`${API}/api/conciliacoes/${reconciliationId}/arquivos?tipo_documento=${type}`, { method: "POST", body: form });
        if (!response.ok) throw new Error((await response.json()).detail ?? "Não foi possível enviar o PDF.");
      }
      const response = await fetch(`${API}/api/conciliacoes/${reconciliationId}/revisao`);
      if (!response.ok) throw new Error("Não foi possível atualizar os dados extraídos.");
      setReview(await response.json());
      setMessage(`${files.length} arquivo(s) enviado(s) e processado(s).`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Falha no envio do arquivo.");
    } finally {
      event.target.value = "";
    }
  }
  async function reprocessDocument(fileId: string) {
    try {
      const response = await fetch(`${API}/api/arquivos/${fileId}/reprocessar`, { method: "POST" });
      if (!response.ok) throw new Error((await response.json()).detail ?? "Não foi possível reprocessar o extrato.");
      const result = await response.json();
      const reviewResponse = await fetch(`${API}/api/conciliacoes/${reconciliationId}/revisao`);
      setReview(await reviewResponse.json());
      setMessage(`Documento reprocessado: ${result.registros_extraidos} registros encontrados.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Falha no reprocessamento.");
    }
  }
  async function reconcileDocuments() {
    try {
      const response = await fetch(`${API}/api/conciliacoes/${reconciliationId}/conciliar`, { method: "POST" });
      if (!response.ok) throw new Error((await response.json()).detail ?? "Não foi possível conciliar.");
      const data = await fetch(`${API}/api/conciliacoes/${reconciliationId}/resultado`).then(item => item.json());
      setResults(data);
      setUnused(await fetch(`${API}/api/conciliacoes/${reconciliationId}/documentos-nao-utilizados`).then(item => item.json()));
      setMessage("Conciliação concluída. Revise os resultados.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Falha na conciliação.");
    }
  }
  return <main className="mx-auto max-w-7xl px-4 py-8 sm:px-8"><header className="mb-8 flex items-center gap-3"><div className="rounded-lg bg-teal-700 p-2 text-white"><FileText size={24}/></div><div><h1 className="text-xl font-bold">Conciliaí</h1><p className="text-sm text-slate-500">Conciliação bancária documental</p></div></header>
    <div className="mb-8 grid gap-2 text-sm sm:grid-cols-5">{["1. Cliente e banco", "2. Upload", "3. Extração e revisão", "4. Conciliação", "5. Resultado"].map((item, i) => <div className={`rounded-lg px-3 py-2 ${i < (reconciliationId ? 3 : 1) ? "bg-teal-700 text-white" : "bg-white text-slate-500"}`} key={item}>{item}</div>)}</div>
    <section className="rounded-xl border border-slate-200 bg-white p-5"><h2 className="mb-4 font-semibold">Cliente, banco e período</h2><div className="grid gap-3 md:grid-cols-4"><select value={clientId} onChange={e => setClientId(e.target.value)} className="rounded-md border p-2"><option value="">Selecione um cliente</option>{clients.map(client => <option value={client.id} key={client.id}>{client.nome}</option>)}</select><input value={newClient} onChange={e => setNewClient(e.target.value)} className="rounded-md border p-2" placeholder="Novo cliente"/><button onClick={createClient} disabled={!newClient} className="rounded-md border px-3 disabled:opacity-40"><Plus className="mr-1 inline" size={16}/>Cadastrar</button><select value={bank} onChange={e => setBank(e.target.value)} className="rounded-md border p-2">{banks.map(item => <option key={item}>{item}</option>)}</select><input type="date" value={start} onChange={e => setStart(e.target.value)} className="rounded-md border p-2"/><input type="date" value={end} onChange={e => setEnd(e.target.value)} className="rounded-md border p-2"/><button onClick={createReconciliation} className="rounded-md bg-teal-700 px-4 py-2 font-medium text-white">Criar conciliação</button></div></section>
    {reconciliationId && <section className="my-6 grid gap-4 md:grid-cols-3">{[["extrato", "Extrato bancário", false], ["comprovante", "Comprovantes bancários", true], ["rfb", "Comprovantes da Receita Federal", true]].map(([type, label, multiple]) => <label className="cursor-pointer rounded-xl border-2 border-dashed border-slate-300 bg-white p-5 text-center hover:border-teal-600" key={String(type)}><Upload className="mx-auto mb-2 text-teal-700"/><strong className="block">{String(label)}</strong><span className="mt-1 block text-xs text-slate-500">{type === "rfb" ? "Envie comprovantes de arrecadação DARF e DAS emitidos pela Receita Federal." : `PDF${multiple ? "s" : ""} com texto selecionável`}</span><input className="hidden" type="file" accept="application/pdf" multiple={Boolean(multiple)} onChange={event => upload(String(type), event)}/></label>)}</section>}
    {message && <p className="mb-5 rounded-md bg-teal-50 p-3 text-sm text-teal-900">{message}</p>}
    {reconciliationId && <section className="mb-5 overflow-hidden rounded-xl border border-slate-200 bg-white"><div className="flex items-center justify-between border-b px-5 py-4"><h2 className="font-semibold">Arquivos enviados</h2><span className="rounded-full bg-slate-100 px-2 py-1 text-xs">{review.arquivos.length} arquivos</span></div><div className="overflow-x-auto"><table className="w-full min-w-[560px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr><th className="px-4 py-3">Arquivo</th><th className="px-4 py-3">Tipo</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Ação</th><th className="px-4 py-3">Erro de extração</th></tr></thead><tbody>{review.arquivos.length ? review.arquivos.map(file => <tr className="border-t" key={file.id}><td className="px-4 py-3">{file.nome}</td><td className="px-4 py-3">{file.tipo.replaceAll("_", " ")}</td><td className="px-4 py-3">{file.status}</td><td className="px-4 py-3">{["extrato", "comprovante", "rfb"].includes(file.tipo) && <button onClick={() => reprocessDocument(file.id)} className="rounded border px-2 py-1 text-xs">Reprocessar</button>}</td><td className="px-4 py-3 text-red-700">{file.erro || "—"}</td></tr>) : <tr><td className="px-4 py-8 text-slate-500" colSpan={5}>Nenhum arquivo enviado.</td></tr>}</tbody></table></div></section>}
    {reconciliationId && <div className="space-y-5"><Table title="Lançamentos do extrato" columns={["Data", "Hora", "Historico", "Valor", "Natureza"]} rows={review.extratos} onView={setViewer}/><Table title="Comprovantes bancários" columns={["Data", "Hora", "Favorecido", "Valor original", "Ajustes", "Valor pago", "Tipo"]} rows={review.comprovantes} onView={setViewer}/><Table title="Comprovantes da Receita Federal" columns={["Tipo", "Competencia apuracao", "Data arrecadacao", "Documento", "Banco", "Principal", "Multa juros", "Total", "Situacao"]} rows={review.rfb} onView={setViewer}/>{review.extratos.length > 0 && <button onClick={reconcileDocuments} className="rounded-md bg-teal-700 px-4 py-2 font-medium text-white">Conciliar</button>}{results.length > 0 && <><ResultTable rows={results} onView={setViewer}/><section className="grid gap-3 md:grid-cols-2"><div className="rounded-xl border bg-white p-4 text-sm"><strong>Resumo dos comprovantes bancários</strong><p>Total: {unused.resumo.comprovantes.total ?? 0} | Utilizados: {unused.resumo.comprovantes.utilizados ?? 0} | Não utilizados: {unused.resumo.comprovantes.nao_utilizados ?? 0} | Fora do período: {unused.resumo.comprovantes.fora_periodo ?? 0}</p></div><div className="rounded-xl border bg-white p-4 text-sm"><strong>Resumo dos comprovantes RFB</strong><p>Total: {unused.resumo.rfb.total ?? 0} | Utilizados: {unused.resumo.rfb.utilizados ?? 0} | Não utilizados: {unused.resumo.rfb.nao_utilizados ?? 0} | Fora do período: {unused.resumo.rfb.fora_periodo ?? 0}</p></div></section><Table title="Comprovantes bancários não utilizados" columns={["Data", "Hora", "Favorecido", "Valor pago", "Tipo", "Situacao"]} rows={unused.comprovantes} showOrigin={false}/><Table title="Comprovantes RFB não utilizados" columns={["Tipo", "Data arrecadacao", "Documento", "Banco", "Total", "Situacao"]} rows={unused.rfb} showOrigin={false}/></>}</div>}{viewer && <PdfModal viewer={viewer} onClose={() => setViewer(null)}/>}
  </main>;
}
