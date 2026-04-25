"use client";

import { formatDate, today } from "@/lib/utils";
import { Bell, RefreshCw } from "lucide-react";

export default function Header({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <header className="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between">
      <div>
        <h1 className="page-title">{title}</h1>
        {subtitle && <p className="page-subtitle">{subtitle}</p>}
      </div>
      <div className="flex items-center gap-3">
        <span className="text-sm text-slate-500">
          {formatDate(today())}
        </span>
        <button
          onClick={() => window.location.reload()}
          className="btn-ghost text-slate-500"
          title="Rafraîchir"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
        <button className="relative btn-ghost text-slate-500">
          <Bell className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
}
