"""
Router — Plan de comptes
"""

import csv
import io
import math
import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AccountAlreadyExistsError,
    AccountHasChildrenError,
    AccountNotFoundError,
)
from app.core.security import AdminOnly, AnyAuthenticated, WriteAccess
from app.data.plan_templates import TEMPLATES, AccountDef
from app.db.session import get_session
from app.models.accounting import AccountPlan, Journal, JournalCode
from app.schemas.accounting import (
    AccountBalanceResponse,
    AccountCreate,
    AccountResponse,
    AccountUpdate,
    PaginatedResponse,
)
from app.services.accounting import AccountService

router = APIRouter(prefix="/accounts", tags=["Plan de comptes"])


# ─── Schémas locaux ───────────────────────────────────────────────────────────


class PlanTemplateInfo(BaseModel):
    id: str
    name: str
    description: str
    target: str
    account_count: int
    journal_count: int


class LoadTemplateResult(BaseModel):
    template_id: str
    accounts_created: int
    accounts_skipped: int
    journals_created: int


class CsvImportResult(BaseModel):
    accounts_created: int
    accounts_skipped: int
    errors: list[str]


# ─── Helper : chargement idempotent d'un template ────────────────────────────


async def _load_template_accounts(
    session: AsyncSession,
    accounts_def: list[AccountDef],
    journals_def: list[dict],
) -> tuple[int, int, int]:
    """Charge les comptes et journaux d'un template de façon idempotente.
    Retourne (created, skipped, journals_created).
    """
    code_to_id: dict[str, str] = {}
    created = 0
    skipped = 0

    # Pré-indexer les comptes existants
    existing = (await session.execute(select(AccountPlan))).scalars().all()
    for acc in existing:
        code_to_id[acc.code] = acc.id

    for acc_def in accounts_def:
        if acc_def.code in code_to_id:
            skipped += 1
            continue

        parent_id = code_to_id.get(acc_def.parent_code) if acc_def.parent_code else None
        level = 1
        path = ""

        if parent_id:
            parent = await session.get(AccountPlan, parent_id)
            if parent:
                level = parent.level + 1
                path = f"{parent.path}{parent_id}/"
                if parent.is_leaf:
                    parent.is_leaf = False

        acc = AccountPlan(
            id=str(uuid.uuid4()),
            code=acc_def.code,
            name=acc_def.name,
            account_class=acc_def.account_class,
            account_type=acc_def.account_type,
            account_nature=acc_def.account_nature,
            parent_id=parent_id,
            level=level,
            path=path,
            is_leaf=acc_def.is_leaf,
            allow_manual_entry=acc_def.allow_manual_entry,
            currency="XOF",
        )
        session.add(acc)
        await session.flush()
        code_to_id[acc_def.code] = acc.id
        created += 1

    journals_created = 0
    for j in journals_def:
        exists = (
            await session.execute(select(Journal).where(Journal.code == j["code"]))
        ).scalar_one_or_none()
        if exists:
            continue
        # JournalCode enum: use code as value lookup
        try:
            jtype = JournalCode(j.get("type", j["code"]))
        except ValueError:
            jtype = JournalCode.GJ
        journal = Journal(
            id=str(uuid.uuid4()),
            code=j["code"],
            name=j["name"],
            journal_type=jtype,
            sequence_prefix=j["prefix"] + "-",
        )
        session.add(journal)
        journals_created += 1

    await session.commit()
    return created, skipped, journals_created


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
        items=items,
        total=total,
        page=page,
        size=size,
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


# ─── Templates de plan comptable ──────────────────────────────────────────────


@router.get("/templates/list", response_model=list[PlanTemplateInfo])
async def list_plan_templates(principal: AnyAuthenticated):
    """Liste les templates de plan comptable disponibles. Rôles : tous."""
    return [
        PlanTemplateInfo(
            id=t.id,
            name=t.name,
            description=t.description,
            target=t.target,
            account_count=len(t.accounts),
            journal_count=len(t.journal_codes),
        )
        for t in TEMPLATES.values()
    ]


@router.post("/templates/{template_id}/load", response_model=LoadTemplateResult)
async def load_plan_template(
    template_id: str,
    principal: AdminOnly,
    session: AsyncSession = Depends(get_session),
):
    """
    Charge le plan comptable d'un template (idempotent — ignore les comptes déjà existants).
    Rôle : ADMIN uniquement.
    """
    template = TEMPLATES.get(template_id)
    if not template:
        raise HTTPException(
            status_code=404,
            detail=f"Template '{template_id}' inconnu. Disponibles : {list(TEMPLATES.keys())}",
        )
    created, skipped, journals_created = await _load_template_accounts(
        session, template.accounts, template.journal_codes
    )
    return LoadTemplateResult(
        template_id=template_id,
        accounts_created=created,
        accounts_skipped=skipped,
        journals_created=journals_created,
    )


@router.post("/import/csv", response_model=CsvImportResult)
async def import_accounts_csv(
    principal: WriteAccess,
    file: UploadFile = File(..., description="Fichier CSV du plan de comptes"),
    session: AsyncSession = Depends(get_session),
):
    """
    Importe des comptes depuis un fichier CSV (idempotent).

    Format attendu (séparateur: virgule ou point-virgule) :
    ```
    code,name,account_class,account_type,account_nature,parent_code,allow_manual_entry,description
    101000,Capital social,1,PASSIF,CREDITEUR,10,true,
    ```
    Colonnes obligatoires : code, name, account_class, account_type, account_nature
    Colonnes optionnelles : parent_code, allow_manual_entry (true/false), description

    Rôles : ADMIN, ACCOUNTANT.
    """
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Le fichier doit être au format CSV (.csv).")

    content = await file.read()
    try:
        text = content.decode("utf-8-sig")  # BOM-safe
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    # Auto-detect delimiter
    sample = text[:1024]
    delimiter = ";" if sample.count(";") >= sample.count(",") else ","

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)

    required_cols = {"code", "name", "account_class", "account_type", "account_nature"}
    if not required_cols.issubset(set(reader.fieldnames or [])):
        missing = required_cols - set(reader.fieldnames or [])
        raise HTTPException(
            status_code=422,
            detail=f"Colonnes manquantes : {', '.join(sorted(missing))}. "
            f"Colonnes requises : {', '.join(sorted(required_cols))}",
        )

    # Pre-index existing accounts
    existing = (await session.execute(select(AccountPlan))).scalars().all()
    code_to_id: dict[str, str] = {acc.code: acc.id for acc in existing}

    from app.models.accounting import AccountClass, AccountNature, AccountType

    rows = list(reader)
    created = 0
    skipped = 0
    errors: list[str] = []

    for i, row in enumerate(rows, start=2):  # line 1 = header
        code = row.get("code", "").strip()
        name = row.get("name", "").strip()
        if not code or not name:
            errors.append(f"Ligne {i}: code ou libellé manquant — ignorée.")
            continue

        if code in code_to_id:
            skipped += 1
            continue

        # Validate enums
        try:
            acc_class = AccountClass(row["account_class"].strip())
            acc_type = AccountType(row["account_type"].strip())
            acc_nature = AccountNature(row["account_nature"].strip())
        except ValueError as e:
            errors.append(f"Ligne {i} ({code}): valeur invalide — {e}")
            continue

        parent_code = row.get("parent_code", "").strip() or None
        parent_id = code_to_id.get(parent_code) if parent_code else None
        level = 1
        path = ""

        if parent_id:
            parent = await session.get(AccountPlan, parent_id)
            if parent:
                level = parent.level + 1
                path = f"{parent.path}{parent_id}/"
                if parent.is_leaf:
                    parent.is_leaf = False
        elif parent_code and not parent_id:
            errors.append(
                f"Ligne {i} ({code}): compte parent '{parent_code}' introuvable — "
                "vérifiez que le parent apparaît avant l'enfant dans le fichier."
            )

        allow = row.get("allow_manual_entry", "true").strip().lower() not in ("false", "0", "non")
        description = row.get("description", "").strip() or None

        acc = AccountPlan(
            id=str(uuid.uuid4()),
            code=code,
            name=name,
            account_class=acc_class,
            account_type=acc_type,
            account_nature=acc_nature,
            parent_id=parent_id,
            level=level,
            path=path,
            is_leaf=True,
            allow_manual_entry=allow,
            description=description,
            currency="XOF",
        )
        session.add(acc)
        await session.flush()
        code_to_id[code] = acc.id
        created += 1

    await session.commit()
    return CsvImportResult(accounts_created=created, accounts_skipped=skipped, errors=errors)
