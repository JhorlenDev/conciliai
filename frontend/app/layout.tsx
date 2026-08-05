import "./globals.css";
import type { Metadata } from "next";
import { ClearCacheButton } from "./components/clear-cache-button";

export const metadata: Metadata = { title: "ConcilIA", description: "Conciliação bancária" };
export default function Layout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="pt-BR"><body className="pb-9">{children}<footer className="fixed inset-x-0 bottom-0 z-40 border-t border-slate-200 bg-white/90 px-4 py-2 text-center text-xs text-slate-500 backdrop-blur">Desenvolvido por <strong className="font-semibold text-slate-700">JVLAB</strong> · v0.0.2<ClearCacheButton/></footer></body></html>; }
