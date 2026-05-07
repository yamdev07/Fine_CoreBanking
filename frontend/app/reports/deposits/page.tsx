"use client";

import { useState } from "react";
import Header from "@/components/layout/Header";
import { PageLoader, ErrorBox } from "@/components/ui/Spinner";
import { getToken } from "@/lib/auth";
import { formatCurrency, formatPct, today, startOfYear } from "@/lib/utils";

const REPORTING_URL = process.env.NEXT_PUBLIC_REPORTING_URL ?? "http://localhost:8001";

export default function DepositsPage() {
  const [asOf, setAsOf] = useState(today());
  const [startDate, setStartDate] = useState(startOfYear());
  const [endDate, setEndDate] = useState(today());
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = () => {
    setLoading(true);
    setError("");
    const token = getToken();
    fetch(`${REPORTING_URL}/api/v1/reports/deposits?as_of_date=${asOf}&start_date=${startDate}&end_date=${endDate}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(async (r) => {
        const json = await r.json();
        if (!r.ok) throw new Error(typeof json?.detail === "string" ? json.detail : r.statusText);
        return json;
      })
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  return (
    <>
      <Header title="État des dépôts & Épargne" />
      <div className="flex-1 p-6 space-y-4">

        <div className="flex items-end gap-3 flex-wrap">
          <div>
            <label className="label">Date d'arrêté</label>
            <input type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)} className="input w-40" />
          </div>
          <div>
            <label className="label">Période intérêts — Du</label>
            <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="input w-40" />
          </div>
          <div>
            <label className="label">Au</label>
            <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className="input w-40" />
          </div>
          <button onClick={load} className="btn-primary">Générer</button>
        </div>

        {error && <ErrorBox message={error} />}
        {loading && <PageLoader />}

        {data && !loading && (
          <>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              {[
                { label: "Total dépôts", value: formatCurrency(data.total_depots) },
                { label: "Dépôts à vue", value: formatCurrency(data.depots_vue) },
                { label: "Dépôts à terme", value: formatCurrency(data.depots_terme) },
                { label: "Plans d'épargne", value: formatCurrency(data.plans_epargne) },
              ].map((k) => (
                <div key={k.label} className="card p-4">
                  <p className="text-xs text-slate-500">{k.label}</p>
                  <p className="text-xl font-bold mt-1">{k.value}</p>
                </div>
              ))}
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div className="card p-4">
                <p className="text-xs text-slate-500">Taux moyen de rémunération</p>
                <p className="text-xl font-bold mt-1">{formatPct(data.taux_moyen_remuneration)}</p>
              </div>
              <div className="card p-4">
                <p className="text-xs text-slate-500">Charges intérêts (période)</p>
                <p className="text-xl font-bold mt-1">{formatCurrency(data.charges_interets_periode)}</p>
              </div>
              <div className="card p-4">
                <p className="text-xs text-slate-500">Ratio crédits / dépôts</p>
                <p className={`text-xl font-bold mt-1 ${parseFloat(data.ratio_credits_depots) > 100 ? "text-red-600" : "text-emerald-700"}`}>
                  {formatPct(data.ratio_credits_depots)}
                </p>
              </div>
            </div>
          </>
        )}
      </div>
    </>
  );
}
