"use client";

import { useState } from "react";
import Header from "@/components/layout/Header";
import { PageLoader, ErrorBox } from "@/components/ui/Spinner";
import ExportButtons from "@/components/ui/ExportButtons";
import { getTrialBalance, type TrialBalanceLine } from "@/lib/api/reporting";
import { exportUrl } from "@/lib/api/reporting";
import { formatCurrency, today, startOfYear } from "@/lib/utils";
import { CheckCircle2, XCircle } from "lucide-react";

export default function TrialBalancePage() {
  const [startDate, setStartDate] = useState(startOfYear());
  const [endDate, setEndDate] = useState(today());
  const [data, setData] = useState<ReturnType<typeof getTrialBalance> extends Promise<infer T> ? T : never | null>(null as any);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = () => {
    setLoading(true);
    setError("");
    getTrialBalance(startDate, endDate)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  const base = `/api/v1/reports/trial-balance?start_date=${startDate}&end_date=${endDate}`;

  return (
    <>
      <Header title="Balance générale" subtitle="Soldes d'ouverture, mouvements et clôture" />
      <div className="flex-1 p-6 space-y-4">

        <div className="flex items-end gap-3 flex-wrap">
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
              pdfUrl={`${process.env.NEXT_PUBLIC_REPORTING_URL ?? "http://localhost:8001"}${base}&format=pdf`}
              excelUrl={`${process.env.NEXT_PUBLIC_REPORTING_URL ?? "http://localhost:8001"}${base}&format=excel`}
            />
          )}
        </div>

        {error && <ErrorBox message={error} />}
        {loading && <PageLoader />}

        {data && !loading && (
          <>
            {/* Résumé */}
            <div className="flex items-center gap-4 p-4 card">
              <div className="flex items-center gap-2">
                {data.is_balanced
                  ? <><CheckCircle2 className="w-5 h-5 text-emerald-600" /><span className="text-sm font-medium text-emerald-700">Balance équilibrée</span></>
                  : <><XCircle className="w-5 h-5 text-red-500" /><span className="text-sm font-medium text-red-600">Balance déséquilibrée</span></>}
              </div>
              <span className="text-slate-400">|</span>
              <span className="text-sm text-slate-600">{data.account_count} comptes mouvementés</span>
            </div>

            <div className="card overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[900px]">
                  <thead className="bg-slate-50 border-b border-slate-200">
                    <tr>
                      <th className="th">Code</th>
                      <th className="th">Libellé</th>
                      <th className="th text-right">Débit ouv.</th>
                      <th className="th text-right">Crédit ouv.</th>
                      <th className="th text-right">Débit pér.</th>
                      <th className="th text-right">Crédit pér.</th>
                      <th className="th text-right">Solde D</th>
                      <th className="th text-right">Solde C</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {data.lines.map((l: TrialBalanceLine) => (
                      <tr key={l.account_code} className="tr-hover">
                        <td className="td font-mono text-brand-700 font-medium">{l.account_code}</td>
                        <td className="td">{l.account_name}</td>
                        <td className="td-num">{formatCurrency(l.opening_debit)}</td>
                        <td className="td-num">{formatCurrency(l.opening_credit)}</td>
                        <td className="td-num">{formatCurrency(l.period_debit)}</td>
                        <td className="td-num">{formatCurrency(l.period_credit)}</td>
                        <td className="td-num font-semibold">{formatCurrency(l.closing_debit)}</td>
                        <td className="td-num font-semibold">{formatCurrency(l.closing_credit)}</td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot className="bg-slate-50 border-t-2 border-slate-300 font-bold">
                    <tr>
                      <td colSpan={2} className="px-4 py-3 text-sm font-bold text-slate-900">TOTAUX</td>
                      <td className="td-num">{formatCurrency(data.total_opening_debit)}</td>
                      <td className="td-num">{formatCurrency(data.total_opening_credit)}</td>
                      <td className="td-num">{formatCurrency(data.total_period_debit)}</td>
                      <td className="td-num">{formatCurrency(data.total_period_credit)}</td>
                      <td className="td-num">{formatCurrency(data.total_closing_debit)}</td>
                      <td className="td-num">{formatCurrency(data.total_closing_credit)}</td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            </div>
          </>
        )}
      </div>
    </>
  );
}
