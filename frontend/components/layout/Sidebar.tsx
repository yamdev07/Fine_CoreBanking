"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard, BookOpen, CalendarDays, FileText,
  BarChart3, TrendingUp, Scale, Activity, Wallet,
  PiggyBank, ShieldCheck, BookMarked, ChevronDown,
  LogOut, Users, Landmark, Settings2,
} from "lucide-react";
import { useState } from "react";
import { useAuth } from "@/context/auth";
import { type UserRole } from "@/lib/auth";

interface NavItem {
  label: string;
  href?: string;
  icon?: React.ComponentType<{ className?: string }>;
  children?: NavItem[];
  adminOnly?: boolean;
  hideFor?: UserRole[];
}

const ROLE_BADGE: Record<UserRole, { label: string; cls: string }> = {
  ADMIN:      { label: "Admin",      cls: "bg-violet-500/20 text-violet-300 ring-1 ring-violet-500/30" },
  ACCOUNTANT: { label: "Comptable",  cls: "bg-brand-500/20 text-brand-300 ring-1 ring-brand-500/30" },
  AUDITOR:    { label: "Auditeur",   cls: "bg-slate-500/20 text-slate-300 ring-1 ring-slate-500/30" },
};

function buildNav(role: UserRole | undefined): NavItem[] {
  const all: NavItem[] = [
    { label: "Tableau de bord", href: "/dashboard", icon: LayoutDashboard },
    {
      label: "Comptabilité", icon: BookOpen,
      hideFor: ["AUDITOR" as UserRole],
      children: [
        { label: "Plan de comptes",   href: "/accounts",      icon: BookMarked },
        { label: "Exercices fiscaux", href: "/fiscal-years",  icon: CalendarDays },
        { label: "Écritures",         href: "/journals",      icon: FileText },
      ],
    },
    {
      label: "Rapports", icon: BarChart3,
      children: [
        { label: "Balance générale",       href: "/reports/trial-balance",       icon: Scale },
        { label: "Grand livre",            href: "/reports/general-ledger",       icon: BookOpen },
        { label: "Bilan comptable",        href: "/reports/balance-sheet",        icon: Activity },
        { label: "Compte de résultat",     href: "/reports/income-statement",     icon: TrendingUp },
        { label: "Flux de trésorerie",     href: "/reports/cash-flow",            icon: Wallet },
        { label: "Portefeuille crédits",   href: "/reports/credit-portfolio",     icon: PiggyBank },
        { label: "Dépôts & Épargne",       href: "/reports/deposits",             icon: PiggyBank },
        { label: "Ratios BCEAO",           href: "/reports/bceao",                icon: ShieldCheck },
        { label: "Journal centralisateur", href: "/reports/journal-centralizer",  icon: BookMarked },
      ],
    },
    {
      label: "Administration", icon: Users,
      adminOnly: true,
      children: [
        { label: "Utilisateurs",         href: "/users",                icon: Users },
        { label: "Plan comptable",        href: "/settings/plan-setup",  icon: Settings2 },
      ],
    },
  ];
  return all.filter((item) => {
    if (item.adminOnly && role !== "ADMIN") return false;
    if (item.hideFor && role && item.hideFor.includes(role)) return false;
    return true;
  });
}

function NavGroup({ item }: { item: NavItem }) {
  const pathname = usePathname();
  const isChildActive = item.children?.some((c) => c.href && pathname.startsWith(c.href));
  const [open, setOpen] = useState(true);

  return (
    <div>
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-3 py-2 text-xs font-semibold uppercase tracking-widest text-slate-500 hover:text-slate-300 transition-colors mt-5 first:mt-2"
      >
        <div className="flex items-center gap-2">
          {item.icon && <item.icon className="w-3.5 h-3.5" />}
          <span>{item.label}</span>
        </div>
        <ChevronDown className={cn("w-3 h-3 transition-transform duration-200", open && "rotate-180")} />
      </button>
      {open && item.children?.map((child) => (
        <NavLink key={child.href} item={child} />
      ))}
    </div>
  );
}

function NavLink({ item }: { item: NavItem }) {
  const pathname = usePathname();
  const active = item.href
    ? pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href))
    : false;
  const Icon = item.icon;

  return (
    <Link
      href={item.href ?? "#"}
      className={cn(
        "flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-all duration-150 mx-1 my-0.5",
        active
          ? "bg-brand-600 text-white font-semibold shadow-sm shadow-brand-900/30"
          : "text-slate-400 hover:bg-slate-800 hover:text-slate-100"
      )}
    >
      {Icon && <Icon className={cn("w-4 h-4 shrink-0", active ? "text-white" : "text-slate-500")} />}
      <span className="truncate">{item.label}</span>
    </Link>
  );
}

export default function Sidebar() {
  const { user, logout } = useAuth();
  const nav = buildNav(user?.role);
  const roleBadge = user ? ROLE_BADGE[user.role] : null;

  return (
    <aside className="w-60 shrink-0 bg-slate-950 flex flex-col min-h-screen border-r border-slate-800">
      {/* Logo */}
      <div className="px-4 py-5 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-brand-600 rounded-xl flex items-center justify-center shadow-lg shadow-brand-900/40">
            <Landmark className="w-5 h-5 text-white" />
          </div>
          <div>
            <p className="text-white font-bold text-sm leading-none tracking-tight">Core Banking</p>
            <p className="text-slate-500 text-xs mt-0.5">Système comptable</p>
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

      {/* User footer */}
      {user && (
        <div className="px-3 py-3 border-t border-slate-800">
          <div className="flex items-center gap-2.5 px-2 py-2 rounded-xl hover:bg-slate-800/60 transition-colors group">
            <div className="w-8 h-8 rounded-lg bg-brand-600/20 border border-brand-500/30 flex items-center justify-center shrink-0">
              <span className="text-brand-400 font-bold text-xs">
                {user.full_name.charAt(0).toUpperCase()}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-slate-200 text-xs font-semibold truncate">{user.full_name}</p>
              {roleBadge && (
                <span className={cn("inline-block mt-0.5 text-[10px] font-medium px-1.5 py-0.5 rounded-full", roleBadge.cls)}>
                  {roleBadge.label}
                </span>
              )}
            </div>
            <button
              onClick={logout}
              title="Déconnexion"
              className="text-slate-600 hover:text-rose-400 transition-colors p-1 rounded-lg hover:bg-rose-500/10"
            >
              <LogOut className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}
    </aside>
  );
}
