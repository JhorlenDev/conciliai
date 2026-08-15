"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Building2, Clock3, FileText, Users } from "lucide-react";

type ProcessBank = { id: string; banco: string; status: string };
const banks = [
  "Banco do Brasil",
  "Santander",
  "BASA",
  "Bradesco",
  "Caixa",
  "Conta Caixa",
  "Apropriações",
  "Empréstimos/Financeiro",
];
const bankLogos: Record<string, string> = {
  "Banco do Brasil": "/bancos/banco-do-brasil.png",
  Santander: "/bancos/santander.png",
  BASA: "/bancos/basa.png",
  Bradesco: "/bancos/bradesco.png",
  Caixa: "/bancos/caixa.png",
  "Conta Caixa": "/bancos/conta-caixa.svg",
  Apropriações: "/bancos/apropriacoes.png",
  "Empréstimos/Financeiro": "/bancos/emprestimos.svg",
};

function CurrentDateTime() {
  const [now, setNow] = useState<Date | null>(null);

  useEffect(() => {
    const update = () => setNow(new Date());
    update();
    const timer = window.setInterval(update, 1_000);
    return () => window.clearInterval(timer);
  }, []);

  if (!now) return <div className="h-6 w-36" aria-hidden="true" />;
  return (
    <div className="hidden items-center gap-1.5 text-right leading-tight text-slate-500 sm:flex">
      <Clock3 size={14} className="text-teal-700" />
      <span className="whitespace-nowrap text-[11px]">
        <strong className="font-semibold text-slate-700">
          {now.toLocaleDateString("pt-BR", {
            weekday: "short",
            day: "numeric",
            month: "short",
            year: "numeric",
          })}
        </strong>{" "}
        <span>
          {now.toLocaleTimeString("pt-BR", {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
          })}
        </span>
      </span>
    </div>
  );
}

export function ProcessTopBar({
  processId,
  activeBank,
  processBanks,
  onSelectBank,
  isSwitching,
}: {
  processId: string;
  activeBank: string;
  processBanks: ProcessBank[];
  onSelectBank: (bank: string) => void;
  isSwitching: boolean;
}) {
  const linkedBanks = new Map(processBanks.map((item) => [item.banco, item]));
  return (
    <header className="border-b border-slate-200 bg-white shadow-sm">
      <div className="mx-auto flex max-w-none items-center gap-2 px-3 py-1.5 sm:px-4">
        <Link
          href="/"
          className="flex shrink-0 items-center gap-1.5 text-sm font-bold text-teal-800"
          aria-label="Central de Conciliações"
        >
          <span className="rounded-md bg-teal-700 p-1 text-white">
            <Building2 size={14} />
          </span>
          <span>Concil<span className="inline-block text-[1.18em] leading-none">IA</span></span>
        </Link>
        <nav
          aria-label="Navegação principal"
          className="ml-auto flex shrink-0 items-center gap-0.5 text-xs"
        >
          <Link
            href="/clientes"
            className="inline-flex items-center gap-1 rounded px-1.5 py-1 text-slate-600 hover:bg-slate-100 hover:text-slate-900"
          >
            <Users size={15} />
            Clientes
          </Link>
          <Link
            href="/documentos"
            className="inline-flex items-center gap-1 rounded px-1.5 py-1 text-slate-600 hover:bg-slate-100 hover:text-slate-900"
          >
            <FileText size={15} />
            Documentos
          </Link>
        </nav>
        <CurrentDateTime />
      </div>
      <nav
        aria-label={`Bancos do processo ${processId}`}
        className="border-t border-slate-100"
      >
        <div className="mx-auto flex max-w-none justify-center overflow-x-auto px-3 sm:px-4">
          {banks.map((bank) => {
            const linked = linkedBanks.get(bank);
            const active = bank === activeBank;
            return (
              <button
                type="button"
                onClick={() => onSelectBank(bank)}
                disabled={isSwitching}
                aria-current={active ? "page" : undefined}
                className={`flex shrink-0 items-center gap-1.5 border-b-2 px-2.5 py-1.5 text-xs transition ${active ? "border-teal-700 bg-teal-50 font-semibold text-teal-900" : "border-transparent text-slate-600 hover:bg-slate-50 hover:text-slate-900"} disabled:cursor-wait disabled:opacity-60`}
                key={bank}
              >
                <img
                  src={bankLogos[bank]}
                  alt=""
                  className="h-4 w-4 rounded-sm object-contain"
                />
                {bank}
                {linked?.status === "concluída" && (
                  <span className="text-xs text-emerald-700">✓</span>
                )}
              </button>
            );
          })}
        </div>
      </nav>
    </header>
  );
}
