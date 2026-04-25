"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard, BookOpen, CalendarDays, FileText,
  BarChart3, TrendingUp, Scale, Activity, Wallet,
  PiggyBank, ShieldCheck, BookMarked, ChevronDown,
} from "lucide-react";
import { useState } from "react";

interface NavItem {
  label: string;
  href?: string;
  icon?: React.ComponentType<{ className?: string }>;
  children?: NavItem[];
}

const nav: NavItem[] = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  {
    label: "Comptabilité", icon: BookOpen,
    children: [
      { label: "Plan de comptes", href: "/accounts", icon: BookMarked },
      { label: "Exercices fiscaux", href: "/fiscal-years", icon: CalendarDays },
      { label: "Écritures", href: "/journals", icon: FileText },
    ],
  },
  {
    label: "Rapports", icon: BarChart3,
    children: [
      { label: "Balance générale", href: "/reports/trial-balance", icon: Scale },
      { label: "Grand livre", href: "/reports/general-ledger", icon: BookOpen },
      { label: "Bilan comptable", href: "/reports/balance-sheet", icon: Activity },
      { label: "Compte de résultat", href: "/reports/income-statement", icon: TrendingUp },
      { label: "Flux de trésorerie", href: "/reports/cash-flow", icon: Wallet },
      { label: "Portefeuille crédits", href: "/reports/credit-portfolio", icon: PiggyBank },
      { label: "Dépôts & Épargne", href: "/reports/deposits", icon: PiggyBank },
      { label: "Ratios BCEAO", href: "/reports/bceao", icon: ShieldCheck },
      { label: "Journal centralisateur", href: "/reports/journal-centralizer", icon: BookMarked },
    ],
  },
];

function NavGroup({ item }: { item: NavItem }) {
  const pathname = usePathname();
  const isChildActive = item.children?.some((c) => c.href && pathname.startsWith(c.href));
  const [open, setOpen] = useState(isChildActive ?? true);

  return (
    <div>
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-3 py-2 text-xs font-semibold uppercase tracking-widest text-slate-400 hover:text-slate-300 transition-colors mt-4"
      >
        <span>{item.label}</span>
        <ChevronDown className={cn("w-3.5 h-3.5 transition-transform", open && "rotate-180")} />
      </button>
      {open && item.children?.map((child) => (
        <NavLink key={child.href} item={child} />
      ))}
    </div>
  );
}

function NavLink({ item }: { item: NavItem }) {
  const pathname = usePathname();
  const active = item.href ? pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href)) : false;
  const Icon = item.icon;

  return (
    <Link
      href={item.href ?? "#"}
      className={cn(
        "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors mx-1",
        active
          ? "bg-brand-600 text-white font-medium"
          : "text-slate-300 hover:bg-slate-700 hover:text-white"
      )}
    >
      {Icon && <Icon className="w-4 h-4 shrink-0" />}
      <span>{item.label}</span>
    </Link>
  );
}

export default function Sidebar() {
  return (
    <aside className="w-60 shrink-0 bg-slate-900 flex flex-col min-h-screen">
      {/* Logo */}
      <div className="px-4 py-5 border-b border-slate-700">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-brand-600 rounded-lg flex items-center justify-center">
            <span className="text-white font-bold text-sm">CB</span>
          </div>
          <div>
            <p className="text-white font-semibold text-sm leading-none">Core Banking</p>
            <p className="text-slate-400 text-xs mt-0.5">Système comptable</p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-2 py-3 overflow-y-auto">
        {nav.map((item) =>
          item.children ? (
            <NavGroup key={item.label} item={item} />
          ) : (
            <NavLink key={item.href} item={item} />
          )
        )}
      </nav>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-slate-700">
        <p className="text-xs text-slate-500">SYSCOHADA · BCEAO/UEMOA</p>
      </div>
    </aside>
  );
}
