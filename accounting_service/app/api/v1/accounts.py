"""
Router — Plan de comptes
"""
import math
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AccountAlreadyExistsError, AccountHasChildrenError,
    AccountNotFoundError,
)
from app.core.security import AdminOnly, AnyAuthenticated, WriteAccess, TokenPayload
from app.db.session import get_session
from app.repositories.accounting import AccountRepository
from app.schemas.accounting import (
    AccountBalanceResponse, AccountCreate, AccountResponse, AccountUpdate,
    PaginatedResponse,
)
from app.services.accounting import AccountService

router = APIRouter(prefix="/accounts", tags=["Plan de comptes"])


def get_account_service(session: AsyncSession = Depends(get_session)) -> AccountService:
    return AccountService(session)


@router.post("/", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    data: AccountCreate,
    principal: WriteAccess,
    svc: AccountService = Depends(get_account_service),
):
    """Crée un nouveau compte dans le plan de comptes. Rôles : ADMIN, ACCOUNTANT."""
    try:
        return await svc.create(data)
    except AccountAlreadyExistsError as e:
        raise HTTPException(status_code=409, detail=e.message)
    except AccountNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)


@router.get("/", response_model=PaginatedResponse[AccountResponse])
async def list_accounts(
    principal: AnyAuthenticated,
    account_class: str | None = Query(None, description="Filtre par classe (1-9)"),
    is_active: bool | None = Query(None),
    is_leaf: bool | None = Query(None),
    search: str | None = Query(None, description="Recherche par code ou libellé"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=500),
    svc: AccountService = Depends(get_account_service),
):
    """Liste les comptes avec filtres et pagination. Rôles : tous."""
    items, total = await svc.list(
        account_class=account_class,
        is_active=is_active,
        is_leaf=is_leaf,
        search=search,
        offset=(page - 1) * size,
        limit=size,
    )
    return PaginatedResponse(
        items=items, total=total, page=page, size=size,
        pages=math.ceil(total / size) if total > 0 else 0,
    )


@router.get("/{account_id}", response_model=AccountResponse)
async def get_account(
    account_id: str,
    principal: AnyAuthenticated,
    svc: AccountService = Depends(get_account_service),
):
    """Rôles : tous."""
    try:
        return await svc.repo.get_by_id(account_id)
    except AccountNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)


@router.patch("/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: str,
    data: AccountUpdate,
    principal: WriteAccess,
    svc: AccountService = Depends(get_account_service),
):
    """Modifie un compte. Rôles : ADMIN, ACCOUNTANT."""
    try:
        return await svc.update(account_id, data)
    except AccountNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_account(
    account_id: str,
    principal: AdminOnly,
    svc: AccountService = Depends(get_account_service),
):
    """Désactive un compte. Rôle : ADMIN uniquement."""
    try:
        await svc.deactivate(account_id)
    except (AccountNotFoundError, AccountHasChildrenError) as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/{account_id}/balance", response_model=AccountBalanceResponse)
async def get_account_balance(
    account_id: str,
    principal: AnyAuthenticated,
    start_date: date = Query(...),
    end_date: date = Query(...),
    svc: AccountService = Depends(get_account_service),
):
    """Retourne le solde d'un compte sur une période. Rôles : tous."""
    try:
        return await svc.get_balance(account_id, start_date, end_date)
    except AccountNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
