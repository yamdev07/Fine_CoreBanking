"""
Router — Rapports comptables
  - Balance générale
  - Grand livre
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AccountNotFoundError
from app.core.security import AnyAuthenticated
from app.db.session import get_session
from app.schemas.accounting import GeneralLedgerResponse, TrialBalanceResponse
from app.services.accounting import ReportService

router = APIRouter(prefix="/reports", tags=["Rapports comptables"])


def get_report_service(session: AsyncSession = Depends(get_session)) -> ReportService:
    return ReportService(session)


@router.get("/trial-balance", response_model=TrialBalanceResponse)
async def trial_balance(
    principal: AnyAuthenticated,
    start_date: date = Query(..., description="Date de début de la période"),
    end_date: date = Query(..., description="Date de fin de la période"),
    svc: ReportService = Depends(get_report_service),
):
    """
    Balance générale des comptes.

    Présente pour chaque compte :
    - Solde d'ouverture
    - Mouvements de la période (débit / crédit)
    - Solde de clôture

    L'équilibre total_débit = total_crédit valide la partie double.
    Rôles : tous.
    """
    if end_date < start_date:
        raise HTTPException(status_code=422, detail="La date de fin doit être >= date de début.")
    return await svc.trial_balance(start_date, end_date)


@router.get("/general-ledger/{account_id}", response_model=GeneralLedgerResponse)
async def general_ledger(
    account_id: str,
    principal: AnyAuthenticated,
    start_date: date = Query(...),
    end_date: date = Query(...),
    svc: ReportService = Depends(get_report_service),
):
    """
    Grand livre d'un compte.

    Liste toutes les écritures passées sur le compte sur la période,
    avec le solde progressif après chaque mouvement.
    Rôles : tous.
    """
    try:
        return await svc.general_ledger(account_id, start_date, end_date)
    except AccountNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
