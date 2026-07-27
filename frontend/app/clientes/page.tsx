"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
type Client = { id: string; nome: string; documento: string | null };

export default function ClientesPage() {
  const [clients, setClients] = useState<Client[]>([]), [name, setName] = useState(""), [document, setDocument] = useState(""), [message, setMessage] = useState("");
  useEffect(() => { fetch(`${API}/api/clientes`).then(response => response.json()).then(setClients).catch(() => setMessage("Não foi possível carregar clientes.")); }, []);
  async function createClient() {
    const response = await fetch(`${API}/api/clientes`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ nome: name, documento: document || null }) });
    if (!response.ok) return setMessage("Não foi possível cadastrar o cliente.");
    const client = await response.json(); setClients(items => [...items, client]); setName(""); setDocument(""); setMessage("Cliente cadastrado.");
  }
  return <main className="min-h-screen bg-slate-100"><header className="bg-emerald-800 px-6 py-3 text-white"><Link href="/" className="text-lg font-bold">Conciliaí</Link><p className="text-xs text-emerald-100">Cadastro de clientes</p></header><section className="mx-auto max-w-5xl px-6 py-10"><div className="grid gap-6 lg:grid-cols-[0.8fr_1.2fr]"><form onSubmit={event => { event.preventDefault(); createClient(); }} className="rounded-xl border bg-white p-5"><h1 className="text-lg font-bold text-emerald-900">Novo cliente</h1><input required value={name} onChange={event => setName(event.target.value)} className="mt-4 w-full rounded border p-2" placeholder="Nome ou razão social"/><input value={document} onChange={event => setDocument(event.target.value)} className="mt-3 w-full rounded border p-2" placeholder="CPF ou CNPJ (opcional)"/><button className="mt-4 rounded bg-emerald-800 px-4 py-2 text-sm font-semibold text-white">Cadastrar cliente</button>{message && <p className="mt-3 text-sm text-slate-600">{message}</p>}</form><section className="overflow-hidden rounded-xl border bg-white"><header className="border-b px-5 py-4"><h2 className="font-semibold">Clientes cadastrados</h2></header><table className="w-full text-left text-sm"><thead className="bg-slate-50 text-xs text-slate-500"><tr><th className="px-5 py-3">Nome</th><th className="px-5 py-3">CPF/CNPJ</th></tr></thead><tbody>{clients.map(client => <tr className="border-t" key={client.id}><td className="px-5 py-3">{client.nome}</td><td className="px-5 py-3">{client.documento || "—"}</td></tr>)}</tbody></table></section></div></section></main>;
}
