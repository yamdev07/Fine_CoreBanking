"use client";

import { useState } from "react";
import Header from "@/components/layout/Header";
import { PageLoader, ErrorBox } from "@/components/ui/Spinner";
import ExportButtons from "@/components/ui/ExportButtons";
import { getResultat, type ResultatSection } from "@/lib/api/reporting";
import { formatCurrency, formatPct, today, startOfYear } from "@/lib/utils";
import { TrendingUp, TrendingDown } from "lucide-react";

const REPORTING_URL = process.env.NEXT_PUBLIC_REPORTING_URL ?? "http://localhost:8001";

function ResultatSectionTable({ section }: { section: ResultatSection }) {
  return (
    <>
      <tr className="bg-slate-100">
        <td colSpan={3} className="px-4 py-2 text-xs font-bold uppercase tracking-wide text-slate-600">
          {section.label}
        </td>
      </tr>
      {section.lines.map((l) => (
        <tr key={l.account_code} className="tr-hover border-b border-slate-100">
          <td className="td font-mono text-xs text-brand-700 w-28">{l.account_code}</td>
          <td className="td text-sm">{l.account_name}</td>
          <td className="td-num">{formatCurrency(l.current_year)}</td>
        </tr>
      ))}
      <tr className="bg-slate-50 border-b border-slate-200">
        <td colSpan={2} className="px-4 py-2 text-sm font-bold text-slate-700">Sous-total</td>
        <td className="td-num font-bold">{formatCurrency(section.subtotal_current)}</td>
      </tr>
    </>
  );
}

export default function IncomeStatementPage() {
  const [startDate, setStartDate] = useState(startOfYear());
  const [endDate, setEndDate] = useState(today());
  const [data, setData] = useState<Awaited<ReturnType<typeof getResultat>> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = () => {
    setLoading(true);
    setError("");
    getResultat(startDate, endDate)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  return (
    <>
      <Header title="Compte de résultat" subtitle="Produits, charges et résultat intermédiaires" />
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
          {data && (
            <ExportButtons
              pdfUrl={`${REPORTING_URL}/api/v1/reports/income-statement?start_date=${startDate}&end_date=${endDate}&format=pdf`}
            />
          )}
        </div>

        {error && <ErrorBox message={error} />}
        {loading && <PageLoader />}

        {data && !loading && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Résultats intermédiaires */}
            <div className="space-y-3">
              {[
                { label: "Produit Net Bancaire", value: data.produit_net_bancaire, desc: "Produits financiers - Charges financières" },
                { label: "RBE", value: data.resultat_brut_exploitation, desc: "Résultat Brut d'Exploitation" },
                { label: "Résultat Net", value: data.resultat_net, desc: "Après dotations et reprises" },
              ].map((kpi) => (
                <div key={kpi.label} className="card p-4">
                  <p className="text-xs text-slate-500">{kpi.label}</p>
                  <p className="text-xs text-slate-400 mb-2">{kpi.desc}</p>
                  <p className={`text-xl font-bold ${kpi.value >= 0 ? "text-emerald-700" : "text-red-600"}`}>
                    {formatCurrency(kpi.value)}
                  </p>
                </div>
              ))}
              <div className="card p-4">
                <p className="text-xs text-slate-500 mb-1">Variation résultat vs N-1</p>
                <div className="flex items-center gap-2">
                  {data.variation_resultat_pct !== null && data.variation_resultat_pct >= 0
                    ? <TrendingUp className="w-5 h-5 text-emerald-600" />
                    : <TrendingDown className="w-5 h-5 text-red-500" />}
                  <p className={`text-xl font-bold ${(data.variation_resultat_pct ?? 0) >= 0 ? "text-emerald-700" : "text-red-600"}`}>
                    {formatPct(data.variation_resultat_pct)}
                  </p>
                </div>
              </div>
            </div>

            {/* Détail Produits */}
            <div className="card overflow-hidden">
              <div className="bg-emerald-700 px-4 py-3">
                <div className="flex justify-between">
                  <p className="text-white font-bold text-sm">PRODUITS</p>
                  <p className="text-white font-bold text-sm">{formatCurrency(data.total_produits)}</p>
                </div>
              </div>
              <table className="w-full">
                <tbody className="divide-y divide-slate-100">
                  <ResultatSectionTable section={data.produits_financiers} />
                  <ResultatSectionTable section={data.produits_accessoires} />
                  <ResultatSectionTable section={data.reprises_provisions} />
                </tbody>
              </table>
            </div>

            {/* Détail Charges */}
            <div className="card overflow-hidden">
              <div className="bg-red-700 px-4 py-3">
                <div className="flex justify-between">
                  <p className="text-white font-bold text-sm">CHARGES</p>
                  <p className="text-white font-bold text-sm">{formatCurrency(data.total_charges)}</p>
                </div>
              </div>
              <table className="w-full">
                <tbody className="divide-y divide-slate-100">
                  <ResultatSectionTable section={data.charges_financieres} />
                  <ResultatSectionTable section={data.charges_exploitation} />
                  <ResultatSectionTable section={data.dotations_provisions} />
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
