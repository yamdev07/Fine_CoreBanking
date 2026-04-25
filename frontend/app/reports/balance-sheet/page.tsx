"use client";

import { useState } from "react";
import Header from "@/components/layout/Header";
import { PageLoader, ErrorBox } from "@/components/ui/Spinner";
import ExportButtons from "@/components/ui/ExportButtons";
import { getBilan, type BilanSection } from "@/lib/api/reporting";
import { formatCurrency, formatPct, today } from "@/lib/utils";
import { CheckCircle2, XCircle } from "lucide-react";

const REPORTING_URL = process.env.NEXT_PUBLIC_REPORTING_URL ?? "http://localhost:8001";

function Section({ section, year, prevYear }: { section: BilanSection; year: number; prevYear: number }) {
  return (
    <tbody>
      <tr className="bg-slate-100">
        <td colSpan={4} className="px-4 py-2 text-xs font-bold uppercase tracking-wide text-slate-600">
          {section.label}
        </td>
      </tr>
      {section.lines.map((l) => (
        <tr key={l.account_code} className="tr-hover border-b border-slate-100">
          <td className="td font-mono text-xs text-brand-700 w-28">{l.account_code}</td>
          <td className="td text-sm">{l.account_name}</td>
          <td className="td-num">{formatCurrency(l.current_year)}</td>
          <td className="td-num text-slate-500">{formatCurrency(l.previous_year)}</td>
        </tr>
      ))}
      <tr className="bg-slate-50 border-b border-slate-200">
        <td colSpan={2} className="px-4 py-2 text-sm font-bold text-slate-700">Sous-total {section.label}</td>
        <td className="td-num font-bold">{formatCurrency(section.subtotal_current)}</td>
        <td className="td-num font-bold text-slate-500">{formatCurrency(section.subtotal_previous)}</td>
      </tr>
    </tbody>
  );
}

export default function BalanceSheetPage() {
  const [date, setDate] = useState(today());
  const [data, setData] = useState<Awaited<ReturnType<typeof getBilan>> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = () => {
    setLoading(true);
    setError("");
    getBilan(date)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  return (
    <>
      <Header title="Bilan comptable" subtitle="Actif / Passif avec comparaison N-1" />
      <div className="flex-1 p-6 space-y-4">

        <div className="flex items-end gap-3">
          <div>
            <label className="label">Date d'arrêté</label>
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="input w-40" />
          </div>
          <button onClick={load} className="btn-primary">Générer</button>
          {data && (
            <ExportButtons
              pdfUrl={`${REPORTING_URL}/api/v1/reports/balance-sheet?as_of_date=${date}&format=pdf`}
            />
          )}
        </div>

        {error && <ErrorBox message={error} />}
        {loading && <PageLoader />}

        {data && !loading && (
          <>
            <div className="flex items-center gap-3 p-3 card">
              {data.is_balanced
                ? <><CheckCircle2 className="w-4 h-4 text-emerald-600" /><span className="text-sm text-emerald-700 font-medium">Bilan équilibré</span></>
                : <><XCircle className="w-4 h-4 text-red-500" /><span className="text-sm text-red-600 font-medium">Bilan déséquilibré</span></>}
              <span className="text-slate-400 text-sm">|</span>
              <span className="text-sm text-slate-600">
                Total actif : <strong>{formatCurrency(data.total_actif)}</strong>
              </span>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* ACTIF */}
              <div className="card overflow-hidden">
                <div className="bg-brand-600 px-4 py-3">
                  <p className="text-white font-bold text-sm uppercase tracking-wider">ACTIF</p>
                </div>
                <table className="w-full">
                  <thead className="bg-slate-50 border-b border-slate-200">
                    <tr>
                      <th className="th w-28">Code</th>
                      <th className="th">Libellé</th>
                      <th className="th text-right">{data.current_year}</th>
                      <th className="th text-right">{data.reference_year}</th>
                    </tr>
                  </thead>
                  <Section section={data.actif_immobilise} year={data.current_year} prevYear={data.reference_year} />
                  <Section section={data.actif_circulant} year={data.current_year} prevYear={data.reference_year} />
                  <Section section={data.tresorerie_actif} year={data.current_year} prevYear={data.reference_year} />
                  <tfoot className="bg-brand-50 border-t-2 border-brand-200">
                    <tr>
                      <td colSpan={2} className="px-4 py-3 font-bold text-brand-800 text-sm">TOTAL ACTIF</td>
                      <td className="td-num font-bold text-brand-800 text-base">{formatCurrency(data.total_actif)}</td>
                      <td className="td-num font-bold text-slate-500">{formatCurrency(data.total_actif_previous)}</td>
                    </tr>
                  </tfoot>
                </table>
              </div>

              {/* PASSIF */}
              <div className="card overflow-hidden">
                <div className="bg-emerald-700 px-4 py-3">
                  <p className="text-white font-bold text-sm uppercase tracking-wider">PASSIF</p>
                </div>
                <table className="w-full">
                  <thead className="bg-slate-50 border-b border-slate-200">
                    <tr>
                      <th className="th w-28">Code</th>
                      <th className="th">Libellé</th>
                      <th className="th text-right">{data.current_year}</th>
                      <th className="th text-right">{data.reference_year}</th>
                    </tr>
                  </thead>
                  <Section section={data.capitaux_propres} year={data.current_year} prevYear={data.reference_year} />
                  <Section section={data.dettes_financieres} year={data.current_year} prevYear={data.reference_year} />
                  <Section section={data.dettes_exploitation} year={data.current_year} prevYear={data.reference_year} />
                  <Section section={data.tresorerie_passif} year={data.current_year} prevYear={data.reference_year} />
                  <tfoot className="bg-emerald-50 border-t-2 border-emerald-200">
                    <tr>
                      <td colSpan={2} className="px-4 py-3 font-bold text-emerald-800 text-sm">TOTAL PASSIF</td>
                      <td className="td-num font-bold text-emerald-800 text-base">{formatCurrency(data.total_passif)}</td>
                      <td className="td-num font-bold text-slate-500">{formatCurrency(data.total_passif_previous)}</td>
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
