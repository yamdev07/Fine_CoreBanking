"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Header from "@/components/layout/Header";
import { PageLoader, ErrorBox } from "@/components/ui/Spinner";
import { getJournalEntries, postJournalEntry, cancelJournalEntry, type JournalEntry } from "@/lib/api/accounting";
import { formatCurrency, formatDate } from "@/lib/utils";
import { Plus, CheckCircle, XCircle, ChevronLeft, ChevronRight } from "lucide-react";

const STATUS_LABELS: Record<string, string> = {
  DRAFT: "Brouillon",
  POSTED: "Validée",
  CANCELLED: "Annulée",
};

export default function JournalsPage() {
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");

  const load = (p = page) => {
    setLoading(true);
    getJournalEntries({ status: statusFilter || undefined, page: p, size: 50 })
      .then((r) => { setEntries(r.items); setTotal(r.total); setPages(r.pages); })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(1); setPage(1); }, [statusFilter]);
  useEffect(() => { load(page); }, [page]);

  const handlePost = async (id: string) => {
    try {
      await postJournalEntry(id);
      setMsg("Écriture validée.");
      load();
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : "Erreur");
    }
  };

  const handleCancel = async (id: string) => {
    if (!confirm("Annuler cette écriture ?")) return;
    try {
      await cancelJournalEntry(id);
      setMsg("Écriture annulée.");
      load();
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : "Erreur");
    }
  };

  return (
    <>
      <Header title="Écritures comptables" subtitle={`${total} écriture(s) au total`} />
      <div className="flex-1 p-6 space-y-4">

        {msg && (
          <div className="rounded-lg bg-emerald-50 border border-emerald-200 p-3 text-sm text-emerald-700">{msg}</div>
        )}

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="input w-44"
            >
              <option value="">Tous les statuts</option>
              <option value="DRAFT">Brouillons</option>
              <option value="POSTED">Validées</option>
              <option value="CANCELLED">Annulées</option>
            </select>
          </div>
          <Link href="/journals/new" className="btn-primary">
            <Plus className="w-4 h-4" /> Nouvelle écriture
          </Link>
        </div>

        {error && <ErrorBox message={error} />}
        {loading && <PageLoader />}

        {!loading && !error && (
          <>
            <div className="card overflow-hidden">
              <table className="w-full">
                <thead className="bg-slate-50 border-b border-slate-200">
                  <tr>
                    <th className="th">N° Écriture</th>
                    <th className="th">Journal</th>
                    <th className="th">Date</th>
                    <th className="th">Description</th>
                    <th className="th text-right">Débit</th>
                    <th className="th text-right">Crédit</th>
                    <th className="th">Statut</th>
                    <th className="th">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {entries.map((e) => (
                    <tr key={e.id} className="tr-hover">
                      <td className="td font-mono text-brand-700 font-medium">{e.entry_number}</td>
                      <td className="td font-medium">{e.journal_code}</td>
                      <td className="td">{formatDate(e.entry_date)}</td>
                      <td className="td max-w-xs truncate">{e.description}</td>
                      <td className="td-num">{formatCurrency(e.total_debit)}</td>
                      <td className="td-num">{formatCurrency(e.total_credit)}</td>
                      <td className="td">
                        <span className={
                          e.status === "POSTED" ? "badge-green" :
                          e.status === "CANCELLED" ? "badge-red" : "badge-yellow"
                        }>
                          {STATUS_LABELS[e.status]}
                        </span>
                      </td>
                      <td className="td">
                        {e.status === "DRAFT" && (
                          <div className="flex items-center gap-1">
                            <button onClick={() => handlePost(e.id)} className="btn-ghost text-xs text-emerald-700">
                              <CheckCircle className="w-3.5 h-3.5" /> Valider
                            </button>
                            <button onClick={() => handleCancel(e.id)} className="btn-ghost text-xs text-red-600">
                              <XCircle className="w-3.5 h-3.5" /> Annuler
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {entries.length === 0 && (
                <p className="text-center text-slate-400 py-10 text-sm">Aucune écriture.</p>
              )}
            </div>

            {/* Pagination */}
            {pages > 1 && (
              <div className="flex items-center justify-center gap-2">
                <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} className="btn-secondary">
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <span className="text-sm text-slate-600">Page {page} / {pages}</span>
                <button onClick={() => setPage(p => Math.min(pages, p + 1))} disabled={page === pages} className="btn-secondary">
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </>
  );
}
