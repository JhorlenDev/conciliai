"use client";

import { RefreshCw } from "lucide-react";

export function ClearCacheButton() {
  async function clearCache() {
    window.localStorage.clear();
    window.sessionStorage.clear();
    if ("caches" in window) await Promise.all((await window.caches.keys()).map((key) => window.caches.delete(key)));
    window.location.reload();
  }

  return <button type="button" onClick={clearCache} className="ml-2 inline-flex items-center gap-1 rounded border border-slate-300 px-1.5 py-0.5 text-[10px] text-slate-500 hover:bg-slate-100 hover:text-slate-700" title="Limpar cache local e recarregar"><RefreshCw size={11}/>Limpar cache</button>;
}
