"use client";

import { useState } from "react";
import Header from "@/components/layout/Header";
import { PageLoader, ErrorBox } from "@/components/ui/Spinner";
import ExportButtons from "@/components/ui/ExportButtons";
import { getJournalCentralizer } from "@/lib/api/reporting";
import { formatCurrency, formatNumber, today, startOfYear } from "@/lib/utils";
import { CheckCircle2, XCircle } from "lucide-react";

const REPORTING_URL = process.env.NEXT_PUBLIC_REPORTING_URL ?? "http://localhost:8001";

export default function JournalCentralizerPage() {
  const [startDate, setStartDate] = useState(startOfYear());
  const [endDate, setEndDate] = useState(today());
  const [data, setData] = useState<Awaited<ReturnType<typeof getJournalCentralizer>> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = () => {
    setLoading(true);
    setError("");
    getJournalCentralizer(startDate, endDate)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  return (
    <>
      <Header title="Journal centralisateur" subtitle="Récapitulatif de tous les journaux" />
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
              excelUrl={`${REPORTING_URL}/api/v1/reports/journal-centralizer?start_date=${startDate}&end_date=${endDate}&format=excel`}
            />
          )}
        </div>

        {error && <ErrorBox message={error} />}
        {loading && <PageLoader />}

        {data && !loading && (
          <>
            <div className="flex items-center gap-4 p-3 card">
              {data.is_balanced
                ? <><CheckCircle2 className="w-4 h-4 text-emerald-600" /><span className="text-sm text-emerald-700 font-medium">Journaux équilibrés</span></>
                : <><XCircle className="w-4 h-4 text-red-500" /><span className="text-sm text-red-600 font-medium">Déséquilibre détecté</span></>}
              <span className="text-slate-400">|</span>
              <span className="text-sm text-slate-600">{data.total_ecritures} écriture(s) au total</span>
            </div>

            <div className="card overflow-hidden">
              <table className="w-full">
                <thead className="bg-slate-50 border-b border-slate-200">
                  <tr>
                    <th className="th">Journal</th>
                    <th className="th">Libellé</th>
                    <th className="th text-right">Nb écritures</th>
                    <th className="th text-right">Total débit</th>
                    <th className="th text-right">Total crédit</th>
                    <th className="th text-center">Équilibré</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {data.lines.map((l) => (
                    <tr key={l.journal_code} className="tr-hover">
                      <td className="td font-mono font-bold text-brand-700">{l.journal_code}</td>
                      <td className="td">{l.journal_name}</td>
                      <td className="td-num">{formatNumber(l.nb_ecritures)}</td>
                      <td className="td-num">{formatCurrency(l.total_debit)}</td>
                      <td className="td-num">{formatCurrency(l.total_credit)}</td>
                      <td className="td text-center">
                        {l.is_balanced
                          ? <CheckCircle2 className="w-4 h-4 text-emerald-500 mx-auto" />
                          : <XCircle className="w-4 h-4 text-red-500 mx-auto" />}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot className="bg-slate-50 border-t-2 border-slate-300">
                  <tr>
                    <td colSpan={2} className="px-4 py-3 font-bold text-slate-900 text-sm">TOTAL</td>
                    <td className="td-num font-bold">{formatNumber(data.total_ecritures)}</td>
                    <td className="td-num font-bold">{formatCurrency(data.grand_total_debit)}</td>
                    <td className="td-num font-bold">{formatCurrency(data.grand_total_credit)}</td>
                    <td></td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </>
        )}
      </div>
    </>
  );
}
