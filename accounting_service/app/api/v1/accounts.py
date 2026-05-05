"""
Router — Plan de comptes
"""

import csv
import io
import math
import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
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
from app.models.accounting import AccountClass, AccountNature, AccountPlan, AccountType, Journal, JournalCode
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


REQUIRED_COLS = {"code", "name", "account_class", "account_type", "account_nature"}

CSV_TEMPLATE = (
    "code,name,account_class,account_type,account_nature,parent_code,allow_manual_entry,description\n"
    "1,CAPITAUX PROPRES,CAPITAL,PASSIF,CREDITEUR,,false,Classe 1 - Comptes de capitaux\n"
    "10,Capital et dotations,CAPITAL,PASSIF,CREDITEUR,1,false,\n"
    "101000,Capital social,CAPITAL,PASSIF,CREDITEUR,10,true,Capital libéré\n"
    "5,TRÉSORERIE,TRESORERIE,ACTIF,DEBITEUR,,false,Classe 5 - Trésorerie\n"
    "57,Caisse,TRESORERIE,ACTIF,DEBITEUR,5,false,\n"
    "571000,Caisse principale,TRESORERIE,ACTIF,DEBITEUR,57,true,\n"
    "6,CHARGES,CHARGES,CHARGE,DEBITEUR,,false,Classe 6 - Charges\n"
    "7,PRODUITS,PRODUITS,PRODUIT,CREDITEUR,,false,Classe 7 - Produits\n"
)

ACCOUNT_CLASS_VALUES: dict[str, str] = {
    "1": "CAPITAL", "2": "IMMOBILISE", "3": "STOCK",
    "4": "TIERS", "5": "TRESORERIE", "6": "CHARGES", "7": "PRODUITS",
    "8": "SPECIAUX", "9": "ANALYTIQUE",
    "CAPITAL": "CAPITAL", "IMMOBILISE": "IMMOBILISE", "STOCK": "STOCK",
    "TIERS": "TIERS", "TRESORERIE": "TRESORERIE", "CHARGES": "CHARGES",
    "PRODUITS": "PRODUITS", "SPECIAUX": "SPECIAUX", "ANALYTIQUE": "ANALYTIQUE",
}


def _parse_csv_rows(content: bytes) -> list[dict]:
    """Decode CSV bytes and return list of row dicts."""
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")
    sample = text[:1024]
    delimiter = ";" if sample.count(";") >= sample.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    fieldnames = set(reader.fieldnames or [])
    missing = REQUIRED_COLS - fieldnames
    if missing:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Colonnes manquantes : {', '.join(sorted(missing))}. "
                f"Colonnes requises : {', '.join(sorted(REQUIRED_COLS))}"
            ),
        )
    return list(reader)


def _parse_pdf_rows(content: bytes) -> list[dict]:
    """Extract account rows from a PDF plan comptable using pdfplumber."""
    try:
        import pdfplumber
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail="Dépendance pdfplumber manquante. Contactez l'administrateur.",
        ) from exc

    rows: list[dict] = []
    header_found = False
    col_map: dict[str, int] = {}

    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if not table:
                    continue
                for row in table:
                    if row is None:
                        continue
                    cells = [str(c).strip() if c else "" for c in row]

                    # Try to detect header row
                    if not header_found:
                        lower = [c.lower() for c in cells]
                        if "code" in lower and "name" in lower:
                            col_map = {c.lower(): i for i, c in enumerate(lower)}
                            header_found = True
                            continue

                    if not header_found:
                        continue

                    def get(key: str) -> str:
                        idx = col_map.get(key, -1)
                        return cells[idx].strip() if 0 <= idx < len(cells) else ""

                    code = get("code")
                    name = get("name") or get("intitulé") or get("libellé")
                    if not code or not name:
                        continue

                    rows.append({
                        "code": code,
                        "name": name,
                        "account_class": get("account_class") or get("classe"),
                        "account_type": get("account_type") or get("type"),
                        "account_nature": get("account_nature") or get("nature"),
                        "parent_code": get("parent_code") or get("parent"),
                        "allow_manual_entry": get("allow_manual_entry") or "true",
                        "description": get("description") or get("description"),
                    })

    if not rows:
        raise HTTPException(
            status_code=422,
            detail=(
                "Aucun tableau avec les colonnes requises trouvé dans le PDF. "
                "Assurez-vous que le PDF contient un tableau avec au minimum les colonnes : "
                "code, name, account_class, account_type, account_nature."
            ),
        )

    missing_vals = REQUIRED_COLS - {"parent_code", "allow_manual_entry", "description"}
    sample_row = rows[0]
    empty_required = [k for k in missing_vals if not sample_row.get(k)]
    if empty_required:
        raise HTTPException(
            status_code=422,
            detail=f"Colonnes requises vides dans le PDF : {', '.join(empty_required)}. "
                   f"Colonnes attendues : {', '.join(sorted(REQUIRED_COLS))}",
        )
    return rows


@router.get("/import/template", response_class=Response)
async def download_import_template(_principal: AnyAuthenticated):
    """
    Télécharge un fichier CSV modèle pour l'import personnalisé.

    Valeurs valides pour account_class : CAPITAL, IMMOBILISE, STOCK, TIERS,
    TRESORERIE, CHARGES, PRODUITS, SPECIAUX, ANALYTIQUE (ou chiffres 1-9).
    Valeurs valides pour account_type  : ACTIF, PASSIF, CHARGE, PRODUIT.
    Valeurs valides pour account_nature : DEBITEUR, CREDITEUR.
    """
    return Response(
        content=CSV_TEMPLATE,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=plan_comptable_template.csv"},
    )


@router.post("/import", response_model=CsvImportResult)
async def import_accounts(
    principal: WriteAccess,
    file: UploadFile = File(..., description="Fichier CSV ou PDF du plan de comptes"),
    session: AsyncSession = Depends(get_session),
):
    """
    Importe des comptes depuis un fichier CSV ou PDF (idempotent).

    **Formats acceptés :** `.csv`, `.pdf`

    **Colonnes obligatoires (CSV) ou colonnes de tableau (PDF) :**
    `code`, `name`, `account_class`, `account_type`, `account_nature`

    **Colonnes optionnelles :** `parent_code`, `allow_manual_entry` (true/false), `description`

    **Valeurs valides pour account_class :**
    `CAPITAL` (1), `IMMOBILISE` (2), `STOCK` (3), `TIERS` (4), `TRESORERIE` (5),
    `CHARGES` (6), `PRODUITS` (7), `SPECIAUX` (8), `ANALYTIQUE` (9).
    Les chiffres 1-9 sont aussi acceptés.

    **Valeurs valides pour account_type :** `ACTIF`, `PASSIF`, `CHARGE`, `PRODUIT`

    **Valeurs valides pour account_nature :** `DEBITEUR`, `CREDITEUR`

    Rôles : ADMIN, ACCOUNTANT.
    """
    filename = (file.filename or "").lower()
    if not (filename.endswith(".csv") or filename.endswith(".pdf")):
        raise HTTPException(
            status_code=400,
            detail="Format non supporté. Utilisez un fichier .csv ou .pdf.",
        )

    content = await file.read()

    rows: list[dict]
    if filename.endswith(".pdf"):
        rows = _parse_pdf_rows(content)
    else:
        rows = _parse_csv_rows(content)

    # Pre-index existing accounts
    existing = (await session.execute(select(AccountPlan))).scalars().all()
    code_to_id: dict[str, str] = {acc.code: acc.id for acc in existing}

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

        # Validate enums — normalize numeric class values ("1" → "CAPITAL")
        raw_class = ACCOUNT_CLASS_VALUES.get(row["account_class"].strip().upper(), row["account_class"].strip())
        try:
            acc_class = AccountClass(raw_class)
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
