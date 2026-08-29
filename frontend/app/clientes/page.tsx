"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Building2, Pencil, Plus, Trash2, X } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
type Client = { id: string; nome: string; documento: string | null };
type BankAccount = { id: string; banco: string; agencia: string; conta: string; titular: string; conta_contabil: string };
const banks = ["Banco do Brasil", "Santander", "BASA", "Bradesco", "Caixa", "Conta Caixa", "Apropriações", "Empréstimos/Financiamentos", "Folha de Pagamento"];

export default function ClientesPage() {
  const [clients, setClients] = useState<Client[]>([]),
    [name, setName] = useState(""),
    [document, setDocument] = useState(""),
    [message, setMessage] = useState(""),
    [editing, setEditing] = useState<string | null>(null),
    [draft, setDraft] = useState({ nome: "", documento: "" }),
    [bankClient, setBankClient] = useState<Client | null>(null),
    [bankAccounts, setBankAccounts] = useState<BankAccount[]>([]),
    [bankDraft, setBankDraft] = useState({ banco: banks[0], agencia: "", conta: "", titular: "" }),
    [bankMessage, setBankMessage] = useState("");
  useEffect(() => {
    fetch(`${API}/api/clientes`)
      .then((response) => response.json())
      .then(setClients)
      .catch(() => setMessage("Não foi possível carregar clientes."));
  }, []);
  async function createClient() {
    const response = await fetch(`${API}/api/clientes`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nome: name, documento: document || null }),
    });
    if (!response.ok)
      return setMessage("Não foi possível cadastrar o cliente.");
    const client = await response.json();
    setClients((items) => [...items, client]);
    setName("");
    setDocument("");
    setMessage("Cliente cadastrado.");
  }
  function beginEdit(client: Client) {
    setEditing(client.id);
    setDraft({ nome: client.nome, documento: client.documento || "" });
  }
  async function saveClient(client: Client) {
    const response = await fetch(`${API}/api/clientes/${client.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        nome: draft.nome,
        documento: draft.documento || null,
      }),
    });
    if (!response.ok)
      return setMessage("Não foi possível atualizar o cliente.");
    const updated = await response.json();
    setClients((items) =>
      items.map((item) => (item.id === updated.id ? updated : item)),
    );
    setEditing(null);
    setMessage("Cliente atualizado.");
  }
  async function removeClient(client: Client) {
    if (!confirm(`Excluir ${client.nome}?`)) return;
    const response = await fetch(`${API}/api/clientes/${client.id}`, {
      method: "DELETE",
    });
    if (!response.ok)
      return setMessage(
        (await response.json()).detail || "Não foi possível excluir o cliente.",
      );
    setClients((items) => items.filter((item) => item.id !== client.id));
    setMessage("Cliente excluído.");
  }
  async function openBankAccounts(client: Client) {
    setBankClient(client);
    setBankMessage("");
    setBankDraft({ banco: banks[0], agencia: "", conta: "", titular: client.nome });
    const response = await fetch(`${API}/api/clientes/${client.id}/contas-bancarias`);
    if (!response.ok) return setBankMessage("Não foi possível carregar as contas bancárias.");
    setBankAccounts(await response.json());
  }
  function editBankAccount(account: BankAccount) {
    setBankDraft({ banco: account.banco, agencia: account.agencia, conta: account.conta, titular: account.titular });
    setBankMessage("");
  }
  async function saveBankAccount() {
    if (!bankClient) return;
    const response = await fetch(`${API}/api/clientes/${bankClient.id}/contas-bancarias/${encodeURIComponent(bankDraft.banco)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ agencia: bankDraft.agencia, conta: bankDraft.conta, titular: bankDraft.titular }),
    });
    if (!response.ok) {
      const error = await response.json();
      return setBankMessage(error.detail || "Não foi possível salvar a conta bancária.");
    }
    const saved = await response.json() as BankAccount;
    setBankAccounts((accounts) => [...accounts.filter((account) => account.banco !== saved.banco), saved].sort((left, right) => left.banco.localeCompare(right.banco)));
    setBankDraft({ banco: banks[0], agencia: "", conta: "", titular: bankClient.nome });
    setBankMessage("Conta bancária salva.");
  }
  async function removeBankAccount(account: BankAccount) {
    if (!bankClient || !confirm(`Excluir a conta ${account.conta} do ${account.banco}?`)) return;
    const response = await fetch(`${API}/api/clientes/${bankClient.id}/contas-bancarias/${encodeURIComponent(account.banco)}`, { method: "DELETE" });
    if (!response.ok) return setBankMessage("Não foi possível excluir a conta bancária.");
    setBankAccounts((accounts) => accounts.filter((item) => item.banco !== account.banco));
    if (bankDraft.banco === account.banco) setBankDraft({ banco: banks[0], agencia: "", conta: "", titular: bankClient.nome });
  }
  return (
    <main className="min-h-screen bg-slate-100">
      <header className="bg-emerald-800 px-6 py-3 text-white">
        <Link href="/" className="text-lg font-bold">
          Concil<span className="inline-block text-[1.18em] leading-none">IA</span>
        </Link>
        <p className="text-xs text-emerald-100">Cadastro de clientes</p>
      </header>
      <section className="mx-auto max-w-5xl px-6 py-10">
        <div className="grid gap-6 lg:grid-cols-[0.8fr_1.2fr]">
          <form
            onSubmit={(event) => {
              event.preventDefault();
              createClient();
            }}
            className="rounded-xl border bg-white p-5"
          >
            <h1 className="text-lg font-bold text-emerald-900">Novo cliente</h1>
            <input
              required
              value={name}
              onChange={(event) => setName(event.target.value)}
              className="mt-4 w-full rounded border p-2"
              placeholder="Nome ou razão social"
            />
            <input
              value={document}
              onChange={(event) => setDocument(event.target.value)}
              className="mt-3 w-full rounded border p-2"
              placeholder="CPF ou CNPJ (opcional)"
            />
            <button className="mt-4 rounded bg-emerald-800 px-4 py-2 text-sm font-semibold text-white">
              Cadastrar cliente
            </button>
            {message && (
              <p className="mt-3 text-sm text-slate-600">{message}</p>
            )}
          </form>
          <section className="overflow-hidden rounded-xl border bg-white">
            <header className="border-b px-5 py-4">
              <h2 className="font-semibold">Clientes cadastrados</h2>
            </header>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[560px] text-left text-sm">
                <thead className="bg-slate-50 text-xs text-slate-500">
                  <tr>
                    <th className="px-5 py-3">Nome</th>
                    <th className="px-5 py-3">CPF/CNPJ</th>
                    <th className="w-px px-5 py-3">Ações</th>
                  </tr>
                </thead>
                <tbody>
                  {clients.map((client) => {
                    const isEditing = editing === client.id;
                    return (
                      <tr className="border-t" key={client.id}>
                        <td className="px-5 py-3">
                          {isEditing ? (
                            <input
                              value={draft.nome}
                              onChange={(event) =>
                                setDraft((item) => ({
                                  ...item,
                                  nome: event.target.value,
                                }))
                              }
                              className="w-full rounded border px-2 py-1"
                            />
                          ) : (
                            client.nome
                          )}
                        </td>
                        <td className="px-5 py-3">
                          {isEditing ? (
                            <input
                              value={draft.documento}
                              onChange={(event) =>
                                setDraft((item) => ({
                                  ...item,
                                  documento: event.target.value,
                                }))
                              }
                              className="w-full rounded border px-2 py-1"
                              placeholder="CPF/CNPJ"
                            />
                          ) : (
                            client.documento || "—"
                          )}
                        </td>
                        <td className="whitespace-nowrap px-5 py-3">
                          {isEditing ? (
                            <>
                              <button
                                onClick={() => saveClient(client)}
                                className="rounded bg-emerald-800 px-2 py-1 text-xs font-semibold text-white"
                              >
                                Salvar
                              </button>
                              <button
                                onClick={() => setEditing(null)}
                                className="ml-1 rounded border p-1 text-slate-600"
                                title="Cancelar"
                              >
                                <X size={15} />
                              </button>
                            </>
                          ) : (
                            <>
                              <button
                                onClick={() => beginEdit(client)}
                                className="rounded border border-emerald-200 p-1 text-emerald-800"
                                title="Editar cliente"
                              >
                                <Pencil size={15} />
                              </button>
                              <button
                                onClick={() => openBankAccounts(client)}
                                className="ml-1 rounded border border-sky-200 p-1 text-sky-800"
                                title="Contas bancárias"
                              >
                                <Building2 size={15} />
                              </button>
                              <button
                                onClick={() => removeClient(client)}
                                className="ml-1 rounded border border-red-200 p-1 text-red-700"
                                title="Excluir cliente"
                              >
                                <Trash2 size={15} />
                              </button>
                            </>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      </section>
      {bankClient && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4">
          <section className="w-full max-w-3xl overflow-hidden rounded-xl bg-white shadow-2xl">
            <header className="flex items-start justify-between bg-emerald-800 px-5 py-4 text-white">
              <div>
                <div className="flex items-center gap-2"><Building2 size={18} /><h2 className="font-semibold">Contas bancárias</h2></div>
                <p className="mt-1 text-xs text-emerald-100">{bankClient.nome}</p>
              </div>
              <button onClick={() => setBankClient(null)} className="rounded p-1 hover:bg-emerald-700" title="Fechar"><X size={18} /></button>
            </header>
            <div className="space-y-5 p-5">
              <section className="rounded-lg border border-emerald-100 bg-emerald-50/50 p-4">
                <div className="mb-3 flex items-center gap-2"><Plus size={16} className="text-emerald-800" /><h3 className="text-sm font-semibold text-emerald-900">Adicionar ou atualizar conta</h3></div>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  <label className="text-xs font-medium text-slate-600">Banco<select value={bankDraft.banco} onChange={(event) => setBankDraft((item) => ({ ...item, banco: event.target.value }))} className="mt-1 w-full rounded border bg-white p-2 text-sm text-slate-800">{banks.map((bank) => <option key={bank}>{bank}</option>)}</select></label>
                  <label className="text-xs font-medium text-slate-600">Agência<input value={bankDraft.agencia} onChange={(event) => setBankDraft((item) => ({ ...item, agencia: event.target.value }))} className="mt-1 w-full rounded border bg-white p-2 text-sm text-slate-800" placeholder="0000-0" /></label>
                  <label className="text-xs font-medium text-slate-600">Conta<input value={bankDraft.conta} onChange={(event) => setBankDraft((item) => ({ ...item, conta: event.target.value }))} className="mt-1 w-full rounded border bg-white p-2 text-sm text-slate-800" placeholder="00000-0" /></label>
                  <label className="text-xs font-medium text-slate-600">Titular<input value={bankDraft.titular} onChange={(event) => setBankDraft((item) => ({ ...item, titular: event.target.value }))} className="mt-1 w-full rounded border bg-white p-2 text-sm text-slate-800" placeholder="Nome do titular" /></label>
                </div>
                <button onClick={saveBankAccount} className="mt-4 rounded bg-emerald-800 px-3 py-2 text-xs font-semibold text-white">Salvar conta</button>
                {bankMessage && <p className="mt-3 text-sm text-slate-600">{bankMessage}</p>}
              </section>
              <section>
                <div className="mb-2 flex items-center justify-between"><h3 className="text-sm font-semibold text-slate-800">Contas cadastradas</h3><span className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-600">{bankAccounts.length}</span></div>
                {bankAccounts.length === 0 ? <p className="rounded-lg border border-dashed p-5 text-center text-sm text-slate-500">Nenhuma conta bancária cadastrada para este cliente.</p> : <div className="space-y-2">{bankAccounts.map((account) => <article className="flex flex-wrap items-center gap-3 rounded-lg border p-3" key={account.id}><div className="min-w-40 flex-1"><p className="font-semibold text-slate-800">{account.banco}</p><p className="text-xs text-slate-500">Titular: {account.titular}</p></div><p className="text-sm text-slate-700">Ag. {account.agencia || "—"} · Cc. {account.conta}</p><button onClick={() => editBankAccount(account)} className="rounded border border-emerald-200 p-1 text-emerald-800" title="Editar conta"><Pencil size={15} /></button><button onClick={() => removeBankAccount(account)} className="rounded border border-red-200 p-1 text-red-700" title="Excluir conta"><Trash2 size={15} /></button></article>)}</div>}
              </section>
            </div>
          </section>
        </div>
      )}
    </main>
  );
}
