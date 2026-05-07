"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Header from "@/components/layout/Header";
import { ErrorBox } from "@/components/ui/Spinner";
import { getJournals, getAccounts, createJournalEntry, type Journal, type Account } from "@/lib/api/accounting";
import { today } from "@/lib/utils";
import { Plus, Trash2, ArrowLeft } from "lucide-react";
import Link from "next/link";

interface Line {
  account_code: string;
  debit_amount: string;
  credit_amount: string;
  description: string;
}

export default function NewJournalEntryPage() {
  const router = useRouter();
  const [journals, setJournals] = useState<Journal[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const [form, setForm] = useState({
    journal_id: "",
    entry_date: today(),
    description: "",
    reference: "",
  });

  const [lines, setLines] = useState<Line[]>([
    { account_code: "", debit_amount: "", credit_amount: "", description: "" },
    { account_code: "", debit_amount: "", credit_amount: "", description: "" },
  ]);

  useEffect(() => {
    Promise.all([getJournals(), getAccounts({ is_leaf: true })])
      .then(([j, a]) => { setJournals(j); setAccounts(a.items); })
      .catch((e) => setError(e.message));
  }, []);

  const addLine = () =>
    setLines([...lines, { account_code: "", debit_amount: "", credit_amount: "", description: "" }]);

  const removeLine = (i: number) => setLines(lines.filter((_, idx) => idx !== i));

  const updateLine = (i: number, field: keyof Line, value: string) => {
    const updated = [...lines];
    updated[i] = { ...updated[i], [field]: value };
    setLines(updated);
  };

  const totalDebit = lines.reduce((s, l) => s + (parseFloat(l.debit_amount) || 0), 0);
  const totalCredit = lines.reduce((s, l) => s + (parseFloat(l.credit_amount) || 0), 0);
  const isBalanced = Math.abs(totalDebit - totalCredit) < 0.01;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isBalanced) { setError("L'écriture est déséquilibrée."); return; }
    setSaving(true);
    setError("");
    try {
      // Résoudre les codes de comptes en IDs
      const accountByCode = Object.fromEntries(accounts.map((a) => [a.code, a.id]));
      await createJournalEntry({
        ...form,
        lines: lines.map((l) => ({
          account_id: accountByCode[l.account_code] ?? l.account_code,
          debit_amount: parseFloat(l.debit_amount) || 0,
          credit_amount: parseFloat(l.credit_amount) || 0,
          description: l.description || undefined,
        })),
      });
      router.push("/journals");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erreur");
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <Header title="Nouvelle écriture comptable" />
      <div className="flex-1 p-6 max-w-5xl">
        <Link href="/journals" className="btn-ghost text-slate-500 mb-6 inline-flex">
          <ArrowLeft className="w-4 h-4" /> Retour aux écritures
        </Link>

        <form onSubmit={handleSubmit} className="space-y-6">
          {error && <ErrorBox message={error} />}

          {/* En-tête */}
          <div className="card p-5">
            <h3 className="font-semibold text-slate-900 mb-4">En-tête de l'écriture</h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Journal *</label>
                <select
                  required
                  value={form.journal_id}
                  onChange={(e) => setForm({ ...form, journal_id: e.target.value })}
                  className="input"
                >
                  <option value="">Sélectionner un journal</option>
                  {journals.map((j) => (
                    <option key={j.id} value={j.id}>{j.code} — {j.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label">Date comptable *</label>
                <input
                  type="date"
                  required
                  value={form.entry_date}
                  onChange={(e) => setForm({ ...form, entry_date: e.target.value })}
                  className="input"
                />
              </div>
              <div className="col-span-2">
                <label className="label">Description *</label>
                <input
                  required
                  placeholder="Libellé de l'écriture"
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  className="input"
                />
              </div>
              <div>
                <label className="label">Référence</label>
                <input
                  placeholder="Numéro de pièce, facture..."
                  value={form.reference}
                  onChange={(e) => setForm({ ...form, reference: e.target.value })}
                  className="input"
                />
              </div>
            </div>
          </div>

          {/* Lignes */}
          <div className="card overflow-hidden">
            <div className="p-4 border-b border-slate-200 flex items-center justify-between">
              <h3 className="font-semibold text-slate-900">Lignes comptables</h3>
              <button type="button" onClick={addLine} className="btn-ghost text-sm">
                <Plus className="w-4 h-4" /> Ajouter une ligne
              </button>
            </div>
            <table className="w-full">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="th w-48">Compte</th>
                  <th className="th">Libellé</th>
                  <th className="th w-36 text-right">Débit</th>
                  <th className="th w-36 text-right">Crédit</th>
                  <th className="th w-10"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {lines.map((line, i) => (
                  <tr key={i}>
                    <td className="px-4 py-2">
                      <select
                        value={line.account_code}
                        onChange={(e) => updateLine(i, "account_code", e.target.value)}
                        className="input text-xs"
                      >
                        <option value="">Choisir un compte</option>
                        {accounts.map((a) => (
                          <option key={a.id} value={a.code}>{a.code} — {a.name}</option>
                        ))}
                      </select>
                    </td>
                    <td className="px-4 py-2">
                      <input
                        placeholder="Libellé ligne"
                        value={line.description}
                        onChange={(e) => updateLine(i, "description", e.target.value)}
                        className="input text-xs"
                      />
                    </td>
                    <td className="px-4 py-2">
                      <input
                        type="number"
                        min="0"
                        step="1"
                        placeholder="0"
                        value={line.debit_amount}
                        onChange={(e) => updateLine(i, "debit_amount", e.target.value)}
                        className="input text-right font-mono text-xs"
                      />
                    </td>
                    <td className="px-4 py-2">
                      <input
                        type="number"
                        min="0"
                        step="1"
                        placeholder="0"
                        value={line.credit_amount}
                        onChange={(e) => updateLine(i, "credit_amount", e.target.value)}
                        className="input text-right font-mono text-xs"
                      />
                    </td>
                    <td className="px-4 py-2">
                      {lines.length > 2 && (
                        <button type="button" onClick={() => removeLine(i)} className="text-slate-400 hover:text-red-500">
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="bg-slate-50 border-t-2 border-slate-200">
                <tr>
                  <td colSpan={2} className="px-4 py-3 text-sm font-semibold text-slate-600">Total</td>
                  <td className="px-4 py-3 text-right font-mono font-bold text-slate-900">
                    {totalDebit.toLocaleString("fr-FR")}
                  </td>
                  <td className={`px-4 py-3 text-right font-mono font-bold ${isBalanced ? "text-emerald-700" : "text-red-600"}`}>
                    {totalCredit.toLocaleString("fr-FR")}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {isBalanced
                      ? <span className="badge-green">✓ Équilibrée</span>
                      : <span className="badge-red">Déséquilibrée</span>}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>

          <div className="flex gap-3">
            <button type="submit" disabled={saving || !isBalanced} className="btn-primary">
              {saving ? "Enregistrement..." : "Enregistrer en brouillon"}
            </button>
            <Link href="/journals" className="btn-secondary">Annuler</Link>
          </div>
        </form>
      </div>
    </>
  );
}
