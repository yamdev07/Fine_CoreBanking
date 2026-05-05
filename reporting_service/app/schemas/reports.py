"""
Schémas Pydantic v2 — Tous les rapports du microservice Reporting.

Rapports implémentés :
  1.  Balance générale
  2.  Grand livre
  3.  Bilan comptable (Actif / Passif)
  4.  Compte de résultat
  5.  Tableau de flux de trésorerie (simplifié)
  6.  État des créances (crédits accordés, impayés)
  7.  État des dépôts (épargne collectée)
  8.  Tableau de bord exécutif (KPIs)
  9.  Rapport BCEAO — États financiers prudentiels
  10. Journal centralisateur (par journal, par période)
"""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

# ─── Helpers communs ──────────────────────────────────────────────────────────


class ExportFormat(StrEnum):
    JSON = "json"
    PDF = "pdf"
    EXCEL = "excel"


class ReportHeader(BaseModel):
    institution_name: str
    report_title: str
    period_start: date
    period_end: date
    currency: str = "XOF"
    generated_at: datetime
    generated_by: str = "reporting-service"


# ─── 1. Balance générale ──────────────────────────────────────────────────────


class TrialBalanceLine(BaseModel):
    account_code: str
    account_name: str
    account_class: str
    account_type: str
    account_nature: str
    opening_debit: Decimal = Decimal("0")
    opening_credit: Decimal = Decimal("0")
    period_debit: Decimal = Decimal("0")
    period_credit: Decimal = Decimal("0")
    cumulative_debit: Decimal = Decimal("0")
    cumulative_credit: Decimal = Decimal("0")
    closing_debit: Decimal = Decimal("0")  # Solde débiteur final
    closing_credit: Decimal = Decimal("0")  # Solde créditeur final


class TrialBalanceReport(BaseModel):
    header: ReportHeader
    lines: list[TrialBalanceLine]
    total_opening_debit: Decimal
    total_opening_credit: Decimal
    total_period_debit: Decimal
    total_period_credit: Decimal
    total_closing_debit: Decimal
    total_closing_credit: Decimal
    is_balanced: bool
    account_count: int


# ─── 2. Grand livre ───────────────────────────────────────────────────────────


class LedgerMovement(BaseModel):
    entry_number: str
    entry_date: date
    value_date: date
    journal_code: str
    description: str
    reference: str | None
    third_party_id: str | None
    debit_amount: Decimal
    credit_amount: Decimal
    running_balance: Decimal
    balance_nature: str  # DEBITEUR | CREDITEUR


class GeneralLedgerReport(BaseModel):
    header: ReportHeader
    account_code: str
    account_name: str
    account_class: str
    account_nature: str
    opening_balance: Decimal
    opening_balance_nature: str
    closing_balance: Decimal
    closing_balance_nature: str
    total_debit: Decimal
    total_credit: Decimal
    movement_count: int
    movements: list[LedgerMovement]


# ─── 3. Bilan comptable ───────────────────────────────────────────────────────


class BilanLine(BaseModel):
    account_code: str
    account_name: str
    account_class: str
    current_year: Decimal  # N
    previous_year: Decimal  # N-1
    variation: Decimal
    variation_pct: Decimal | None


class BilanSection(BaseModel):
    label: str
    lines: list[BilanLine]
    subtotal_current: Decimal
    subtotal_previous: Decimal


class BilanReport(BaseModel):
    header: ReportHeader
    # ACTIF
    actif_immobilise: BilanSection
    actif_circulant: BilanSection
    tresorerie_actif: BilanSection
    total_actif: Decimal
    total_actif_previous: Decimal
    # PASSIF
    capitaux_propres: BilanSection
    dettes_financieres: BilanSection
    dettes_exploitation: BilanSection
    tresorerie_passif: BilanSection
    total_passif: Decimal
    total_passif_previous: Decimal
    # Contrôle
    is_balanced: bool  # total_actif == total_passif
    reference_year: int
    current_year: int


# ─── 4. Compte de résultat ────────────────────────────────────────────────────


class ResultatLine(BaseModel):
    account_code: str
    account_name: str
    current_year: Decimal
    previous_year: Decimal
    variation: Decimal
    variation_pct: Decimal | None


class ResultatSection(BaseModel):
    label: str
    lines: list[ResultatLine]
    subtotal_current: Decimal
    subtotal_previous: Decimal


class CompteDeResultatReport(BaseModel):
    header: ReportHeader
    # Produits
    produits_financiers: ResultatSection
    produits_accessoires: ResultatSection
    reprises_provisions: ResultatSection
    total_produits: Decimal
    total_produits_previous: Decimal
    # Charges
    charges_financieres: ResultatSection
    charges_exploitation: ResultatSection
    dotations_provisions: ResultatSection
    total_charges: Decimal
    total_charges_previous: Decimal
    # Résultats intermédiaires
    produit_net_bancaire: Decimal  # PNB = Produits financiers - Charges financières
    resultat_brut_exploitation: Decimal
    resultat_net: Decimal
    resultat_net_previous: Decimal
    variation_resultat_pct: Decimal | None


# ─── 5. Flux de trésorerie (simplifié) ───────────────────────────────────────


class FluxTresorerieReport(BaseModel):
    header: ReportHeader
    # Activités opérationnelles
    flux_exploitation: Decimal
    flux_exploitation_detail: list[dict[str, Any]]
    # Activités d'investissement
    flux_investissement: Decimal
    flux_investissement_detail: list[dict[str, Any]]
    # Activités de financement
    flux_financement: Decimal
    flux_financement_detail: list[dict[str, Any]]
    # Synthèse
    variation_nette_tresorerie: Decimal
    tresorerie_ouverture: Decimal
    tresorerie_cloture: Decimal


# ─── 6. État des créances (portefeuille crédits) ──────────────────────────────


class CreditPortfolioLine(BaseModel):
    account_code: str
    account_name: str
    encours: Decimal  # Solde débiteur = capital restant dû
    encours_previous: Decimal
    variation: Decimal
    pct_portefeuille: Decimal  # Part dans le portefeuille total


class CreditPortfolioReport(BaseModel):
    header: ReportHeader
    # Par catégorie
    credits_court_terme: CreditPortfolioLine
    credits_moyen_terme: CreditPortfolioLine
    credits_long_terme: CreditPortfolioLine
    creances_souffrance: CreditPortfolioLine
    creances_irrecouvrable: CreditPortfolioLine
    total_portefeuille: Decimal
    total_portefeuille_previous: Decimal
    # Indicateurs qualité
    taux_impayés: Decimal  # Créances souffrance / Total portefeuille
    taux_creances_douteuses: Decimal
    taux_couverture_provisions: Decimal
    # Provisions
    provisions_constituees: Decimal
    provisions_requises: Decimal
    deficit_provisionnement: Decimal


# ─── 7. État des dépôts (épargne) ────────────────────────────────────────────


class DepositReport(BaseModel):
    header: ReportHeader
    # Par type de dépôt
    depots_vue: Decimal
    depots_vue_previous: Decimal
    depots_terme: Decimal
    depots_terme_previous: Decimal
    plans_epargne: Decimal
    plans_epargne_previous: Decimal
    total_depots: Decimal
    total_depots_previous: Decimal
    variation_pct: Decimal | None
    # Coût des ressources
    charges_interets_periode: Decimal
    taux_moyen_remuneration: Decimal  # en %
    # Ratio
    ratio_credits_depots: Decimal  # Total crédits / Total dépôts (en %)


# ─── 8. Tableau de bord exécutif (KPIs) ──────────────────────────────────────


class KPIValue(BaseModel):
    label: str
    value: Decimal
    unit: str  # XOF | % | ratio
    previous_value: Decimal | None = None
    variation_pct: Decimal | None = None
    trend: str | None = None  # UP | DOWN | STABLE


class DashboardReport(BaseModel):
    header: ReportHeader
    as_of_date: date
    # Activité
    kpi_encours_credits: KPIValue
    kpi_encours_epargne: KPIValue
    kpi_tresorerie: KPIValue
    kpi_produit_net_bancaire: KPIValue
    # Qualité du portefeuille
    kpi_taux_impayes: KPIValue
    kpi_taux_couverture: KPIValue
    # Rentabilité
    kpi_resultat_net: KPIValue
    kpi_roe: KPIValue  # Return on Equity
    kpi_roa: KPIValue  # Return on Assets
    # Liquidité
    kpi_ratio_liquidite: KPIValue  # Trésorerie / Dépôts à vue
    kpi_ratio_credits_depots: KPIValue


# ─── 9. Rapport BCEAO — États prudentiels ────────────────────────────────────


class BceaoRatioLine(BaseModel):
    code_ratio: str  # ex: "R1", "R2"
    libelle: str
    numerateur: Decimal
    denominateur: Decimal
    valeur: Decimal  # en %
    norme: str  # ex: ">= 8%"
    conforme: bool


class BceaoReport(BaseModel):
    header: ReportHeader
    institution_agree: str  # Numéro d'agrément BCEAO
    date_arrete: date
    # Fonds propres nets
    fonds_propres_nets: Decimal
    # Ratios prudentiels UEMOA
    ratio_solvabilite: BceaoRatioLine  # R1 >= 8%
    ratio_liquidite: BceaoRatioLine  # R2 >= 100%
    ratio_transformation: BceaoRatioLine  # R3
    ratio_division_risques: BceaoRatioLine  # R4 <= 75%
    ratio_couverture_risques: BceaoRatioLine  # R5
    # Synthèse conformité
    total_ratios: int
    ratios_conformes: int
    ratios_non_conformes: int
    observations: str | None


# ─── 10. Journal centralisateur ───────────────────────────────────────────────


class JournalCentralisateurLine(BaseModel):
    journal_code: str
    journal_name: str
    nb_ecritures: int
    total_debit: Decimal
    total_credit: Decimal
    is_balanced: bool


class JournalCentralisateurReport(BaseModel):
    header: ReportHeader
    lines: list[JournalCentralisateurLine]
    total_ecritures: int
    grand_total_debit: Decimal
    grand_total_credit: Decimal
    is_balanced: bool


# ─── Paramètres de requête communs ───────────────────────────────────────────


class DateRangeParams(BaseModel):
    start_date: date
    end_date: date
    fiscal_year_id: str | None = None


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    size: int = Field(default=50, ge=1, le=1000)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size
