"use client";

import Header from "@/components/layout/Header";
import Link from "next/link";
import { BookMarked, Building2, ChevronRight, Info } from "lucide-react";

const SETTINGS_SECTIONS = [
  {
    href: "/settings/plan-setup",
    icon: BookMarked,
    title: "Plan comptable",
    description: "Choisir et charger un référentiel comptable (PCIMF, PCEC) ou importer un plan personnalisé.",
    badge: "Admin",
    badgeCls: "badge-red",
  },
  {
    href: "#",
    icon: Building2,
    title: "Institution",
    description: "Nom de l'institution, pays, devise par défaut, coordonnées pour les rapports officiels.",
    badge: "Bientôt",
    badgeCls: "badge-gray",
  },
];

export default function SettingsPage() {
  return (
    <>
      <Header title="Paramétrage" subtitle="Configuration de l'institution et du système comptable" />
      <div className="flex-1 p-6 max-w-3xl space-y-4">

        <div className="rounded-xl border border-brand-100 bg-brand-50 p-4 flex items-start gap-3">
          <Info className="w-4 h-4 text-brand-500 mt-0.5 flex-shrink-0" />
          <p className="text-sm text-brand-700">
            Les modifications de paramétrage sont réservées aux administrateurs et peuvent affecter
            l'ensemble des données comptables. Procédez avec soin.
          </p>
        </div>

        <div className="space-y-3">
          {SETTINGS_SECTIONS.map(s => {
            const Icon = s.icon;
            const isActive = s.href !== "#";
            return (
              <Link
                key={s.href}
                href={s.href}
                className={`
                  flex items-center gap-4 p-5 rounded-xl border bg-white transition-all duration-150
                  ${isActive
                    ? "border-slate-200 hover:border-brand-200 hover:shadow-sm cursor-pointer"
                    : "border-slate-100 opacity-60 cursor-not-allowed"}
                `}
              >
                <div className="w-10 h-10 rounded-xl bg-slate-100 flex items-center justify-center flex-shrink-0">
                  <Icon className="w-5 h-5 text-slate-600" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-slate-900">{s.title}</span>
                    <span className={s.badgeCls}>{s.badge}</span>
                  </div>
                  <p className="text-sm text-slate-500 mt-0.5">{s.description}</p>
                </div>
                {isActive && <ChevronRight className="w-4 h-4 text-slate-400 flex-shrink-0" />}
              </Link>
            );
          })}
        </div>
      </div>
    </>
  );
}
