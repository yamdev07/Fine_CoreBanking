"use client";

import { useEffect, useState } from "react";
import Header from "@/components/layout/Header";
import { PageLoader, ErrorBox } from "@/components/ui/Spinner";
import { getAccounts, type Account } from "@/lib/api/accounting";
import { formatCurrency, formatDate, today, startOfYear } from "@/lib/utils";

const REPORTING_URL = process.env.NEXT_PUBLIC_REPORTING_URL ?? "http://localhost:8001";

export default function GeneralLedgerPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [accountCode, setAccountCode] = useState("");
  const [startDate, setStartDate] = useState(startOfYear());
  const [endDate, setEndDate] = useState(today());
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getAccounts({ is_leaf: true }).then((r) => setAccounts(r.items)).catch(() => {});
  }, []);

  const load = () => {
    if (!accountCode) return;
    setLoading(true);
    setError("");
    fetch(`${REPORTING_URL}/api/v1/reports/general-ledger?account_code=${accountCode}&start_date=${startDate}&end_date=${endDate}&size=500`)
      .then((r) => r.json())
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  return (
    <>
      <Header title="Grand livre" subtitle="Détail des mouvements par compte" />
      <div className="flex-1 p-6 space-y-4">

        <div className="flex items-end gap-3 flex-wrap">
          <div className="w-72">
            <label className="label">Compte</label>
            <select value={accountCode} onChange={(e) => setAccountCode(e.target.value)} className="input">
              <option value="">Sélectionner un compte</option>
              {accounts.map((a) => (
                <option key={a.id} value={a.code}>{a.code} — {a.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">Du</label>
            <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="input w-40" />
          </div>
          <div>
            <label className="label">Au</label>
            <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className="input w-40" />
          </div>
          <button onClick={load} disabled={!accountCode} className="btn-primary">Générer</button>
        </div>

        {error && <ErrorBox message={error} />}
        {loading && <PageLoader />}

        {data && !loading && (
          <>
            <div className="flex items-center gap-6 p-4 card">
              <div>
                <p className="text-xs text-slate-500">Compte</p>
                <p className="font-bold text-slate-900">{data.account_code} — {data.account_name}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Solde ouverture</p>
                <p className="font-bold">{formatCurrency(data.opening_balance)} <span className="text-xs font-normal text-slate-500">{data.opening_balance_nature}</span></p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Solde clôture</p>
                <p className="font-bold">{formatCurrency(data.closing_balance)} <span className="text-xs font-normal text-slate-500">{data.closing_balance_nature}</span></p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Mouvements</p>
                <p className="font-bold">{data.movement_count}</p>
              </div>
            </div>

            <div className="card overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[800px]">
                  <thead className="bg-slate-50 border-b border-slate-200">
                    <tr>
                      <th className="th">N° Écriture</th>
                      <th className="th">Date</th>
                      <th className="th">Journal</th>
                      <th className="th">Description</th>
                      <th className="th text-right">Débit</th>
                      <th className="th text-right">Crédit</th>
                      <th className="th text-right">Solde progressif</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {data.movements.map((m: any, i: number) => (
                      <tr key={i} className="tr-hover">
                        <td className="td font-mono text-xs text-brand-700">{m.entry_number}</td>
                        <td className="td">{formatDate(m.entry_date)}</td>
                        <td className="td font-medium">{m.journal_code}</td>
                        <td className="td max-w-xs truncate">{m.description}</td>
                        <td className="td-num">{parseFloat(m.debit_amount) > 0 ? formatCurrency(m.debit_amount) : "—"}</td>
                        <td className="td-num">{parseFloat(m.credit_amount) > 0 ? formatCurrency(m.credit_amount) : "—"}</td>
                        <td className="td-num font-semibold">
                          {formatCurrency(m.running_balance)}
                          <span className="text-xs font-normal text-slate-400 ml-1">{m.balance_nature}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </div>
    </>
  );
}
