"use client";

import { useEffect, useState } from "react";
import Header from "@/components/layout/Header";
import { PageLoader, ErrorBox } from "@/components/ui/Spinner";
import { getAccounts, type Account } from "@/lib/api/accounting";
import { Search } from "lucide-react";

const CLASS_LABELS: Record<string, string> = {
  "1": "Classe 1 — Capitaux",
  "2": "Classe 2 — Immobilisations",
  "3": "Classe 3 — Opérations",
  "4": "Classe 4 — Tiers",
  "5": "Classe 5 — Trésorerie",
  "6": "Classe 6 — Charges",
  "7": "Classe 7 — Produits",
};

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [classFilter, setClassFilter] = useState("");

  useEffect(() => {
    setLoading(true);
    getAccounts()
      .then((r) => { setAccounts(r.items); setTotal(r.total); })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const filtered = accounts.filter((a) => {
    const q = search.toLowerCase();
    const matchSearch = !q || a.code.includes(q) || a.name.toLowerCase().includes(q);
    const matchClass = !classFilter || a.account_class === classFilter;
    return matchSearch && matchClass;
  });

  return (
    <>
      <Header title="Plan de comptes" subtitle={`${total} comptes · SYSCOHADA`} />
      <div className="flex-1 p-6">

        {/* Filtres */}
        <div className="flex items-center gap-3 mb-4">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              placeholder="Rechercher code ou libellé..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="input pl-9"
            />
          </div>
          <select
            value={classFilter}
            onChange={(e) => setClassFilter(e.target.value)}
            className="input w-52"
          >
            <option value="">Toutes les classes</option>
            {Object.entries(CLASS_LABELS).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
          <span className="text-sm text-slate-500">{filtered.length} compte(s)</span>
        </div>

        {error && <ErrorBox message={error} />}
        {loading && <PageLoader />}

        {!loading && !error && (
          <div className="card overflow-hidden">
            <table className="w-full">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="th">Code</th>
                  <th className="th">Libellé</th>
                  <th className="th">Classe</th>
                  <th className="th">Type</th>
                  <th className="th">Nature</th>
                  <th className="th text-center">Feuille</th>
                  <th className="th text-center">Statut</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filtered.map((a) => (
                  <tr key={a.id} className="tr-hover">
                    <td className="td font-mono font-medium text-brand-700">{a.code}</td>
                    <td className="td">{a.name}</td>
                    <td className="td text-slate-500">{CLASS_LABELS[a.account_class] ?? a.account_class}</td>
                    <td className="td">
                      <span className={a.account_type === "ACTIF" || a.account_type === "CHARGE" ? "badge-blue" : "badge-green"}>
                        {a.account_type}
                      </span>
                    </td>
                    <td className="td">
                      <span className={a.account_nature === "DEBITEUR" ? "badge-yellow" : "badge-gray"}>
                        {a.account_nature}
                      </span>
                    </td>
                    <td className="td text-center">
                      {a.is_leaf ? <span className="badge-green">Oui</span> : <span className="badge-gray">Non</span>}
                    </td>
                    <td className="td text-center">
                      {a.is_active ? <span className="badge-green">Actif</span> : <span className="badge-red">Inactif</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {filtered.length === 0 && (
              <p className="text-center text-slate-400 py-10 text-sm">Aucun compte trouvé.</p>
            )}
          </div>
        )}
      </div>
    </>
  );
}
