"use client";

import { useState } from "react";
import Header from "@/components/layout/Header";
import { PageLoader, ErrorBox } from "@/components/ui/Spinner";
import { getCreditPortfolio } from "@/lib/api/reporting";
import { formatCurrency, formatPct, today } from "@/lib/utils";
import { AlertTriangle } from "lucide-react";
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from "recharts";

const COLORS = ["#2563eb", "#10b981", "#8b5cf6", "#f59e0b", "#ef4444"];

export default function CreditPortfolioPage() {
  const [date, setDate] = useState(today());
  const [data, setData] = useState<Awaited<ReturnType<typeof getCreditPortfolio>> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = () => {
    setLoading(true);
    setError("");
    getCreditPortfolio(date)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  const lines = data ? [
    data.credits_court_terme,
    data.credits_moyen_terme,
    data.credits_long_terme,
    data.creances_souffrance,
    data.creances_irrecouvrable,
  ] : [];

  const pieData = lines.filter((l) => l.encours > 0).map((l) => ({
    name: l.account_name,
    value: parseFloat(String(l.encours)),
  }));

  return (
    <>
      <Header title="Portefeuille de crédits" subtitle="Encours, impayés et provisionnement" />
      <div className="flex-1 p-6 space-y-4">

        <div className="flex items-end gap-3">
          <div>
            <label className="label">Date d'arrêté</label>
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="input w-40" />
          </div>
          <button onClick={load} className="btn-primary">Générer</button>
        </div>

        {error && <ErrorBox message={error} />}
        {loading && <PageLoader />}

        {data && !loading && (
          <>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="card p-4">
                <p className="text-xs text-slate-500">Encours total</p>
                <p className="text-xl font-bold mt-1">{formatCurrency(data.total_portefeuille)}</p>
              </div>
              <div className="card p-4">
                <p className="text-xs text-slate-500">Taux d'impayés</p>
                <p className={`text-xl font-bold mt-1 ${parseFloat(String(data.taux_impayés)) > 5 ? "text-red-600" : "text-emerald-700"}`}>
                  {formatPct(data.taux_impayés)}
                </p>
              </div>
              <div className="card p-4">
                <p className="text-xs text-slate-500">Taux couverture provisions</p>
                <p className={`text-xl font-bold mt-1 ${parseFloat(String(data.taux_couverture_provisions)) < 100 ? "text-amber-600" : "text-emerald-700"}`}>
                  {formatPct(data.taux_couverture_provisions)}
                </p>
              </div>
              <div className="card p-4">
                <p className="text-xs text-slate-500">Déficit provisionnement</p>
                <p className={`text-xl font-bold mt-1 ${parseFloat(String(data.deficit_provisionnement)) > 0 ? "text-red-600" : "text-slate-400"}`}>
                  {formatCurrency(data.deficit_provisionnement)}
                </p>
              </div>
            </div>

            {parseFloat(String(data.deficit_provisionnement)) > 0 && (
              <div className="flex items-center gap-3 p-3 rounded-lg bg-red-50 border border-red-200">
                <AlertTriangle className="w-4 h-4 text-red-500" />
                <p className="text-sm text-red-700">
                  Déficit de provisionnement de {formatCurrency(data.deficit_provisionnement)} — action corrective requise.
                </p>
              </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="card overflow-hidden">
                <table className="w-full">
                  <thead className="bg-slate-50 border-b border-slate-200">
                    <tr>
                      <th className="th">Catégorie</th>
                      <th className="th text-right">Encours</th>
                      <th className="th text-right">% Portefeuille</th>
                      <th className="th text-right">Variation</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {lines.map((l) => (
                      <tr key={l.account_code} className="tr-hover">
                        <td className="td text-sm">{l.account_name}</td>
                        <td className="td-num">{formatCurrency(l.encours)}</td>
                        <td className="td-num">{formatPct(l.pct_portefeuille)}</td>
                        <td className={`td-num ${parseFloat(String(l.variation)) >= 0 ? "text-emerald-700" : "text-red-600"}`}>
                          {parseFloat(String(l.variation)) >= 0 ? "+" : ""}{formatCurrency(l.variation)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="card p-4">
                <p className="text-sm font-semibold text-slate-700 mb-3">Répartition du portefeuille</p>
                <ResponsiveContainer width="100%" height={220}>
                  <PieChart>
                    <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={false}>
                      {pieData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                    </Pie>
                    <Tooltip formatter={(v: number) => formatCurrency(v)} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>
          </>
        )}
      </div>
    </>
  );
}
