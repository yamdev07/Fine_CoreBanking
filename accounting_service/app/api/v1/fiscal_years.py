"""
Router — Exercices fiscaux et périodes comptables.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import AnyAuthenticated, WriteAccess
from app.core.exceptions import FiscalYearClosedError, FiscalYearNotFoundError
from app.db.session import get_session
from app.schemas.accounting import (
    FiscalYearCreate, FiscalYearResponse, PeriodResponse,
)
from app.services.accounting import FiscalYearService

router = APIRouter(prefix="/fiscal-years", tags=["Exercices fiscaux"])


def _svc(session: AsyncSession = Depends(get_session)) -> FiscalYearService:
    return FiscalYearService(session)


@router.get("/", response_model=list[FiscalYearResponse])
async def list_fiscal_years(
    _: AnyAuthenticated,
    svc: FiscalYearService = Depends(_svc),
):
    """Liste tous les exercices fiscaux."""
    return await svc.list_all()


@router.post("/", response_model=FiscalYearResponse, status_code=status.HTTP_201_CREATED)
async def create_fiscal_year(
    body: FiscalYearCreate,
    principal: WriteAccess,
    svc: FiscalYearService = Depends(_svc),
):
    """Crée un exercice fiscal et génère automatiquement ses 12 périodes mensuelles."""
    return await svc.create(body)


@router.get("/{fiscal_year_id}", response_model=FiscalYearResponse)
async def get_fiscal_year(
    fiscal_year_id: str,
    _: AnyAuthenticated,
    svc: FiscalYearService = Depends(_svc),
):
    try:
        return await svc.repo.get_by_id(fiscal_year_id)
    except FiscalYearNotFoundError as e:
        raise HTTPException(status_code=404, detail={"error_code": "FISCAL_YEAR_NOT_FOUND", "message": str(e)})


@router.get("/{fiscal_year_id}/periods", response_model=list[PeriodResponse])
async def list_periods(
    fiscal_year_id: str,
    _: AnyAuthenticated,
    svc: FiscalYearService = Depends(_svc),
):
    """Liste les périodes mensuelles d'un exercice fiscal."""
    try:
        await svc.repo.get_by_id(fiscal_year_id)
    except FiscalYearNotFoundError as e:
        raise HTTPException(status_code=404, detail={"error_code": "FISCAL_YEAR_NOT_FOUND", "message": str(e)})
    return await svc.period_repo.list_by_fiscal_year(fiscal_year_id)


@router.post("/{fiscal_year_id}/close", response_model=FiscalYearResponse)
async def close_fiscal_year(
    fiscal_year_id: str,
    principal: WriteAccess,
    svc: FiscalYearService = Depends(_svc),
):
    """Clôture définitivement un exercice fiscal (irréversible)."""
    try:
        return await svc.close(fiscal_year_id, closed_by=principal.sub)
    except FiscalYearClosedError as e:
        raise HTTPException(status_code=409, detail={"error_code": "FISCAL_YEAR_ALREADY_CLOSED", "message": str(e)})
    except FiscalYearNotFoundError as e:
        raise HTTPException(status_code=404, detail={"error_code": "FISCAL_YEAR_NOT_FOUND", "message": str(e)})
