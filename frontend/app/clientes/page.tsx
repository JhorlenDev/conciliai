"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Pencil, Trash2, X } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
type Client = { id: string; nome: string; documento: string | null };

export default function ClientesPage() {
  const [clients, setClients] = useState<Client[]>([]),
    [name, setName] = useState(""),
    [document, setDocument] = useState(""),
    [message, setMessage] = useState(""),
    [editing, setEditing] = useState<string | null>(null),
    [draft, setDraft] = useState({ nome: "", documento: "" });
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
  return (
    <main className="min-h-screen bg-slate-100">
      <header className="bg-emerald-800 px-6 py-3 text-white">
        <Link href="/" className="text-lg font-bold">
          ConcilIAí
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
    </main>
  );
}
