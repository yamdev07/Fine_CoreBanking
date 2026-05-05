"use client";

import { useEffect, useRef, useState } from "react";
import Header from "@/components/layout/Header";
import { PageLoader, ErrorBox } from "@/components/ui/Spinner";
import {
  getPlanTemplates, loadPlanTemplate, getAccounts, importAccounts, downloadImportTemplate,
  type PlanTemplate, type LoadTemplateResult, type CsvImportResult,
} from "@/lib/api/accounting";
import { CheckCircle2, Building2, Users, Wrench, ChevronRight, AlertTriangle, Upload, FileText } from "lucide-react";
import Link from "next/link";

const TARGET_ICON: Record<string, React.ComponentType<{ className?: string }>> = {
  MICROFINANCE: Users,
  BANK:         Building2,
  CUSTOM:       Wrench,
};

const TARGET_COLOR: Record<string, string> = {
  MICROFINANCE: "border-emerald-200 bg-emerald-50",
  BANK:         "border-brand-200 bg-brand-50",
  CUSTOM:       "border-slate-200 bg-slate-50",
};

const TARGET_BADGE: Record<string, string> = {
  MICROFINANCE: "badge-green",
  BANK:         "badge-blue",
  CUSTOM:       "badge-gray",
};

const TARGET_LABEL: Record<string, string> = {
  MICROFINANCE: "Microfinance / IMF",
  BANK:         "Banque Commerciale",
  CUSTOM:       "Personnalisé",
};

export default function PlanSetupPage() {
  const [templates, setTemplates]   = useState<PlanTemplate[]>([]);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState("");
  const [existingCount, setExistingCount] = useState<number | null>(null);

  const [selected, setSelected]     = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [loading2, setLoading2]     = useState(false);
  const [result, setResult]         = useState<LoadTemplateResult | null>(null);
  const [loadError, setLoadError]   = useState("");

  // Custom file import state
  const fileInputRef                         = useRef<HTMLInputElement>(null);
  const [importFile, setImportFile]          = useState<File | null>(null);
  const [importing, setImporting]            = useState(false);
  const [importResult, setImportResult]      = useState<CsvImportResult | null>(null);
  const [importError, setImportError]        = useState("");

  useEffect(() => {
    Promise.all([getPlanTemplates(), getAccounts({ size: 1 })])
      .then(([t, a]) => { setTemplates(t); setExistingCount(a.total); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const handleImport = async () => {
    if (!importFile) return;
    setImporting(true); setImportError("");
    try {
      const r = await importAccounts(importFile);
      setImportResult(r);
      setImportFile(null);
      getAccounts({ size: 1 }).then(a => setExistingCount(a.total));
    } catch (e: unknown) {
      setImportError(e instanceof Error ? e.message : "Erreur lors de l'import");
    } finally {
      setImporting(false);
    }
  };

  const handleLoad = async () => {
    if (!selected) return;
    setLoading2(true); setLoadError("");
    try {
      const r = await loadPlanTemplate(selected);
      setResult(r);
      setConfirming(false);
      // Refresh account count
      getAccounts({ size: 1 }).then(a => setExistingCount(a.total));
    } catch (e: unknown) {
      setLoadError(e instanceof Error ? e.message : "Erreur");
    } finally {
      setLoading2(false);
    }
  };

  return (
    <>
      <Header
        title="Paramétrage du plan comptable"
        subtitle="Choisissez le référentiel comptable adapté à votre institution"
      />
      <div className="flex-1 p-6 max-w-4xl space-y-6">

        {/* Comptes existants */}
        {existingCount !== null && existingCount > 0 && (
          <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-500 mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-sm font-semibold text-amber-800">
                {existingCount} compte(s) déjà présent(s) dans la base
              </p>
              <p className="text-xs text-amber-700 mt-0.5">
                Le chargement d'un template est idempotent — seuls les comptes manquants seront ajoutés.
                Vos comptes existants ne seront pas modifiés ni supprimés.
              </p>
            </div>
          </div>
        )}

        {/* Résultat du chargement */}
        {result && (
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-5">
            <div className="flex items-center gap-2 mb-3">
              <CheckCircle2 className="w-5 h-5 text-emerald-600" />
              <p className="font-semibold text-emerald-800">Plan chargé avec succès</p>
            </div>
            <div className="grid grid-cols-3 gap-4 text-center">
              <div className="bg-white rounded-lg p-3 border border-emerald-100">
                <p className="text-2xl font-bold text-emerald-700">{result.accounts_created}</p>
                <p className="text-xs text-slate-500 mt-1">Comptes créés</p>
              </div>
              <div className="bg-white rounded-lg p-3 border border-emerald-100">
                <p className="text-2xl font-bold text-slate-400">{result.accounts_skipped}</p>
                <p className="text-xs text-slate-500 mt-1">Déjà existants</p>
              </div>
              <div className="bg-white rounded-lg p-3 border border-emerald-100">
                <p className="text-2xl font-bold text-brand-600">{result.journals_created}</p>
                <p className="text-xs text-slate-500 mt-1">Journaux créés</p>
              </div>
            </div>
            <div className="mt-4 flex gap-3">
              <Link href="/accounts" className="btn-primary text-sm">
                Voir le plan de comptes <ChevronRight className="w-4 h-4" />
              </Link>
              <button onClick={() => setResult(null)} className="btn-secondary text-sm">
                Charger un autre template
              </button>
            </div>
          </div>
        )}

        {error && <ErrorBox message={error} />}
        {loading && <PageLoader />}

        {!loading && !error && !result && !importResult && (
          <>
            <p className="text-slate-600 text-sm">
              Sélectionnez le type de plan adapté à votre institution. Le chargement est <strong>cumulatif</strong> —
              vous pouvez charger plusieurs templates et compléter manuellement ensuite.
            </p>

            {/* Grille templates */}
            <div className="grid grid-cols-1 gap-4">
              {templates.map(t => {
                const Icon = TARGET_ICON[t.target] ?? Wrench;
                const isSelected = selected === t.id;
                return (
                  <button
                    key={t.id}
                    onClick={() => { setSelected(isSelected ? null : t.id); setConfirming(false); }}
                    className={`
                      w-full text-left rounded-xl border-2 p-5 transition-all duration-150
                      ${isSelected
                        ? "border-brand-500 bg-brand-50 shadow-md shadow-brand-100"
                        : `${TARGET_COLOR[t.target]} hover:border-slate-300 hover:shadow-sm`}
                    `}
                  >
                    <div className="flex items-start gap-4">
                      <div className={`w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0 ${
                        isSelected ? "bg-brand-600" : "bg-white border border-slate-200"
                      }`}>
                        <Icon className={`w-6 h-6 ${isSelected ? "text-white" : "text-slate-600"}`} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <h3 className="font-semibold text-slate-900">{t.name}</h3>
                          <span className={TARGET_BADGE[t.target]}>{TARGET_LABEL[t.target]}</span>
                          {isSelected && <span className="badge-blue">Sélectionné</span>}
                        </div>
                        <p className="text-sm text-slate-600 mt-1.5 leading-relaxed">{t.description}</p>
                        <div className="flex items-center gap-4 mt-3">
                          <span className="text-xs text-slate-500 flex items-center gap-1">
                            <span className="font-semibold text-slate-700">{t.account_count}</span> comptes
                          </span>
                          <span className="text-xs text-slate-500 flex items-center gap-1">
                            <span className="font-semibold text-slate-700">{t.journal_count}</span> journaux
                          </span>
                        </div>
                      </div>
                      <div className={`w-5 h-5 rounded-full border-2 flex-shrink-0 mt-1 transition-colors ${
                        isSelected ? "border-brand-600 bg-brand-600" : "border-slate-300"
                      }`}>
                        {isSelected && <CheckCircle2 className="w-full h-full text-white" />}
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>

            {/* Panel import personnalisé */}
            {selected && templates.find(t => t.id === selected)?.target === "CUSTOM" && (
              <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
                <div className="flex items-center gap-2">
                  <Wrench className="w-4 h-4 text-slate-500" />
                  <p className="font-semibold text-slate-800 text-sm">Import de plan personnalisé</p>
                </div>

                {/* Docs champs */}
                <div className="rounded-lg border border-slate-100 bg-slate-50 p-4 text-xs space-y-2">
                  <p className="font-semibold text-slate-700">Colonnes <span className="text-red-500">obligatoires</span> :</p>
                  <ul className="list-disc list-inside text-slate-600 space-y-1">
                    <li><code className="font-mono bg-white px-1 rounded">code</code> — code du compte (ex : 101000)</li>
                    <li><code className="font-mono bg-white px-1 rounded">name</code> — libellé</li>
                    <li><code className="font-mono bg-white px-1 rounded">account_class</code> — <span className="font-medium">CAPITAL, IMMOBILISE, STOCK, TIERS, TRESORERIE, CHARGES, PRODUITS, SPECIAUX, ANALYTIQUE</span> (ou chiffres 1–9)</li>
                    <li><code className="font-mono bg-white px-1 rounded">account_type</code> — <span className="font-medium">ACTIF, PASSIF, CHARGE, PRODUIT</span></li>
                    <li><code className="font-mono bg-white px-1 rounded">account_nature</code> — <span className="font-medium">DEBITEUR, CREDITEUR</span></li>
                  </ul>
                  <p className="font-semibold text-slate-700 pt-1">Colonnes optionnelles :</p>
                  <ul className="list-disc list-inside text-slate-600 space-y-1">
                    <li><code className="font-mono bg-white px-1 rounded">parent_code</code> — code du compte parent</li>
                    <li><code className="font-mono bg-white px-1 rounded">allow_manual_entry</code> — true / false</li>
                    <li><code className="font-mono bg-white px-1 rounded">description</code> — texte libre</li>
                  </ul>
                  <p className="text-slate-500 pt-1">Formats acceptés : <strong>.csv</strong> (séparateur , ou ;) et <strong>.pdf</strong> (tableau avec colonnes nommées).</p>
                </div>

                {/* Télécharger le modèle */}
                <button
                  onClick={() => downloadImportTemplate().catch(e => setImportError(e.message))}
                  className="btn-secondary text-xs flex items-center gap-2"
                >
                  <FileText className="w-4 h-4" />
                  Télécharger le modèle CSV
                </button>

                {/* Zone de dépôt fichier */}
                <div
                  onClick={() => fileInputRef.current?.click()}
                  onDragOver={e => e.preventDefault()}
                  onDrop={e => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) setImportFile(f); }}
                  className="border-2 border-dashed border-slate-300 rounded-xl p-6 text-center cursor-pointer hover:border-brand-400 hover:bg-brand-50 transition-colors"
                >
                  <Upload className="w-8 h-8 text-slate-400 mx-auto mb-2" />
                  {importFile ? (
                    <p className="text-sm font-medium text-brand-700">{importFile.name}</p>
                  ) : (
                    <p className="text-sm text-slate-500">Glisser-déposer ou cliquer pour choisir un fichier <strong>.csv</strong> ou <strong>.pdf</strong></p>
                  )}
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".csv,.pdf"
                    className="hidden"
                    onChange={e => setImportFile(e.target.files?.[0] ?? null)}
                  />
                </div>

                {importError && <p className="text-sm text-red-600">{importError}</p>}

                <div className="flex gap-3">
                  <button
                    onClick={handleImport}
                    disabled={!importFile || importing}
                    className="btn-primary text-sm disabled:opacity-50"
                  >
                    {importing ? "Import en cours..." : "Importer"}
                  </button>
                  <button onClick={() => { setSelected(null); setImportFile(null); setImportError(""); }} className="btn-secondary text-sm">
                    Annuler
                  </button>
                </div>
              </div>
            )}

            {/* Bouton charger (templates non-CUSTOM) */}
            {selected && templates.find(t => t.id === selected)?.target !== "CUSTOM" && !confirming && (
              <div className="flex items-center gap-3 pt-2">
                <button onClick={() => setConfirming(true)} className="btn-primary">
                  Charger ce plan
                </button>
                <button onClick={() => setSelected(null)} className="btn-secondary">Annuler</button>
              </div>
            )}

            {/* Confirmation */}
            {confirming && (
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-5 space-y-3">
                <p className="text-sm font-semibold text-slate-800">Confirmer le chargement</p>
                <p className="text-sm text-slate-600">
                  Le template <strong>{templates.find(t => t.id === selected)?.name}</strong> va être chargé.
                  Les comptes et journaux déjà présents seront ignorés.
                </p>
                {loadError && <p className="text-sm text-red-600">{loadError}</p>}
                <div className="flex gap-3">
                  <button onClick={handleLoad} disabled={loading2} className="btn-primary">
                    {loading2 ? "Chargement en cours..." : "Confirmer"}
                  </button>
                  <button onClick={() => setConfirming(false)} className="btn-secondary">Annuler</button>
                </div>
              </div>
            )}
          </>
        )}

        {/* Résultat import personnalisé */}
        {importResult && (
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-5 space-y-4">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 text-emerald-600" />
              <p className="font-semibold text-emerald-800">Import terminé</p>
            </div>
            <div className="grid grid-cols-2 gap-4 text-center">
              <div className="bg-white rounded-lg p-3 border border-emerald-100">
                <p className="text-2xl font-bold text-emerald-700">{importResult.accounts_created}</p>
                <p className="text-xs text-slate-500 mt-1">Comptes créés</p>
              </div>
              <div className="bg-white rounded-lg p-3 border border-emerald-100">
                <p className="text-2xl font-bold text-slate-400">{importResult.accounts_skipped}</p>
                <p className="text-xs text-slate-500 mt-1">Déjà existants</p>
              </div>
            </div>
            {importResult.errors.length > 0 && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
                <p className="text-xs font-semibold text-amber-800 mb-1">{importResult.errors.length} avertissement(s)</p>
                <ul className="text-xs text-amber-700 space-y-0.5 list-disc list-inside">
                  {importResult.errors.map((e, i) => <li key={i}>{e}</li>)}
                </ul>
              </div>
            )}
            <div className="flex gap-3">
              <Link href="/accounts" className="btn-primary text-sm">
                Voir le plan de comptes <ChevronRight className="w-4 h-4" />
              </Link>
              <button onClick={() => { setImportResult(null); setSelected(null); }} className="btn-secondary text-sm">
                Importer un autre fichier
              </button>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
