import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Conciliaí", description: "Conciliação bancária" };
export default function Layout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="pt-BR"><body className="pb-9">{children}<footer className="fixed inset-x-0 bottom-0 z-40 border-t border-slate-200 bg-white/90 px-4 py-2 text-center text-xs text-slate-500 backdrop-blur">Desenvolvido por <strong className="font-semibold text-slate-700">JVLAB</strong> · v0.0.1</footer></body></html>; }
