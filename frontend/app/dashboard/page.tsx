"use client";

import { useEffect, useState } from "react";
import Header from "@/components/layout/Header";
import { PageLoader, ErrorBox } from "@/components/ui/Spinner";
import { getDashboard, type DashboardReport, type KPIValue } from "@/lib/api/reporting";
import { formatCurrency, formatPct, today } from "@/lib/utils";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, Cell,
} from "recharts";
import {
  TrendingUp, TrendingDown, Minus, AlertTriangle, CheckCircle2,
  Landmark, PiggyBank, Wallet, Activity,
} from "lucide-react";
import { cn } from "@/lib/utils";

const KPI_ICONS = [Landmark, PiggyBank, Wallet, Activity];

function KPICard({
  kpi,
  isCurrency = true,
  icon: Icon,
  accent = "brand",
}: {
  kpi: KPIValue;
  isCurrency?: boolean;
  icon?: React.ComponentType<{ className?: string }>;
  accent?: "brand" | "emerald" | "violet" | "amber";
}) {
  const value = isCurrency ? formatCurrency(kpi.value) : formatPct(kpi.value);
  const TrendIcon =
    kpi.trend === "UP" ? TrendingUp :
    kpi.trend === "DOWN" ? TrendingDown : Minus;
  const isUp   = kpi.trend === "UP";
  const isDown = kpi.trend === "DOWN";

  const accentMap = {
    brand:   { bg: "bg-brand-50",   icon: "text-brand-600",   ring: "ring-brand-100" },
    emerald: { bg: "bg-emerald-50", icon: "text-emerald-600", ring: "ring-emerald-100" },
    violet:  { bg: "bg-violet-50",  icon: "text-violet-600",  ring: "ring-violet-100" },
    amber:   { bg: "bg-amber-50",   icon: "text-amber-600",   ring: "ring-amber-100" },
  };
  const a = accentMap[accent];

  return (
    <div className="card p-5 flex flex-col gap-3 hover:shadow-card-md transition-shadow">
      <div className="flex items-start justify-between">
        <p className="kpi-label">{kpi.label}</p>
        {Icon && (
          <div className={cn("w-9 h-9 rounded-xl flex items-center justify-center ring-1", a.bg, a.ring)}>
            <Icon className={cn("w-5 h-5", a.icon)} />
          </div>
        )}
      </div>
      <p className="kpi-value">{value}</p>
      {kpi.variation_pct !== null && (
        <div className={cn(
          "flex items-center gap-1 text-xs font-medium",
          isUp && "kpi-change-up",
          isDown && "kpi-change-down",
          !isUp && !isDown && "text-slate-400",
        )}>
          <TrendIcon className="w-3.5 h-3.5" />
          <span>{formatPct(Math.abs(kpi.variation_pct))} vs N-1</span>
        </div>
      )}
    </div>
  );
}

function RatioCard({ kpi, good = "high" }: { kpi: KPIValue; good?: "high" | "low" }) {
  const v = parseFloat(String(kpi.value));
  const isAlert = good === "high" ? v > 5 : v < 75;
  return (
    <div className="card p-4 flex items-center gap-4 hover:shadow-card-md transition-shadow">
      <div className={cn(
        "w-10 h-10 rounded-xl flex items-center justify-center shrink-0",
        isAlert ? "bg-rose-50 ring-1 ring-rose-100" : "bg-emerald-50 ring-1 ring-emerald-100"
      )}>
        {isAlert
          ? <AlertTriangle className="w-5 h-5 text-rose-500" />
          : <CheckCircle2 className="w-5 h-5 text-emerald-600" />}
      </div>
      <div>
        <p className="text-xs text-slate-500 font-medium">{kpi.label}</p>
        <p className={cn("text-xl font-bold mt-0.5", isAlert ? "text-rose-600" : "text-emerald-700")}>
          {formatPct(kpi.value)}
        </p>
      </div>
    </div>
  );
}

const BAR_COLORS = ["#4F46E5", "#10B981"];

export default function DashboardPage() {
  const [data, setData] = useState<DashboardReport | null>(null);
  const [error, setError] = useState("");
  const [date, setDate] = useState(today());

  useEffect(() => {
    setError("");
    setData(null);
    getDashboard(date).then(setData).catch((e) => setError(e.message));
  }, [date]);

  const barData = data ? [
    {
      name: "Encours",
      Crédits: parseFloat(String(data.kpi_encours_credits.value)) / 1_000_000,
      Épargne: parseFloat(String(data.kpi_encours_epargne.value)) / 1_000_000,
    },
  ] : [];

  const kpiAccents = ["brand", "emerald", "violet", "amber"] as const;

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
      <div className="flex-1 p-6 space-y-6">
        {error && <ErrorBox message={error} />}
        {!data && !error && <PageLoader />}

        {data && (
          <>
            {/* KPIs */}
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">Indicateurs financiers</p>
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                {[
                  { kpi: data.kpi_encours_credits,    icon: Landmark,  acc: "brand" },
                  { kpi: data.kpi_encours_epargne,    icon: PiggyBank, acc: "emerald" },
                  { kpi: data.kpi_tresorerie,         icon: Wallet,    acc: "violet" },
                  { kpi: data.kpi_produit_net_bancaire, icon: Activity, acc: "amber" },
                ].map(({ kpi, icon, acc }, i) => (
                  <KPICard key={i} kpi={kpi} icon={icon} accent={acc as "brand" | "emerald" | "violet" | "amber"} />
                ))}
              </div>
            </div>

            {/* Charts */}
            <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
              {/* Résultat */}
              <div className="card p-5 lg:col-span-2">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-4">Rentabilité</p>
                <div className="grid grid-cols-2 gap-4">
                  {[
                    { label: "Résultat net", value: formatCurrency(data.kpi_resultat_net.value) },
                    { label: "ROE",          value: formatPct(data.kpi_roe.value) },
                    { label: "ROA",          value: formatPct(data.kpi_roa.value) },
                    { label: "Liquidité",    value: formatPct(data.kpi_ratio_liquidite.value) },
                  ].map((item) => (
                    <div key={item.label} className="bg-slate-50 rounded-xl p-3.5">
                      <p className="text-xs text-slate-500 font-medium">{item.label}</p>
                      <p className="text-base font-bold text-slate-900 mt-1">{item.value}</p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Bar chart */}
              <div className="card p-5 lg:col-span-3">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-4">Crédits vs Dépôts (M XOF)</p>
                <ResponsiveContainer width="100%" height={180}>
                  <BarChart data={barData} barCategoryGap="50%" barGap={6}>
                    <XAxis dataKey="name" hide />
                    <YAxis tickFormatter={(v) => `${v}M`} width={48} tick={{ fontSize: 11, fill: "#94A3B8" }} axisLine={false} tickLine={false} />
                    <Tooltip
                      formatter={(v: number) => `${v.toFixed(1)} M XOF`}
                      contentStyle={{ borderRadius: 12, border: "1px solid #E2E8F0", fontSize: 12 }}
                    />
                    <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
                    <Bar dataKey="Crédits" fill="#4F46E5" radius={[6, 6, 0, 0]} maxBarSize={80} />
                    <Bar dataKey="Épargne" fill="#10B981" radius={[6, 6, 0, 0]} maxBarSize={80} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Qualité du portefeuille */}
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">Qualité du portefeuille</p>
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <RatioCard kpi={data.kpi_taux_impayes}        good="high" />
                <RatioCard kpi={data.kpi_taux_couverture}     good="low" />
                <RatioCard kpi={data.kpi_ratio_liquidite}     good="low" />
                <RatioCard kpi={data.kpi_ratio_credits_depots} good="low" />
              </div>
            </div>
          </>
        )}
      </div>
    </>
  );
}
