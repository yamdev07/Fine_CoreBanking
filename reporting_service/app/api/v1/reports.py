"""
Router — Tous les rapports financiers.
Endpoints en lecture seule, avec cache Redis et export PDF/Excel.
"""
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import get_current_principal
from app.db.session import get_session
from app.schemas.reports import (
    BilanReport, BceaoReport, CompteDeResultatReport,
    CreditPortfolioReport, DashboardReport, DepositReport,
    ExportFormat, FluxTresorerieReport,
    GeneralLedgerReport, JournalCentralisateurReport, TrialBalanceReport,
)
from app.services.reporting import ReportingService
from app.utils.cache import get_cached, make_cache_key, set_cached

router = APIRouter(
    prefix="/reports",
    tags=["Rapports financiers"],
    dependencies=[Depends(get_current_principal)],
)


def get_service(session: AsyncSession = Depends(get_session)) -> ReportingService:
    return ReportingService(session)


# ─── 1. Balance générale ──────────────────────────────────────────────────────

@router.get(
    "/trial-balance",
    response_model=TrialBalanceReport,
    summary="Balance générale des comptes",
    description="""
Présente pour chaque compte les soldes d'ouverture, les mouvements de la période
et les soldes de clôture (débiteur / créditeur).
L'équilibre total_débit = total_crédit valide la partie double.
""",
)
async def trial_balance(
    start_date: date = Query(..., description="Date de début"),
    end_date: date = Query(..., description="Date de fin"),
    format: ExportFormat = Query(ExportFormat.JSON),
    svc: ReportingService = Depends(get_service),
):
    cache_key = make_cache_key("trial_balance", {
        "start": str(start_date), "end": str(end_date)
    })
    cached = await get_cached(cache_key)

    if cached and format == ExportFormat.JSON:
        return cached

    report = await svc.trial_balance(start_date, end_date)
    report_dict = report.model_dump()
    await set_cached(cache_key, report_dict)

    if format == ExportFormat.EXCEL:
        from app.utils.exporters import export_trial_balance_excel
        content = export_trial_balance_excel(report_dict)
        filename = f"balance_{start_date}_{end_date}.xlsx"
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    if format == ExportFormat.PDF:
        from app.utils.exporters import export_generic_pdf
        content = export_generic_pdf(report_dict, "Balance Générale")
        filename = f"balance_{start_date}_{end_date}.pdf"
        return Response(
            content=content,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return report


# ─── 2. Grand livre ───────────────────────────────────────────────────────────

@router.get(
    "/general-ledger",
    response_model=GeneralLedgerReport,
    summary="Grand livre d'un compte",
    description="""
Liste tous les mouvements d'un compte sur la période avec le solde progressif.
Identifiez le compte par `account_code` (ex: `571100`) ou `account_id`.
""",
)
async def general_ledger(
    start_date: date = Query(...),
    end_date: date = Query(...),
    account_code: str | None = Query(None, description="Code du compte (ex: 571100)"),
    account_id: str | None = Query(None, description="UUID du compte"),
    page: int = Query(1, ge=1),
    size: int = Query(500, ge=1, le=1000),
    svc: ReportingService = Depends(get_service),
):
    if not account_code and not account_id:
        raise HTTPException(status_code=422, detail="Fournir account_code ou account_id.")
    return await svc.general_ledger(
        account_id=account_id,
        account_code=account_code,
        start_date=start_date,
        end_date=end_date,
        page=page,
        size=size,
    )


# ─── 3. Bilan comptable ───────────────────────────────────────────────────────

@router.get(
    "/balance-sheet",
    response_model=BilanReport,
    summary="Bilan comptable (Actif / Passif)",
    description="""
Bilan à une date d'arrêté avec comparaison N-1.
Présente l'actif immobilisé, l'actif circulant, la trésorerie,
les capitaux propres, et les dettes.
""",
)
async def balance_sheet(
    as_of_date: date = Query(..., description="Date d'arrêté du bilan"),
    format: ExportFormat = Query(ExportFormat.JSON),
    svc: ReportingService = Depends(get_service),
):
    cache_key = make_cache_key("bilan", {"date": str(as_of_date)})
    cached = await get_cached(cache_key)
    if cached and format == ExportFormat.JSON:
        return cached

    report = await svc.bilan(as_of_date)
    report_dict = report.model_dump()
    await set_cached(cache_key, report_dict, ttl=settings.CACHE_TTL_ANNUAL_REPORT)

    if format == ExportFormat.PDF:
        from app.utils.exporters import export_generic_pdf
        content = export_generic_pdf(report_dict, "Bilan Comptable")
        return Response(
            content=content, media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="bilan_{as_of_date}.pdf"'},
        )

    return report


# ─── 4. Compte de résultat ────────────────────────────────────────────────────

@router.get(
    "/income-statement",
    response_model=CompteDeResultatReport,
    summary="Compte de résultat",
    description="""
Produits et charges de la période avec résultats intermédiaires :
Produit Net Bancaire (PNB), Résultat Brut d'Exploitation (RBE), Résultat Net.
Comparaison avec l'exercice précédent.
""",
)
async def income_statement(
    start_date: date = Query(...),
    end_date: date = Query(...),
    format: ExportFormat = Query(ExportFormat.JSON),
    svc: ReportingService = Depends(get_service),
):
    cache_key = make_cache_key("resultat", {
        "start": str(start_date), "end": str(end_date)
    })
    cached = await get_cached(cache_key)
    if cached and format == ExportFormat.JSON:
        return cached

    report = await svc.compte_de_resultat(start_date, end_date)
    report_dict = report.model_dump()
    await set_cached(cache_key, report_dict)

    if format == ExportFormat.PDF:
        from app.utils.exporters import export_generic_pdf
        content = export_generic_pdf(report_dict, "Compte de Résultat")
        filename = f"resultat_{start_date}_{end_date}.pdf"
        return Response(content=content, media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'})

    return report


# ─── 5. Flux de trésorerie ────────────────────────────────────────────────────

@router.get(
    "/cash-flow",
    response_model=FluxTresorerieReport,
    summary="Tableau de flux de trésorerie",
    description="""
Flux de trésorerie classés en trois catégories :
exploitation (crédits, dépôts, intérêts),
investissement (immobilisations),
financement (capitaux propres).
""",
)
async def cash_flow(
    start_date: date = Query(...),
    end_date: date = Query(...),
    svc: ReportingService = Depends(get_service),
):
    return await svc.flux_tresorerie(start_date, end_date)


# ─── 6. Portefeuille crédits ──────────────────────────────────────────────────

@router.get(
    "/credit-portfolio",
    response_model=CreditPortfolioReport,
    summary="État du portefeuille de crédits",
    description="""
Encours de crédits par catégorie (court, moyen, long terme),
créances en souffrance, taux d'impayés, provisions et déficit de provisionnement.
""",
)
async def credit_portfolio(
    as_of_date: date = Query(...),
    format: ExportFormat = Query(ExportFormat.JSON),
    svc: ReportingService = Depends(get_service),
):
    cache_key = make_cache_key("credit_portfolio", {"date": str(as_of_date)})
    cached = await get_cached(cache_key)
    if cached and format == ExportFormat.JSON:
        return cached

    report = await svc.credit_portfolio(as_of_date)
    await set_cached(cache_key, report.model_dump())
    return report


# ─── 7. État des dépôts ───────────────────────────────────────────────────────

@router.get(
    "/deposits",
    response_model=DepositReport,
    summary="État des dépôts (épargne collectée)",
    description="""
Encours de dépôts par type (vue, terme, plans d'épargne),
coût des ressources, taux moyen de rémunération et ratio crédits/dépôts.
""",
)
async def deposits(
    as_of_date: date = Query(...),
    start_date: date = Query(..., description="Début pour le calcul des intérêts"),
    end_date: date = Query(..., description="Fin pour le calcul des intérêts"),
    svc: ReportingService = Depends(get_service),
):
    return await svc.deposits(as_of_date, start_date, end_date)


# ─── 8. Tableau de bord exécutif ─────────────────────────────────────────────

@router.get(
    "/dashboard",
    response_model=DashboardReport,
    summary="Tableau de bord exécutif (KPIs)",
    description="""
Vue synthétique pour la direction :
encours crédits/épargne, trésorerie, PNB, taux d'impayés,
résultat net, ROE, ROA, ratios de liquidité.
""",
)
async def dashboard(
    as_of_date: date = Query(...),
    format: ExportFormat = Query(ExportFormat.JSON),
    svc: ReportingService = Depends(get_service),
):
    cache_key = make_cache_key("dashboard", {"date": str(as_of_date)})
    cached = await get_cached(cache_key)
    if cached and format == ExportFormat.JSON:
        return cached

    report = await svc.dashboard(as_of_date)
    report_dict = report.model_dump()
    await set_cached(cache_key, report_dict, ttl=60)  # Cache 1 minute seulement

    if format == ExportFormat.EXCEL:
        from app.utils.exporters import export_dashboard_excel
        content = export_dashboard_excel(report_dict)
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="dashboard_{as_of_date}.xlsx"'},
        )

    return report


# ─── 9. Rapport BCEAO ────────────────────────────────────────────────────────

@router.get(
    "/bceao-prudential",
    response_model=BceaoReport,
    summary="États prudentiels BCEAO/UEMOA",
    description="""
Calcule les 5 ratios prudentiels réglementaires BCEAO :
- R1 : Solvabilité (>= 8%)
- R2 : Liquidité (>= 75%)
- R3 : Transformation (<= 100%)
- R4 : Division des risques (<= 75%)
- R5 : Couverture des risques (>= 10%)

Indique la conformité de chaque ratio et génère les observations réglementaires.
""",
)
async def bceao_prudential(
    as_of_date: date = Query(..., description="Date d'arrêté"),
    numero_agrement: str = Query(..., description="Numéro d'agrément BCEAO"),
    format: ExportFormat = Query(ExportFormat.JSON),
    svc: ReportingService = Depends(get_service),
):
    cache_key = make_cache_key("bceao", {
        "date": str(as_of_date), "agr": numero_agrement
    })
    cached = await get_cached(cache_key)
    if cached and format == ExportFormat.JSON:
        return cached

    report = await svc.bceao_report(as_of_date, numero_agrement)
    report_dict = report.model_dump()
    await set_cached(cache_key, report_dict, ttl=settings.CACHE_TTL_ANNUAL_REPORT)

    if format == ExportFormat.PDF:
        from app.utils.exporters import export_bceao_pdf
        content = export_bceao_pdf(report_dict)
        filename = f"bceao_prudential_{as_of_date}.pdf"
        return Response(
            content=content, media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return report


# ─── 10. Journal centralisateur ───────────────────────────────────────────────

@router.get(
    "/journal-centralizer",
    response_model=JournalCentralisateurReport,
    summary="Journal centralisateur",
    description="""
Récapitulatif de tous les journaux sur la période :
nombre d'écritures, totaux débit/crédit, équilibre.
Permet de vérifier la cohérence globale avant clôture.
""",
)
async def journal_centralizer(
    start_date: date = Query(...),
    end_date: date = Query(...),
    format: ExportFormat = Query(ExportFormat.JSON),
    svc: ReportingService = Depends(get_service),
):
    report = await svc.journal_centralizer(start_date, end_date)

    if format == ExportFormat.EXCEL:
        from app.utils.exporters import export_journal_centralizer_excel
        content = export_journal_centralizer_excel(report.model_dump())
        filename = f"journal_centralizer_{start_date}_{end_date}.xlsx"
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return report


# ─── Exercices fiscaux (référence) ───────────────────────────────────────────

@router.get(
    "/fiscal-years",
    summary="Liste des exercices fiscaux",
)
async def fiscal_years(svc: ReportingService = Depends(get_service)):
    return await svc.repo.get_fiscal_years()
