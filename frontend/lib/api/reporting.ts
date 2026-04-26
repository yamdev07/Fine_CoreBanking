import { getToken } from "@/lib/auth";

const BASE = process.env.NEXT_PUBLIC_REPORTING_URL ?? "http://localhost:8001";

async function req<T>(path: string): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = token
    ? { Authorization: `Bearer ${token}` }
    : {};
  const res = await fetch(`${BASE}${path}`, { headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ message: res.statusText }));
    const msg = err?.detail?.message ?? err?.message ?? res.statusText;
    throw new Error(msg);
  }
  return res.json();
}

export function exportUrl(path: string, format: "pdf" | "excel"): string {
  const token = getToken();
  const sep = path.includes("?") ? "&" : "?";
  const tokenParam = token ? `&_token=${encodeURIComponent(token)}` : "";
  return `${BASE}${path}${sep}format=${format}${tokenParam}`;
}

// ── Types ──────────────────────────────────────────────────────────────────────

export interface ReportHeader {
  institution_name: string;
  report_title: string;
  period_start: string;
  period_end: string;
  currency: string;
  generated_at: string;
}

export interface KPIValue {
  label: string;
  value: number;
  unit: string;
  previous_value: number | null;
  variation_pct: number | null;
  trend: "UP" | "DOWN" | "STABLE" | null;
}

export interface DashboardReport {
  header: ReportHeader;
  as_of_date: string;
  kpi_encours_credits: KPIValue;
  kpi_encours_epargne: KPIValue;
  kpi_tresorerie: KPIValue;
  kpi_produit_net_bancaire: KPIValue;
  kpi_taux_impayes: KPIValue;
  kpi_taux_couverture: KPIValue;
  kpi_resultat_net: KPIValue;
  kpi_roe: KPIValue;
  kpi_roa: KPIValue;
  kpi_ratio_liquidite: KPIValue;
  kpi_ratio_credits_depots: KPIValue;
}

export interface TrialBalanceLine {
  account_code: string;
  account_name: string;
  account_class: string;
  account_type: string;
  account_nature: string;
  opening_debit: number;
  opening_credit: number;
  period_debit: number;
  period_credit: number;
  cumulative_debit: number;
  cumulative_credit: number;
  closing_debit: number;
  closing_credit: number;
}

export interface TrialBalanceReport {
  header: ReportHeader;
  lines: TrialBalanceLine[];
  total_opening_debit: number;
  total_opening_credit: number;
  total_period_debit: number;
  total_period_credit: number;
  total_closing_debit: number;
  total_closing_credit: number;
  is_balanced: boolean;
  account_count: number;
}

export interface BilanSection {
  label: string;
  lines: { account_code: string; account_name: string; current_year: number; previous_year: number; variation: number; variation_pct: number | null }[];
  subtotal_current: number;
  subtotal_previous: number;
}

export interface BilanReport {
  header: ReportHeader;
  actif_immobilise: BilanSection;
  actif_circulant: BilanSection;
  tresorerie_actif: BilanSection;
  total_actif: number;
  total_actif_previous: number;
  capitaux_propres: BilanSection;
  dettes_financieres: BilanSection;
  dettes_exploitation: BilanSection;
  tresorerie_passif: BilanSection;
  total_passif: number;
  total_passif_previous: number;
  is_balanced: boolean;
  current_year: number;
  reference_year: number;
}

export interface ResultatSection {
  label: string;
  lines: { account_code: string; account_name: string; current_year: number; previous_year: number; variation: number; variation_pct: number | null }[];
  subtotal_current: number;
  subtotal_previous: number;
}

export interface CompteDeResultatReport {
  header: ReportHeader;
  produits_financiers: ResultatSection;
  produits_accessoires: ResultatSection;
  reprises_provisions: ResultatSection;
  total_produits: number;
  total_produits_previous: number;
  charges_financieres: ResultatSection;
  charges_exploitation: ResultatSection;
  dotations_provisions: ResultatSection;
  total_charges: number;
  total_charges_previous: number;
  produit_net_bancaire: number;
  resultat_brut_exploitation: number;
  resultat_net: number;
  resultat_net_previous: number;
  variation_resultat_pct: number | null;
}

export interface BceaoRatioLine {
  code_ratio: string;
  libelle: string;
  numerateur: number;
  denominateur: number;
  valeur: number;
  norme: string;
  conforme: boolean;
}

export interface BceaoReport {
  header: ReportHeader;
  institution_agree: string;
  date_arrete: string;
  fonds_propres_nets: number;
  ratio_solvabilite: BceaoRatioLine;
  ratio_liquidite: BceaoRatioLine;
  ratio_transformation: BceaoRatioLine;
  ratio_division_risques: BceaoRatioLine;
  ratio_couverture_risques: BceaoRatioLine;
  total_ratios: number;
  ratios_conformes: number;
  ratios_non_conformes: number;
  observations: string | null;
}

export interface CreditPortfolioLine {
  account_code: string;
  account_name: string;
  encours: number;
  encours_previous: number;
  variation: number;
  pct_portefeuille: number;
}

export interface CreditPortfolioReport {
  header: ReportHeader;
  credits_court_terme: CreditPortfolioLine;
  credits_moyen_terme: CreditPortfolioLine;
  credits_long_terme: CreditPortfolioLine;
  creances_souffrance: CreditPortfolioLine;
  creances_irrecouvrable: CreditPortfolioLine;
  total_portefeuille: number;
  total_portefeuille_previous: number;
  taux_impayés: number;
  taux_creances_douteuses: number;
  taux_couverture_provisions: number;
  provisions_constituees: number;
  provisions_requises: number;
  deficit_provisionnement: number;
}

export interface JournalCentralisateurLine {
  journal_code: string;
  journal_name: string;
  nb_ecritures: number;
  total_debit: number;
  total_credit: number;
  is_balanced: boolean;
}

export interface JournalCentralisateurReport {
  header: ReportHeader;
  lines: JournalCentralisateurLine[];
  total_ecritures: number;
  grand_total_debit: number;
  grand_total_credit: number;
  is_balanced: boolean;
}

// ── Appels API ─────────────────────────────────────────────────────────────────

export const getDashboard = (date: string) =>
  req<DashboardReport>(`/api/v1/reports/dashboard?as_of_date=${date}`);

export const getTrialBalance = (start: string, end: string) =>
  req<TrialBalanceReport>(`/api/v1/reports/trial-balance?start_date=${start}&end_date=${end}`);

export const getBilan = (date: string) =>
  req<BilanReport>(`/api/v1/reports/balance-sheet?as_of_date=${date}`);

export const getResultat = (start: string, end: string) =>
  req<CompteDeResultatReport>(`/api/v1/reports/income-statement?start_date=${start}&end_date=${end}`);

export const getBceao = (date: string, agrement: string) =>
  req<BceaoReport>(`/api/v1/reports/bceao-prudential?as_of_date=${date}&numero_agrement=${agrement}`);

export const getCreditPortfolio = (date: string) =>
  req<CreditPortfolioReport>(`/api/v1/reports/credit-portfolio?as_of_date=${date}`);

export const getJournalCentralizer = (start: string, end: string) =>
  req<JournalCentralisateurReport>(`/api/v1/reports/journal-centralizer?start_date=${start}&end_date=${end}`);

export const getFiscalYears = () =>
  req<{ id: string; name: string; start_date: string; end_date: string; status: string }[]>(
    "/api/v1/reports/fiscal-years"
  );
