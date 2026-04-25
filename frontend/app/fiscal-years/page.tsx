"use client";

import { useEffect, useState } from "react";
import Header from "@/components/layout/Header";
import { PageLoader, ErrorBox } from "@/components/ui/Spinner";
import { getFiscalYears, createFiscalYear, closeFiscalYear, type FiscalYear } from "@/lib/api/accounting";
import { formatDate } from "@/lib/utils";
import { Plus, Lock } from "lucide-react";

export default function FiscalYearsPage() {
  const [years, setYears] = useState<FiscalYear[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", start_date: "", end_date: "" });
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  const load = () => {
    setLoading(true);
    getFiscalYears()
      .then(setYears)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleCreate = async () => {
    setSaving(true);
    setMsg("");
    try {
      await createFiscalYear(form);
      setShowForm(false);
      setForm({ name: "", start_date: "", end_date: "" });
      setMsg("Exercice créé avec succès.");
      load();
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : "Erreur");
    } finally {
      setSaving(false);
    }
  };

  const handleClose = async (id: string, name: string) => {
    if (!confirm(`Clôturer l'exercice ${name} ? Cette action est irréversible.`)) return;
    try {
      await closeFiscalYear(id);
      setMsg(`Exercice ${name} clôturé.`);
      load();
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : "Erreur");
    }
  };

  return (
    <>
      <Header title="Exercices fiscaux" />
      <div className="flex-1 p-6 space-y-4">

        {msg && (
          <div className="rounded-lg bg-emerald-50 border border-emerald-200 p-3 text-sm text-emerald-700">{msg}</div>
        )}

        <div className="flex justify-end">
          <button onClick={() => setShowForm(!showForm)} className="btn-primary">
            <Plus className="w-4 h-4" /> Nouvel exercice
          </button>
        </div>

        {showForm && (
          <div className="card p-5 space-y-4 max-w-md">
            <h3 className="font-semibold text-slate-900">Créer un exercice fiscal</h3>
            <div>
              <label className="label">Nom</label>
              <input className="input" placeholder="Ex: 2026" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label">Date de début</label>
                <input type="date" className="input" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} />
              </div>
              <div>
                <label className="label">Date de fin</label>
                <input type="date" className="input" value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} />
              </div>
            </div>
            <div className="flex gap-2">
              <button onClick={handleCreate} disabled={saving} className="btn-primary">
                {saving ? "Création..." : "Créer"}
              </button>
              <button onClick={() => setShowForm(false)} className="btn-secondary">Annuler</button>
            </div>
          </div>
        )}

        {error && <ErrorBox message={error} />}
        {loading && <PageLoader />}

        {!loading && (
          <div className="card overflow-hidden">
            <table className="w-full">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="th">Nom</th>
                  <th className="th">Début</th>
                  <th className="th">Fin</th>
                  <th className="th">Statut</th>
                  <th className="th">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {years.map((y) => (
                  <tr key={y.id} className="tr-hover">
                    <td className="td font-semibold">{y.name}</td>
                    <td className="td">{formatDate(y.start_date)}</td>
                    <td className="td">{formatDate(y.end_date)}</td>
                    <td className="td">
                      {y.status === "OPEN"
                        ? <span className="badge-green">Ouvert</span>
                        : <span className="badge-gray">Clôturé</span>}
                    </td>
                    <td className="td">
                      {y.status === "OPEN" && (
                        <button onClick={() => handleClose(y.id, y.name)} className="btn-ghost text-xs text-amber-700">
                          <Lock className="w-3.5 h-3.5" /> Clôturer
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {years.length === 0 && (
              <p className="text-center text-slate-400 py-10 text-sm">Aucun exercice fiscal.</p>
            )}
          </div>
        )}
      </div>
    </>
  );
}
