"use client";

import { formatDate, today } from "@/lib/utils";
import { RefreshCw } from "lucide-react";

export default function Header({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
}) {
  return (
    <header className="bg-white/80 backdrop-blur-sm border-b border-slate-100 px-6 py-4 flex items-center justify-between sticky top-0 z-10">
      <div>
        <h1 className="page-title">{title}</h1>
        {subtitle && <p className="page-subtitle">{subtitle}</p>}
      </div>
      <div className="flex items-center gap-3">
        {actions}
        <span className="hidden sm:block text-xs text-slate-400 font-medium">
          {formatDate(today())}
        </span>
        <button
          onClick={() => window.location.reload()}
          className="btn-icon"
          title="Rafraîchir"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
}
