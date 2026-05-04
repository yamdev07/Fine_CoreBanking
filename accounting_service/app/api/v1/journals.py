"""
Router — Journaux et Écritures comptables
"""
import math
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounting import EntryStatus

from app.core.exceptions import (
    AccountNotActiveError, AccountNotFoundError,
    JournalEntryAlreadyPostedError, JournalEntryAlreadyReversedError,
    JournalEntryNotFoundError, PeriodClosedError, PeriodNotFoundError,
    LetteringImbalancedError, LineAlreadyLetteredError,
)
from app.core.security import AnyAuthenticated, ServiceOrWrite, WriteAccess, TokenPayload
from app.db.session import get_session
from app.repositories.accounting import JournalRepository
from app.schemas.accounting import (
    JournalEntryCreate, JournalEntryResponse, JournalResponse,
    LetteringRequest, LetteringResponse, PaginatedResponse,
)
from app.services.accounting import JournalEntryService

# ─── Router pour les Journaux (CJ, BJ, OD…) ─────────────────────────────────
journals_router = APIRouter(prefix="/journals", tags=["Journaux"])


@journals_router.get("/", response_model=list[JournalResponse])
async def list_journals(
    principal: AnyAuthenticated,
    session: AsyncSession = Depends(get_session),
):
    """Liste tous les journaux actifs. Rôles : tous."""
    return await JournalRepository(session).list_all()


# ─── Router pour les Écritures (JournalEntry) ────────────────────────────────
router = APIRouter(prefix="/journal-entries", tags=["Écritures comptables"])


def get_entry_service(session: AsyncSession = Depends(get_session)) -> JournalEntryService:
    return JournalEntryService(session)


@router.post("/", response_model=JournalEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_entry(
    data: JournalEntryCreate,
    principal: ServiceOrWrite,
    svc: JournalEntryService = Depends(get_entry_service),
):
    """
    Crée une écriture comptable en brouillon (DRAFT).

    La règle de la partie double (ΣDébit = ΣCrédit) est vérifiée automatiquement.
    L'identité de l'auteur est extraite du token JWT (champ `sub`).
    Rôles : ADMIN, ACCOUNTANT, SERVICE_CREDIT, SERVICE_SAVINGS, SERVICE_CASH.
    """
    try:
        entry = await svc.create_entry(data, created_by=principal.sub)
        return await svc.entry_repo.get_by_id(entry.id, with_lines=True)
    except (PeriodNotFoundError, AccountNotFoundError, AccountNotActiveError) as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/", response_model=PaginatedResponse[JournalEntryResponse])
async def list_entries(
    principal: AnyAuthenticated,
    period_id: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=500),
    svc: JournalEntryService = Depends(get_entry_service),
):
    """Liste les écritures (filtrables par période et statut). Rôles : tous."""
    try:
        status_enum = EntryStatus(status) if status else None
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Statut invalide: '{status}'. Valeurs acceptées: {[s.value for s in EntryStatus]}",
        )
    items, total = await svc.entry_repo.list_by_period(
        period_id, status=status_enum, offset=(page - 1) * size, limit=size
    )
    return PaginatedResponse(
        items=items, total=total, page=page, size=size,
        pages=math.ceil(total / size) if total > 0 else 0,
    )


@router.get("/{entry_id}", response_model=JournalEntryResponse)
async def get_entry(
    entry_id: str,
    principal: AnyAuthenticated,
    svc: JournalEntryService = Depends(get_entry_service),
):
    """Rôles : tous."""
    try:
        return await svc.entry_repo.get_by_id(entry_id, with_lines=True)
    except JournalEntryNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)


@router.post("/{entry_id}/post", response_model=JournalEntryResponse)
async def post_entry(
    entry_id: str,
    principal: WriteAccess,
    svc: JournalEntryService = Depends(get_entry_service),
):
    """
    Valide une écriture (DRAFT → POSTED).
    Une fois validée, l'écriture est immuable (règle d'intangibilité).
    Rôles : ADMIN, ACCOUNTANT.
    """
    try:
        entry = await svc.post_entry(entry_id, posted_by=principal.sub)
        return await svc.entry_repo.get_by_id(entry.id, with_lines=True)
    except JournalEntryNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
    except (JournalEntryAlreadyPostedError, JournalEntryAlreadyReversedError, PeriodClosedError) as e:
        raise HTTPException(status_code=422, detail=e.message)


@router.post("/{entry_id}/reverse", response_model=JournalEntryResponse)
async def reverse_entry(
    entry_id: str,
    principal: WriteAccess,
    reversal_date: date | None = Query(None, description="Date d'extourne (défaut : aujourd'hui)"),
    svc: JournalEntryService = Depends(get_entry_service),
):
    """
    Extourne une écriture validée (crée l'écriture miroir avec débit/crédit inversés).
    Rôles : ADMIN, ACCOUNTANT.
    """
    try:
        reversal = await svc.reverse_entry(
            entry_id, reversed_by=principal.sub, reversal_date=reversal_date
        )
        return await svc.entry_repo.get_by_id(reversal.id, with_lines=True)
    except JournalEntryNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
    except (JournalEntryAlreadyPostedError, JournalEntryAlreadyReversedError) as e:
        raise HTTPException(status_code=422, detail=e.message)


@router.post("/letter", response_model=LetteringResponse)
async def letter_lines(
    data: LetteringRequest,
    principal: WriteAccess,
    svc: JournalEntryService = Depends(get_entry_service),
):
    """
    Lettrage de lignes comptables.
    Rapproche des mouvements débiteurs et créditeurs sur le même compte.
    Rôles : ADMIN, ACCOUNTANT.
    """
    try:
        return await svc.letter_lines(data.line_ids, principal.sub, data.lettering_code)
    except (LetteringImbalancedError, LineAlreadyLetteredError) as e:
        raise HTTPException(status_code=422, detail=e.message)
