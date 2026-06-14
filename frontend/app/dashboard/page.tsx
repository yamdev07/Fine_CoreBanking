"use client";

import { useEffect, useState } from "react";
import Header from "@/components/layout/Header";
import { PageLoader, ErrorBox } from "@/components/ui/Spinner";
import { getDashboard, type DashboardReport, type KPIValue } from "@/lib/api/reporting";
import { getJournalEntries, type JournalEntry } from "@/lib/api/accounting";
import { formatCurrency, formatPct, today } from "@/lib/utils";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, CartesianGrid,
} from "recharts";
import {
  TrendingUp, TrendingDown, Minus, AlertTriangle, CheckCircle2,
  Landmark, PiggyBank, Wallet, Activity, FileText, Clock,
  ArrowUpRight, ArrowDownRight,
} from "lucide-react";
import { cn } from "@/lib/utils";

// ── KPI gradient config ────────────────────────────────────────────────────────

const KPI_CONFIGS = [
  {
    gradient: "from-indigo-500 via-indigo-600 to-indigo-700",
    shadow: "shadow-indigo-500/25",
    icon: Landmark,
    barColor: "#4F46E5",
  },
  {
    gradient: "from-emerald-500 via-emerald-600 to-emerald-700",
    shadow: "shadow-emerald-500/25",
    icon: PiggyBank,
    barColor: "#10B981",
  },
  {
    gradient: "from-violet-500 via-violet-600 to-violet-700",
    shadow: "shadow-violet-500/25",
    icon: Wallet,
    barColor: "#8B5CF6",
  },
  {
    gradient: "from-amber-500 via-amber-600 to-amber-700",
    shadow: "shadow-amber-500/25",
    icon: Activity,
    barColor: "#F59E0B",
  },
] as const;

// ── Components ─────────────────────────────────────────────────────────────────

function KPICard({ kpi, config }: { kpi: KPIValue; config: typeof KPI_CONFIGS[number] }) {
  const Icon = config.icon;
  const isUp   = kpi.trend === "UP";
  const isDown = kpi.trend === "DOWN";
  const TrendIcon = isUp ? ArrowUpRight : isDown ? ArrowDownRight : Minus;

  return (
    <div className={cn(
      "rounded-2xl p-5 bg-gradient-to-br text-white shadow-lg relative overflow-hidden",
      config.gradient, config.shadow,
    )}>
      {/* decorative circle */}
      <div className="absolute -right-4 -top-4 w-24 h-24 rounded-full bg-white/10 pointer-events-none" />
      <div className="absolute -right-2 -bottom-6 w-16 h-16 rounded-full bg-white/5 pointer-events-none" />

      <div className="relative flex items-start justify-between mb-3">
        <div className="w-10 h-10 rounded-xl bg-white/20 backdrop-blur-sm flex items-center justify-center">
          <Icon className="w-5 h-5 text-white" />
        </div>
        {kpi.variation_pct !== null && (
          <div className={cn(
            "flex items-center gap-0.5 text-xs font-semibold px-2 py-1 rounded-lg",
            isUp ? "bg-white/25" : isDown ? "bg-black/20" : "bg-white/15",
          )}>
            <TrendIcon className="w-3 h-3" />
            <span>{formatPct(Math.abs(kpi.variation_pct))}</span>
          </div>
        )}
      </div>

      <div className="relative">
        <p className="text-2xl font-bold tabular-nums tracking-tight leading-tight">
          {formatCurrency(kpi.value)}
        </p>
        <p className="text-white/70 text-xs font-semibold uppercase tracking-wider mt-2">
          {kpi.label}
        </p>
      </div>
    </div>
  );
}

const STATUS_BADGE: Record<string, { label: string; cls: string }> = {
  POSTED:   { label: "Validé",    cls: "badge-green" },
  DRAFT:    { label: "Brouillon", cls: "badge-yellow" },
  REVERSED: { label: "Extourné",  cls: "badge-red" },
};

function RecentEntries({ entries }: { entries: JournalEntry[] }) {
  if (entries.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-slate-300">
        <FileText className="w-10 h-10 mb-3 opacity-50" />
        <p className="text-sm font-medium text-slate-400">Aucune écriture enregistrée</p>
        <p className="text-xs text-slate-400 mt-1">Créez des écritures dans le module Comptabilité</p>
      </div>
    );
  }

  return (
    <div className="table-wrap">
      <table className="w-full">
        <thead>
          <tr>
            <th className="th">Référence</th>
            <th className="th">Date</th>
            <th className="th">Description</th>
            <th className="th">Journal</th>
            <th className="th-right">Montant</th>
            <th className="th">Statut</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((e) => {
            const s = STATUS_BADGE[e.status] ?? STATUS_BADGE.DRAFT;
            return (
              <tr key={e.id} className="tr-hover">
                <td className="td font-mono text-xs text-slate-400">{e.entry_number}</td>
                <td className="td text-slate-500 whitespace-nowrap">
                  {new Date(e.entry_date).toLocaleDateString("fr-FR", { day: "2-digit", month: "short", year: "numeric" })}
                </td>
                <td className="td max-w-[200px]">
                  <span className="truncate block text-slate-700">{e.description}</span>
                </td>
                <td className="td">
                  <span className="badge badge-blue">{e.journal_code ?? "—"}</span>
                </td>
                <td className="td-num font-semibold">{formatCurrency(parseFloat(e.total_debit))}</td>
                <td className="td">
                  <span className={cn("badge", s.cls)}>{s.label}</span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function RentabiliteCard({ data }: { data: DashboardReport }) {
  const items = [
    { label: "Résultat net", value: formatCurrency(data.kpi_resultat_net.value),     color: "text-slate-900" },
    { label: "ROE",          value: formatPct(data.kpi_roe.value),                    color: "text-brand-600" },
    { label: "ROA",          value: formatPct(data.kpi_roa.value),                    color: "text-brand-600" },
    { label: "Liquidité",    value: formatPct(data.kpi_ratio_liquidite.value),         color: "text-emerald-600" },
  ];

  const barData = [
    { name: "Crédits",    value: data.kpi_encours_credits.value / 1_000_000,       fill: "#4F46E5" },
    { name: "Épargne",    value: data.kpi_encours_epargne.value / 1_000_000,       fill: "#10B981" },
    { name: "Trésorerie", value: data.kpi_tresorerie.value / 1_000_000,            fill: "#8B5CF6" },
    { name: "PNB",        value: data.kpi_produit_net_bancaire.value / 1_000_000,  fill: "#F59E0B" },
  ];

  return (
    <div className="card p-5 flex flex-col gap-5">
      <div>
        <p className="section-title">Rentabilité</p>
        <p className="text-xs text-slate-400 mt-0.5">Indicateurs de performance</p>
      </div>

      <div className="space-y-1">
        {items.map((item) => (
          <div key={item.label}
            className="flex items-center justify-between py-2.5 border-b border-slate-50 last:border-0"
          >
            <span className="text-sm text-slate-500">{item.label}</span>
            <span className={cn("text-sm font-bold tabular-nums", item.color)}>{item.value}</span>
          </div>
        ))}
      </div>

      <div className="border-t border-slate-100 pt-4">
        <p className="text-xs text-slate-400 font-semibold uppercase tracking-wider mb-3">
          Encours (M XOF)
        </p>
        <ResponsiveContainer width="100%" height={130}>
          <BarChart data={barData} barCategoryGap="30%">
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F1F5F9" />
            <XAxis dataKey="name" tick={{ fontSize: 10, fill: "#94A3B8" }} axisLine={false} tickLine={false} />
            <YAxis
              tickFormatter={(v: number) => `${v.toFixed(1)}M`}
              width={36}
              tick={{ fontSize: 9, fill: "#94A3B8" }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              formatter={(v: number) => [`${v.toFixed(2)} M XOF`]}
              contentStyle={{ borderRadius: 10, border: "1px solid #E2E8F0", fontSize: 11, padding: "4px 10px" }}
            />
            <Bar dataKey="value" radius={[4, 4, 0, 0]} maxBarSize={44}>
              {barData.map((entry, i) => (
                <Cell key={i} fill={entry.fill} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function PortfolioCard({ kpi, good }: { kpi: KPIValue; good: "high" | "low" }) {
  const v = parseFloat(String(kpi.value));
  const isAlert = good === "high" ? v > 5 : v < 75;

  return (
    <div className={cn(
      "card p-4 flex items-center gap-4 hover:shadow-card-md transition-all duration-150 border-l-[3px]",
      isAlert ? "border-l-rose-400" : "border-l-emerald-400",
    )}>
      <div className={cn(
        "w-10 h-10 rounded-xl flex items-center justify-center shrink-0",
        isAlert ? "bg-rose-50 ring-1 ring-rose-100" : "bg-emerald-50 ring-1 ring-emerald-100",
      )}>
        {isAlert
          ? <AlertTriangle className="w-5 h-5 text-rose-500" />
          : <CheckCircle2 className="w-5 h-5 text-emerald-600" />}
      </div>
      <div className="min-w-0">
        <p className="text-xs text-slate-500 font-medium truncate">{kpi.label}</p>
        <p className={cn("text-xl font-bold mt-0.5 tabular-nums", isAlert ? "text-rose-600" : "text-emerald-700")}>
          {formatPct(kpi.value)}
        </p>
      </div>
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const [data,    setData]    = useState<DashboardReport | null>(null);
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [error,   setError]   = useState("");
  const [date,    setDate]    = useState(today());

  useEffect(() => {
    setError("");
    setData(null);

    getDashboard(date)
      .then(setData)
      .catch((e: Error) => setError(e.message));

    getJournalEntries({ size: 5, status: "POSTED" })
      .then((r) => setEntries(r.items))
      .catch(() => setEntries([]));
  }, [date]);

  return (
    <>
      <Header
        title="Tableau de bord"
        subtitle="Vue exécutive en temps réel"
        actions={
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="input w-40 text-xs"
          />
        }
      />

      <div className="flex-1 p-6 space-y-6 bg-slate-50/60">
        {error && <ErrorBox message={error} />}
        {!data && !error && <PageLoader />}

        {data && (
          <>
            {/* ── KPI gradient cards ── */}
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">
                Indicateurs financiers
              </p>
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                {([
                  { kpi: data.kpi_encours_credits,      cfg: KPI_CONFIGS[0] },
                  { kpi: data.kpi_encours_epargne,      cfg: KPI_CONFIGS[1] },
                  { kpi: data.kpi_tresorerie,           cfg: KPI_CONFIGS[2] },
                  { kpi: data.kpi_produit_net_bancaire, cfg: KPI_CONFIGS[3] },
                ] as const).map(({ kpi, cfg }, i) => (
                  <KPICard key={i} kpi={kpi} config={cfg} />
                ))}
              </div>
            </div>

            {/* ── Recent entries + rentabilité ── */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Recent entries */}
              <div className="card p-5 lg:col-span-2">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <p className="section-title">Dernières écritures</p>
                    <p className="text-xs text-slate-400 mt-0.5">5 entrées les plus récentes validées</p>
                  </div>
                  <div className="flex items-center gap-1.5 text-xs text-slate-400 bg-slate-50 px-2.5 py-1.5 rounded-lg border border-slate-100">
                    <Clock className="w-3.5 h-3.5" />
                    <span>Temps réel</span>
                  </div>
                </div>
                <RecentEntries entries={entries} />
              </div>

              {/* Rentabilité */}
              <RentabiliteCard data={data} />
            </div>

            {/* ── Portfolio quality ── */}
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">
                Qualité du portefeuille
              </p>
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <PortfolioCard kpi={data.kpi_taux_impayes}         good="high" />
                <PortfolioCard kpi={data.kpi_taux_couverture}      good="low"  />
                <PortfolioCard kpi={data.kpi_ratio_liquidite}      good="low"  />
                <PortfolioCard kpi={data.kpi_ratio_credits_depots} good="low"  />
              </div>
            </div>
          </>
        )}
      </div>
    </>
  );
}
