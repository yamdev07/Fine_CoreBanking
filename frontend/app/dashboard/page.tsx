"use client";

import { useEffect, useState } from "react";
import Header from "@/components/layout/Header";
import { PageLoader, ErrorBox } from "@/components/ui/Spinner";
import { getDashboard, type DashboardReport, type KPIValue } from "@/lib/api/reporting";
import { formatCurrency, formatPct, today, startOfYear } from "@/lib/utils";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  LineChart, Line, CartesianGrid, Legend,
} from "recharts";
import { TrendingUp, TrendingDown, Minus, AlertTriangle, CheckCircle2 } from "lucide-react";

function KPICard({ kpi, isCurrency = true }: { kpi: KPIValue; isCurrency?: boolean }) {
  const value = isCurrency ? formatCurrency(kpi.value) : formatPct(kpi.value);
  const TrendIcon =
    kpi.trend === "UP" ? TrendingUp :
    kpi.trend === "DOWN" ? TrendingDown : Minus;
  const trendColor =
    kpi.trend === "UP" ? "text-emerald-600" :
    kpi.trend === "DOWN" ? "text-red-500" : "text-slate-400";

  return (
    <div className="card p-5">
      <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">{kpi.label}</p>
      <p className="text-2xl font-bold text-slate-900 mt-2">{value}</p>
      {kpi.variation_pct !== null && (
        <div className={`flex items-center gap-1 mt-2 text-xs ${trendColor}`}>
          <TrendIcon className="w-3.5 h-3.5" />
          <span>{formatPct(kpi.variation_pct)} vs N-1</span>
        </div>
      )}
    </div>
  );
}

function RatioCard({ kpi, good = "high" }: { kpi: KPIValue; good?: "high" | "low" }) {
  const v = parseFloat(String(kpi.value));
  const isGood = good === "high" ? v < 10 : v > 0;
  return (
    <div className="card p-4 flex items-center gap-4">
      <div className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${isGood ? "bg-red-50" : "bg-emerald-50"}`}>
        {isGood
          ? <AlertTriangle className="w-5 h-5 text-red-500" />
          : <CheckCircle2 className="w-5 h-5 text-emerald-600" />}
      </div>
      <div>
        <p className="text-xs text-slate-500">{kpi.label}</p>
        <p className="text-lg font-bold text-slate-900">{formatPct(kpi.value)}</p>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardReport | null>(null);
  const [error, setError] = useState("");
  const [date, setDate] = useState(today());

  useEffect(() => {
    setError("");
    setData(null);
    getDashboard(date)
      .then(setData)
      .catch((e) => setError(e.message));
  }, [date]);

  const barData = data ? [
    {
      name: "Encours",
      Crédits: parseFloat(String(data.kpi_encours_credits.value)) / 1_000_000,
      Épargne: parseFloat(String(data.kpi_encours_epargne.value)) / 1_000_000,
    },
  ] : [];

  return (
    <>
      <Header title="Tableau de bord" subtitle="Vue exécutive en temps réel" />
      <div className="flex-1 p-6 space-y-6">

        {/* Date picker */}
        <div className="flex items-center gap-3">
          <label className="text-sm font-medium text-slate-600">Date d'arrêté :</label>
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="input w-44"
          />
        </div>

        {error && <ErrorBox message={error} />}
        {!data && !error && <PageLoader />}

        {data && (
          <>
            {/* KPIs financiers */}
            <div>
              <h2 className="section-title">Indicateurs financiers</h2>
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <KPICard kpi={data.kpi_encours_credits} />
                <KPICard kpi={data.kpi_encours_epargne} />
                <KPICard kpi={data.kpi_tresorerie} />
                <KPICard kpi={data.kpi_produit_net_bancaire} />
              </div>
            </div>

            {/* Résultat + ratios */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

              {/* Résultat net */}
              <div className="card p-5">
                <h2 className="section-title">Résultat net & Rentabilité</h2>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-xs text-slate-500">Résultat net</p>
                    <p className="text-xl font-bold mt-1">{formatCurrency(data.kpi_resultat_net.value)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">ROE</p>
                    <p className="text-xl font-bold mt-1">{formatPct(data.kpi_roe.value)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">ROA</p>
                    <p className="text-xl font-bold mt-1">{formatPct(data.kpi_roa.value)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Liquidité</p>
                    <p className="text-xl font-bold mt-1">{formatPct(data.kpi_ratio_liquidite.value)}</p>
                  </div>
                </div>
              </div>

              {/* Crédits vs Dépôts */}
              <div className="card p-5">
                <h2 className="section-title">Crédits vs Dépôts (M XOF)</h2>
                <ResponsiveContainer width="100%" height={160}>
                  <BarChart data={barData} barGap={8}>
                    <XAxis dataKey="name" hide />
                    <YAxis tickFormatter={(v) => `${v}M`} width={50} tick={{ fontSize: 11 }} />
                    <Tooltip formatter={(v: number) => `${v.toFixed(1)} M XOF`} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Bar dataKey="Crédits" fill="#2563eb" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="Épargne" fill="#10b981" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Qualité du portefeuille */}
            <div>
              <h2 className="section-title">Qualité du portefeuille</h2>
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <RatioCard kpi={data.kpi_taux_impayes} good="high" />
                <RatioCard kpi={data.kpi_taux_couverture} good="low" />
                <RatioCard kpi={data.kpi_ratio_liquidite} good="low" />
                <RatioCard kpi={data.kpi_ratio_credits_depots} good="low" />
              </div>
            </div>
          </>
        )}
      </div>
    </>
  );
}
