"use client";

import { useEffect, useState, useMemo } from "react";
import Header from "@/components/layout/Header";
import { PageLoader, ErrorBox } from "@/components/ui/Spinner";
import {
  getAccounts, createAccount, updateAccount, deactivateAccount,
  type Account, type AccountCreate, type AccountUpdate,
} from "@/lib/api/accounting";
import { Search, Plus, Pencil, Trash2, ChevronRight, ChevronDown, List, GitBranch, Upload, X, AlertCircle } from "lucide-react";
import { importAccountsCsv, type CsvImportResult } from "@/lib/api/accounting";

// ── Constants ────────────────────────────────────────────────────────────────

const CLASS_LABELS: Record<string, string> = {
  "1": "Cl.1 — Capitaux",
  "2": "Cl.2 — Immobilisations",
  "3": "Cl.3 — Opérations",
  "4": "Cl.4 — Tiers",
  "5": "Cl.5 — Trésorerie",
  "6": "Cl.6 — Charges",
  "7": "Cl.7 — Produits",
  "8": "Cl.8 — Spéciaux",
  "9": "Cl.9 — Analytique",
};

const CLASS_DEFAULTS: Record<string, {
  type: "ACTIF" | "PASSIF" | "CHARGE" | "PRODUIT";
  nature: "DEBITEUR" | "CREDITEUR";
}> = {
  "1": { type: "PASSIF",  nature: "CREDITEUR" },
  "2": { type: "ACTIF",   nature: "DEBITEUR"  },
  "3": { type: "ACTIF",   nature: "DEBITEUR"  },
  "5": { type: "ACTIF",   nature: "DEBITEUR"  },
  "6": { type: "CHARGE",  nature: "DEBITEUR"  },
  "7": { type: "PRODUIT", nature: "CREDITEUR" },
};

// ── Tree helpers ─────────────────────────────────────────────────────────────

interface AccountNode extends Account { children: AccountNode[] }

function buildTree(accounts: Account[]): AccountNode[] {
  const map = new Map<string, AccountNode>();
  for (const a of accounts) map.set(a.id, { ...a, children: [] });
  const roots: AccountNode[] = [];
  for (const a of accounts) {
    const node = map.get(a.id)!;
    if (a.parent_id && map.has(a.parent_id)) map.get(a.parent_id)!.children.push(node);
    else roots.push(node);
  }
  const sort = (nodes: AccountNode[]) => {
    nodes.sort((a, b) => a.code.localeCompare(b.code));
    nodes.forEach(n => sort(n.children));
  };
  sort(roots);
  return roots;
}

// ── Blank form ───────────────────────────────────────────────────────────────

const blank = (): AccountCreate & { is_active?: boolean } => ({
  code: "", name: "", short_name: "",
  account_class: "", account_type: "ACTIF", account_nature: "DEBITEUR",
  parent_id: "", currency: "XOF", allow_manual_entry: true, description: "",
});

// ── Page ─────────────────────────────────────────────────────────────────────

export default function AccountsPage() {
  const [accounts, setAccounts]   = useState<Account[]>([]);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState("");
  const [msg, setMsg]             = useState("");

  const [search, setSearch]       = useState("");
  const [classFilter, setClassFilter] = useState("");
  const [viewMode, setViewMode]   = useState<"list" | "tree">("list");
  const [expanded, setExpanded]   = useState<Set<string>>(new Set());

  const [showModal, setShowModal] = useState(false);
  const [editId, setEditId]       = useState<string | null>(null);
  const [form, setForm]           = useState(blank());
  const [saving, setSaving]       = useState(false);
  const [formError, setFormError] = useState("");

  const [showImport, setShowImport]   = useState(false);
  const [importFile, setImportFile]   = useState<File | null>(null);
  const [importing, setImporting]     = useState(false);
  const [importResult, setImportResult] = useState<CsvImportResult | null>(null);
  const [importError, setImportError] = useState("");

  // ── Load ──────────────────────────────────────────────────────────────────

  const load = () => {
    setLoading(true);
    getAccounts({ size: 500 })
      .then(r => setAccounts(r.items))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  // ── Filtered flat list ────────────────────────────────────────────────────

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return accounts
      .filter(a => {
        const matchSearch = !q || a.code.includes(q) || a.name.toLowerCase().includes(q);
        const matchClass  = !classFilter || a.account_class === classFilter;
        return matchSearch && matchClass;
      })
      .sort((a, b) => a.code.localeCompare(b.code));
  }, [accounts, search, classFilter]);

  // ── Tree ──────────────────────────────────────────────────────────────────

  const tree = useMemo(() => buildTree(accounts), [accounts]);

  const toggle = (id: string) =>
    setExpanded(prev => { const s = new Set(prev); s.has(id) ? s.delete(id) : s.add(id); return s; });

  // ── Modal helpers ─────────────────────────────────────────────────────────

  const openCreate = () => {
    setEditId(null); setForm(blank()); setFormError(""); setShowModal(true);
  };

  const openEdit = (a: Account) => {
    setEditId(a.id);
    setForm({
      code: a.code, name: a.name, short_name: a.short_name ?? "",
      account_class: a.account_class, account_type: a.account_type, account_nature: a.account_nature,
      parent_id: a.parent_id ?? "", currency: a.currency,
      allow_manual_entry: a.allow_manual_entry, description: a.description ?? "",
      is_active: a.is_active,
    });
    setFormError(""); setShowModal(true);
  };

  const handleCodeChange = (code: string) => {
    const d = CLASS_DEFAULTS[code[0]];
    setForm(prev => ({
      ...prev, code,
      account_class: CLASS_LABELS[code[0]] ? code[0] : prev.account_class,
      ...(d && !editId ? { account_type: d.type, account_nature: d.nature } : {}),
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true); setFormError("");
    try {
      if (editId) {
        const patch: AccountUpdate = {
          name: form.name,
          short_name: form.short_name || undefined,
          allow_manual_entry: form.allow_manual_entry,
          description: form.description || undefined,
          is_active: (form as { is_active?: boolean }).is_active,
        };
        await updateAccount(editId, patch);
        setMsg("Compte modifié.");
      } else {
        await createAccount({
          code: form.code, name: form.name,
          short_name: form.short_name || undefined,
          account_class: form.account_class,
          account_type: form.account_type, account_nature: form.account_nature,
          parent_id: form.parent_id || undefined,
          currency: form.currency, allow_manual_entry: form.allow_manual_entry,
          description: form.description || undefined,
        });
        setMsg("Compte créé.");
      }
      setShowModal(false); load();
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : "Erreur");
    } finally { setSaving(false); }
  };

  const handleDeactivate = async (a: Account) => {
    if (!confirm(`Désactiver ${a.code} — ${a.name} ?`)) return;
    try { await deactivateAccount(a.id); setMsg("Compte désactivé."); load(); }
    catch (e: unknown) { setMsg(e instanceof Error ? e.message : "Erreur"); }
  };

  const handleImport = async () => {
    if (!importFile) return;
    setImporting(true); setImportError(""); setImportResult(null);
    try {
      const r = await importAccountsCsv(importFile);
      setImportResult(r);
      setImportFile(null);
      load();
    } catch (e: unknown) {
      setImportError(e instanceof Error ? e.message : "Erreur");
    } finally { setImporting(false); }
  };

  // ── Shared sub-components ─────────────────────────────────────────────────

  const TypeBadge   = ({ t }: { t: string }) => (
    <span className={t === "ACTIF" || t === "CHARGE" ? "badge-blue" : "badge-green"}>{t}</span>
  );
  const NatureBadge = ({ n }: { n: string }) => (
    <span className={n === "DEBITEUR" ? "badge-yellow" : "badge-gray"}>{n}</span>
  );
  const Actions = ({ a }: { a: Account }) => (
    <div className="flex gap-1 items-center">
      <button onClick={() => openEdit(a)} title="Modifier"
        className="p-1 rounded text-slate-400 hover:text-brand-600 hover:bg-slate-100">
        <Pencil className="w-3.5 h-3.5" />
      </button>
      {a.is_active && (
        <button onClick={() => handleDeactivate(a)} title="Désactiver"
          className="p-1 rounded text-slate-400 hover:text-red-500 hover:bg-red-50">
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );

  // ── Tree row (recursive) ──────────────────────────────────────────────────

  const TreeRow = ({ node, depth = 0 }: { node: AccountNode; depth?: number }) => {
    const hasKids = node.children.length > 0;
    const open    = expanded.has(node.id);
    return (
      <>
        <tr className={`tr-hover ${!node.is_active ? "opacity-40" : ""}`}>
          <td className="td font-mono text-brand-700 font-medium whitespace-nowrap">
            <div className="flex items-center gap-1" style={{ paddingLeft: depth * 20 }}>
              {hasKids
                ? <button onClick={() => toggle(node.id)} className="text-slate-400 hover:text-slate-700">
                    {open ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                  </button>
                : <span className="w-3.5 inline-block" />}
              {node.code}
            </div>
          </td>
          <td className="td">{node.name}{node.short_name && <span className="ml-1 text-slate-400 text-xs">({node.short_name})</span>}</td>
          <td className="td"><TypeBadge t={node.account_type} /></td>
          <td className="td"><NatureBadge n={node.account_nature} /></td>
          <td className="td text-center">
            {node.is_leaf
              ? <span className="badge-green text-xs">Feuille</span>
              : <span className="badge-gray text-xs">Nœud</span>}
          </td>
          <td className="td text-center">
            {node.is_active
              ? <span className="badge-green text-xs">Actif</span>
              : <span className="badge-red text-xs">Inactif</span>}
          </td>
          <td className="td"><Actions a={node} /></td>
        </tr>
        {open && node.children.map(c => <TreeRow key={c.id} node={c} depth={depth + 1} />)}
      </>
    );
  };

  // ── Modal ─────────────────────────────────────────────────────────────────

  const formData = form as typeof form & { is_active?: boolean };
  const parentCandidates = accounts
    .filter(a => a.is_active && a.account_class === form.account_class)
    .sort((a, b) => a.code.localeCompare(b.code));

  const Modal = () => (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg overflow-hidden flex flex-col max-h-[90vh]">
        <div className="p-5 border-b border-slate-200 flex-shrink-0">
          <h2 className="font-semibold text-slate-900 text-lg">
            {editId ? "Modifier le compte" : "Nouveau compte"}
          </h2>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col flex-1 overflow-hidden">
          <div className="p-5 space-y-4 overflow-y-auto flex-1">
            {formError && <div className="rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700">{formError}</div>}

            {/* Code + Classe */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label">Code *</label>
                <input required pattern="\d+" maxLength={20} placeholder="ex: 411000"
                  value={form.code}
                  onChange={e => handleCodeChange(e.target.value)}
                  className="input font-mono" disabled={!!editId} />
                {!editId && <p className="text-xs text-slate-400 mt-1">Chiffres uniquement</p>}
              </div>
              <div>
                <label className="label">Classe *</label>
                <select required value={form.account_class}
                  onChange={e => setForm({ ...form, account_class: e.target.value })}
                  className="input" disabled={!!editId}>
                  <option value="">Choisir</option>
                  {Object.entries(CLASS_LABELS).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Libellé */}
            <div>
              <label className="label">Libellé *</label>
              <input required minLength={2} maxLength={200} placeholder="Nom complet du compte"
                value={form.name}
                onChange={e => setForm({ ...form, name: e.target.value })}
                className="input" />
            </div>

            {/* Libellé court */}
            <div>
              <label className="label">Libellé court</label>
              <input maxLength={50} placeholder="Abréviation (optionnel)"
                value={form.short_name ?? ""}
                onChange={e => setForm({ ...form, short_name: e.target.value })}
                className="input" />
            </div>

            {/* Type + Nature (création uniquement) */}
            {!editId && (
              <>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="label">Type *</label>
                    <select required value={form.account_type}
                      onChange={e => setForm({ ...form, account_type: e.target.value as Account["account_type"] })}
                      className="input">
                      <option value="ACTIF">ACTIF</option>
                      <option value="PASSIF">PASSIF</option>
                      <option value="CHARGE">CHARGE</option>
                      <option value="PRODUIT">PRODUIT</option>
                    </select>
                  </div>
                  <div>
                    <label className="label">Nature *</label>
                    <select required value={form.account_nature}
                      onChange={e => setForm({ ...form, account_nature: e.target.value as Account["account_nature"] })}
                      className="input">
                      <option value="DEBITEUR">DÉBITEUR</option>
                      <option value="CREDITEUR">CRÉDITEUR</option>
                    </select>
                  </div>
                </div>

                {/* Compte parent */}
                <div>
                  <label className="label">Compte parent</label>
                  <select value={form.parent_id ?? ""}
                    onChange={e => setForm({ ...form, parent_id: e.target.value })}
                    className="input">
                    <option value="">Aucun (compte racine de classe)</option>
                    {parentCandidates.map(a => (
                      <option key={a.id} value={a.id}>{a.code} — {a.name}</option>
                    ))}
                  </select>
                </div>
              </>
            )}

            {/* Statut (modification uniquement) */}
            {editId && (
              <div className="flex items-center gap-2">
                <input type="checkbox" id="is_active_chk"
                  checked={formData.is_active ?? true}
                  onChange={e => setForm({ ...form, is_active: e.target.checked } as typeof form)}
                  className="rounded" />
                <label htmlFor="is_active_chk" className="text-sm text-slate-700">Compte actif</label>
              </div>
            )}

            {/* Description */}
            <div>
              <label className="label">Description</label>
              <textarea rows={2} maxLength={500} placeholder="Notes ou instructions (optionnel)"
                value={form.description ?? ""}
                onChange={e => setForm({ ...form, description: e.target.value })}
                className="input resize-none" />
            </div>

            {/* Saisie manuelle */}
            <div className="flex items-center gap-2">
              <input type="checkbox" id="allow_manual"
                checked={form.allow_manual_entry ?? true}
                onChange={e => setForm({ ...form, allow_manual_entry: e.target.checked })}
                className="rounded" />
              <label htmlFor="allow_manual" className="text-sm text-slate-700">
                Autoriser les saisies manuelles
              </label>
            </div>
          </div>

          <div className="p-4 border-t border-slate-200 flex gap-3 justify-end flex-shrink-0">
            <button type="button" onClick={() => setShowModal(false)} className="btn-secondary">Annuler</button>
            <button type="submit" disabled={saving} className="btn-primary">
              {saving ? "Enregistrement..." : editId ? "Enregistrer" : "Créer le compte"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <>
      <Header title="Plan de comptes" subtitle={`${accounts.length} compte(s) au total`} />
      <div className="flex-1 p-6 space-y-4">

        {msg && (
          <div className="rounded-lg bg-emerald-50 border border-emerald-200 p-3 text-sm text-emerald-700">{msg}</div>
        )}

        {/* Toolbar */}
        <div className="flex items-center gap-3 flex-wrap">
          <div className="relative flex-1 min-w-48 max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input placeholder="Code ou libellé…" value={search}
              onChange={e => setSearch(e.target.value)} className="input pl-9" />
          </div>

          <select value={classFilter} onChange={e => setClassFilter(e.target.value)} className="input w-52">
            <option value="">Toutes les classes</option>
            {Object.entries(CLASS_LABELS).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>

          {/* Vue toggle */}
          <div className="flex rounded-lg border border-slate-200 overflow-hidden text-xs">
            <button onClick={() => setViewMode("list")}
              className={`px-3 py-2 flex items-center gap-1.5 ${viewMode === "list" ? "bg-brand-600 text-white" : "bg-white text-slate-600 hover:bg-slate-50"}`}>
              <List className="w-3.5 h-3.5" /> Liste
            </button>
            <button onClick={() => setViewMode("tree")}
              className={`px-3 py-2 flex items-center gap-1.5 ${viewMode === "tree" ? "bg-brand-600 text-white" : "bg-white text-slate-600 hover:bg-slate-50"}`}>
              <GitBranch className="w-3.5 h-3.5" /> Arborescence
            </button>
          </div>

          {viewMode === "tree" && (
            <div className="flex gap-2">
              <button onClick={() => setExpanded(new Set(accounts.map(a => a.id)))}
                className="btn-ghost text-xs">Tout déplier</button>
              <button onClick={() => setExpanded(new Set())}
                className="btn-ghost text-xs">Tout replier</button>
            </div>
          )}

          <span className="text-sm text-slate-500">
            {viewMode === "list" ? `${filtered.length} affiché(s)` : `${accounts.length} au total`}
          </span>

          <div className="flex gap-2 ml-auto">
            <button onClick={() => { setShowImport(v => !v); setImportResult(null); setImportError(""); }}
              className="btn-secondary">
              <Upload className="w-4 h-4" /> Importer CSV
            </button>
            <button onClick={openCreate} className="btn-primary">
              <Plus className="w-4 h-4" /> Nouveau compte
            </button>
          </div>
        </div>

        {/* Panneau import CSV */}
        {showImport && (
          <div className="card p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-slate-800 flex items-center gap-2">
                <Upload className="w-4 h-4" /> Import CSV
              </h3>
              <button onClick={() => setShowImport(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="text-xs text-slate-500 bg-slate-50 rounded-lg p-3 font-mono">
              <p className="font-semibold text-slate-600 mb-1">Format attendu (virgule ou point-virgule) :</p>
              <p>code,name,account_class,account_type,account_nature,parent_code,allow_manual_entry,description</p>
              <p className="mt-1 text-slate-400">101000,Capital social,1,PASSIF,CREDITEUR,10,true,</p>
              <p className="mt-2 text-slate-500 font-sans">
                account_class: 1-9 · account_type: ACTIF/PASSIF/CHARGE/PRODUIT · account_nature: DEBITEUR/CREDITEUR
              </p>
            </div>

            {importResult && (
              <div className="rounded-lg bg-emerald-50 border border-emerald-200 p-3 space-y-1">
                <p className="text-sm font-semibold text-emerald-800">Import terminé</p>
                <p className="text-xs text-emerald-700">
                  {importResult.accounts_created} créé(s) · {importResult.accounts_skipped} ignoré(s) (déjà présents)
                </p>
                {importResult.errors.length > 0 && (
                  <div className="mt-2 space-y-1">
                    <p className="text-xs font-semibold text-amber-700 flex items-center gap-1">
                      <AlertCircle className="w-3.5 h-3.5" /> {importResult.errors.length} avertissement(s)
                    </p>
                    {importResult.errors.map((e, i) => (
                      <p key={i} className="text-xs text-amber-600 pl-4">{e}</p>
                    ))}
                  </div>
                )}
              </div>
            )}

            {importError && <p className="text-sm text-red-600">{importError}</p>}

            <div className="flex items-center gap-3">
              <input
                type="file" accept=".csv"
                onChange={e => { setImportFile(e.target.files?.[0] ?? null); setImportResult(null); }}
                className="text-sm text-slate-600 file:mr-3 file:btn-secondary file:text-xs"
              />
              <button onClick={handleImport} disabled={!importFile || importing} className="btn-primary text-sm">
                {importing ? "Import en cours..." : "Importer"}
              </button>
            </div>
          </div>
        )}

        {error && <ErrorBox message={error} />}
        {loading && <PageLoader />}

        {!loading && !error && (
          <div className="card overflow-hidden">
            <table className="w-full">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="th">Code</th>
                  <th className="th">Libellé</th>
                  {viewMode === "list" && <th className="th">Classe</th>}
                  <th className="th">Type</th>
                  <th className="th">Nature</th>
                  <th className="th text-center">Feuille</th>
                  <th className="th text-center">Statut</th>
                  <th className="th w-20">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {viewMode === "list"
                  ? filtered.map(a => (
                      <tr key={a.id} className={`tr-hover ${!a.is_active ? "opacity-40" : ""}`}>
                        <td className="td font-mono font-medium text-brand-700">{a.code}</td>
                        <td className="td">
                          {a.name}
                          {a.short_name && <span className="ml-1 text-slate-400 text-xs">({a.short_name})</span>}
                        </td>
                        <td className="td text-slate-500 text-xs">{CLASS_LABELS[a.account_class] ?? a.account_class}</td>
                        <td className="td"><TypeBadge t={a.account_type} /></td>
                        <td className="td"><NatureBadge n={a.account_nature} /></td>
                        <td className="td text-center">
                          {a.is_leaf
                            ? <span className="badge-green text-xs">Feuille</span>
                            : <span className="badge-gray text-xs">Nœud</span>}
                        </td>
                        <td className="td text-center">
                          {a.is_active
                            ? <span className="badge-green text-xs">Actif</span>
                            : <span className="badge-red text-xs">Inactif</span>}
                        </td>
                        <td className="td"><Actions a={a} /></td>
                      </tr>
                    ))
                  : tree.map(n => <TreeRow key={n.id} node={n} depth={0} />)}
              </tbody>
            </table>
            {(viewMode === "list" ? filtered : accounts).length === 0 && (
              <p className="text-center text-slate-400 py-10 text-sm">Aucun compte trouvé.</p>
            )}
          </div>
        )}
      </div>

      {showModal && <Modal />}
    </>
  );
}
