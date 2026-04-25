"use client";

import { useState, useEffect } from "react";
import Header from "@/components/layout/Header";
import { PageLoader, ErrorBox } from "@/components/ui/Spinner";
import { formatCurrency, today, startOfYear } from "@/lib/utils";

const REPORTING_URL = process.env.NEXT_PUBLIC_REPORTING_URL ?? "http://localhost:8001";

export default function CashFlowPage() {
  const [startDate, setStartDate] = useState(startOfYear());
  const [endDate, setEndDate] = useState(today());
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = () => {
    setLoading(true);
    setError("");
    fetch(`${REPORTING_URL}/api/v1/reports/cash-flow?start_date=${startDate}&end_date=${endDate}`)
      .then((r) => r.json())
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  const FluxRow = ({ label, value }: { label: string; value: number }) => (
    <tr className="tr-hover border-b border-slate-100">
      <td className="td">{label}</td>
      <td className={`td-num font-semibold ${value >= 0 ? "text-emerald-700" : "text-red-600"}`}>
        {value >= 0 ? "+" : ""}{formatCurrency(value)}
      </td>
    </tr>
  );

  const Section = ({ title, color, flux, detail }: { title: string; color: string; flux: number; detail: any[] }) => (
    <div className="card overflow-hidden">
      <div className={`${color} px-4 py-3 flex justify-between items-center`}>
        <p className="text-white font-bold text-sm">{title}</p>
        <p className={`font-bold text-sm ${flux >= 0 ? "text-white" : "text-red-200"}`}>
          {flux >= 0 ? "+" : ""}{formatCurrency(flux)}
        </p>
      </div>
      <table className="w-full">
        <tbody>
          {detail.map((d: any) => (
            <FluxRow key={d.label} label={d.label} value={parseFloat(d.montant)} />
          ))}
        </tbody>
      </table>
    </div>
  );

  return (
    <>
      <Header title="Tableau de flux de trésorerie" />
      <div className="flex-1 p-6 space-y-4">
        <div className="flex items-end gap-3">
          <div>
            <label className="label">Du</label>
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
            <div className="grid grid-cols-3 gap-4 mb-2">
              {[
                { label: "Trésorerie ouverture", value: data.tresorerie_ouverture },
                { label: "Variation nette", value: data.variation_nette_tresorerie },
                { label: "Trésorerie clôture", value: data.tresorerie_cloture },
              ].map((k) => (
                <div key={k.label} className="card p-4">
                  <p className="text-xs text-slate-500">{k.label}</p>
                  <p className={`text-xl font-bold mt-1 ${parseFloat(String(k.value)) >= 0 ? "text-slate-900" : "text-red-600"}`}>
                    {formatCurrency(k.value)}
                  </p>
                </div>
              ))}
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <Section title="Flux d'exploitation" color="bg-brand-600" flux={parseFloat(data.flux_exploitation)} detail={data.flux_exploitation_detail} />
              <Section title="Flux d'investissement" color="bg-violet-700" flux={parseFloat(data.flux_investissement)} detail={data.flux_investissement_detail} />
              <Section title="Flux de financement" color="bg-emerald-700" flux={parseFloat(data.flux_financement)} detail={data.flux_financement_detail} />
            </div>
          </>
        )}
      </div>
    </>
  );
}
