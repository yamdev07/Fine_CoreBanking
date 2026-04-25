"use client";

import { useState } from "react";
import Header from "@/components/layout/Header";
import { PageLoader, ErrorBox } from "@/components/ui/Spinner";
import ExportButtons from "@/components/ui/ExportButtons";
import { getBceao, type BceaoRatioLine } from "@/lib/api/reporting";
import { formatCurrency, formatPct, today } from "@/lib/utils";
import { CheckCircle2, XCircle, AlertTriangle } from "lucide-react";

const REPORTING_URL = process.env.NEXT_PUBLIC_REPORTING_URL ?? "http://localhost:8001";

function RatioRow({ r }: { r: BceaoRatioLine }) {
  return (
    <tr className="tr-hover border-b border-slate-100">
      <td className="td font-mono font-bold text-brand-700">{r.code_ratio}</td>
      <td className="td text-sm">{r.libelle}</td>
      <td className="td-num">{formatCurrency(r.numerateur)}</td>
      <td className="td-num">{formatCurrency(r.denominateur)}</td>
      <td className={`td-num font-bold text-base ${r.conforme ? "text-emerald-700" : "text-red-600"}`}>
        {formatPct(r.valeur)}
      </td>
      <td className="td text-slate-500 text-xs">{r.norme}</td>
      <td className="td text-center">
        {r.conforme
          ? <CheckCircle2 className="w-5 h-5 text-emerald-500 mx-auto" />
          : <XCircle className="w-5 h-5 text-red-500 mx-auto" />}
      </td>
    </tr>
  );
}

export default function BceaoPage() {
  const [date, setDate] = useState(today());
  const [agrement, setAgrement] = useState("IMF-BJ-001");
  const [data, setData] = useState<Awaited<ReturnType<typeof getBceao>> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = () => {
    setLoading(true);
    setError("");
    getBceao(date, agrement)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  const ratios = data ? [
    data.ratio_solvabilite,
    data.ratio_liquidite,
    data.ratio_transformation,
    data.ratio_division_risques,
    data.ratio_couverture_risques,
  ] : [];

  return (
    <>
      <Header title="États prudentiels BCEAO/UEMOA" subtitle="Ratios réglementaires — 5 indicateurs" />
      <div className="flex-1 p-6 space-y-4">

        <div className="flex items-end gap-3 flex-wrap">
          <div>
            <label className="label">Date d'arrêté</label>
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="input w-40" />
          </div>
          <div>
            <label className="label">N° Agrément BCEAO</label>
            <input value={agrement} onChange={(e) => setAgrement(e.target.value)} className="input w-44" placeholder="IMF-BJ-001" />
          </div>
          <button onClick={load} className="btn-primary">Calculer</button>
          {data && (
            <ExportButtons
              pdfUrl={`${REPORTING_URL}/api/v1/reports/bceao-prudential?as_of_date=${date}&numero_agrement=${agrement}&format=pdf`}
            />
          )}
        </div>

        {error && <ErrorBox message={error} />}
        {loading && <PageLoader />}

        {data && !loading && (
          <>
            {/* Score */}
            <div className="grid grid-cols-3 gap-4">
              <div className="card p-5 text-center">
                <p className="text-xs text-slate-500 mb-2">Ratios conformes</p>
                <p className="text-4xl font-bold text-emerald-600">{data.ratios_conformes}</p>
                <p className="text-xs text-slate-400 mt-1">sur {data.total_ratios}</p>
              </div>
              <div className="card p-5 text-center">
                <p className="text-xs text-slate-500 mb-2">Ratios non conformes</p>
                <p className={`text-4xl font-bold ${data.ratios_non_conformes > 0 ? "text-red-600" : "text-slate-300"}`}>
                  {data.ratios_non_conformes}
                </p>
              </div>
              <div className="card p-5 text-center">
                <p className="text-xs text-slate-500 mb-2">Fonds propres nets</p>
                <p className="text-xl font-bold text-slate-900">{formatCurrency(data.fonds_propres_nets)}</p>
              </div>
            </div>

            {data.observations && (
              <div className="flex items-start gap-3 p-4 rounded-lg bg-amber-50 border border-amber-200">
                <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
                <p className="text-sm text-amber-800">{data.observations}</p>
              </div>
            )}

            <div className="card overflow-hidden">
              <table className="w-full">
                <thead className="bg-slate-50 border-b border-slate-200">
                  <tr>
                    <th className="th w-16">Code</th>
                    <th className="th">Libellé</th>
                    <th className="th text-right">Numérateur</th>
                    <th className="th text-right">Dénominateur</th>
                    <th className="th text-right">Valeur</th>
                    <th className="th">Norme</th>
                    <th className="th text-center">Conforme</th>
                  </tr>
                </thead>
                <tbody>
                  {ratios.map((r) => <RatioRow key={r.code_ratio} r={r} />)}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </>
  );
}
