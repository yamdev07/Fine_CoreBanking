"""
Tests d'intégration — API Reporting complète.
Lance un vrai serveur FastAPI contre une base SQLite en mémoire
peuplée avec des données de test réalistes.
"""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# On réutilise les modèles du service comptabilité
# (en production le reporting pointe sur la même DB)
from tests.fixtures.db_models import (
    AccountPlan, AccountingPeriod, FiscalYear, Journal,
    JournalEntry, JournalLine, Base,
    AccountClass, AccountNature, AccountType,
    EntryStatus, FiscalYearStatus, JournalCode, PeriodStatus,
)
from app.main import app
from app.db.session import get_session


# ─── Setup base de test ───────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="module")
async def test_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="module")
async def db_session(test_engine):
    factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with factory() as session:
        yield session


@pytest_asyncio.fixture(scope="module")
async def seeded_db(db_session):
    """Peuple la base avec un exercice fiscal complet + écritures représentatives."""
    s = db_session

    # Exercice 2024
    fy = FiscalYear(
        id=str(uuid.uuid4()), name="2024",
        start_date=date(2024, 1, 1), end_date=date(2024, 12, 31),
        status=FiscalYearStatus.OPEN,
    )
    s.add(fy)

    # Exercice 2023 (pour comparatifs N-1)
    fy_prev = FiscalYear(
        id=str(uuid.uuid4()), name="2023",
        start_date=date(2023, 1, 1), end_date=date(2023, 12, 31),
        status=FiscalYearStatus.CLOSED,
    )
    s.add(fy_prev)

    # Périodes
    p1 = AccountingPeriod(
        id=str(uuid.uuid4()), fiscal_year_id=fy.id,
        name="2024-01", start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31), status=PeriodStatus.OPEN,
    )
    p2 = AccountingPeriod(
        id=str(uuid.uuid4()), fiscal_year_id=fy.id,
        name="2024-06", start_date=date(2024, 6, 1),
        end_date=date(2024, 6, 30), status=PeriodStatus.OPEN,
    )
    s.add_all([p1, p2])

    # Comptes SYSCOHADA
    accounts_data = [
        ("101000", "Capital social",         "1", "PASSIF",  "CREDITEUR"),
        ("211000", "Immobilisations",         "2", "ACTIF",   "DEBITEUR"),
        ("251100", "Crédits court terme",     "4", "ACTIF",   "DEBITEUR"),
        ("257000", "Créances en souffrance",  "4", "ACTIF",   "DEBITEUR"),
        ("371100", "Dépôts à vue",            "4", "PASSIF",  "CREDITEUR"),
        ("521000", "Banque principale",       "5", "ACTIF",   "DEBITEUR"),
        ("571100", "Caisse principale",       "5", "ACTIF",   "DEBITEUR"),
        ("663100", "Intérêts sur dépôts",     "6", "CHARGE",  "DEBITEUR"),
        ("694100", "Dotations provisions",    "6", "CHARGE",  "DEBITEUR"),
        ("701100", "Intérêts sur crédits",    "7", "PRODUIT", "CREDITEUR"),
        ("701900", "Pénalités recouvrement",  "7", "PRODUIT", "CREDITEUR"),
    ]
    accs = {}
    for code, name, cls, atype, anature in accounts_data:
        acc = AccountPlan(
            id=str(uuid.uuid4()), code=code, name=name,
            account_class=cls, account_type=atype,
            account_nature=anature, is_leaf=True,
            is_active=True, currency="XOF",
        )
        s.add(acc)
        accs[code] = acc

    # Journaux
    journals_data = [
        ("CJ", "Journal de Caisse", JournalCode.CJ, "CJ-"),
        ("CR", "Journal Crédits",   JournalCode.CR, "CR-"),
        ("EP", "Journal Épargne",   JournalCode.EP, "EP-"),
        ("OD", "Opérations Diverses", JournalCode.OD, "OD-"),
    ]
    jnls = {}
    for code, name, jtype, prefix in journals_data:
        j = Journal(
            id=str(uuid.uuid4()), code=code, name=name,
            journal_type=jtype, sequence_prefix=prefix, last_sequence=0,
        )
        s.add(j)
        jnls[code] = j

    await s.flush()

    def make_entry(journal, period, entry_date, desc, lines_data, n):
        entry = JournalEntry(
            id=str(uuid.uuid4()),
            entry_number=f"{journal.code}-2024-{n:06d}",
            journal_id=journal.id,
            period_id=period.id,
            entry_date=entry_date,
            value_date=entry_date,
            description=desc,
            total_debit=sum(d for _, d, _ in lines_data),
            total_credit=sum(c for _, _, c in lines_data),
            currency="XOF",
            status=EntryStatus.POSTED,
            created_by="test",
            posted_by="test",
            posting_date=datetime.now(timezone.utc),
        )
        return entry

    def make_lines(entry, lines_data, accs):
        result = []
        for i, (code, d, c) in enumerate(lines_data, start=1):
            result.append(JournalLine(
                id=str(uuid.uuid4()),
                entry_id=entry.id,
                account_id=accs[code].id,
                line_number=i,
                debit_amount=Decimal(str(d)),
                credit_amount=Decimal(str(c)),
                currency="XOF",
            ))
        return result

    # ── Écriture 1 : Apport en capital (janv 2024)
    e1 = make_entry(jnls["OD"], p1, date(2024, 1, 5),
                    "Apport capital fondateurs",
                    [("571100", 5000000, 0), ("101000", 0, 5000000)], 1)
    s.add(e1)
    await s.flush()
    for l in make_lines(e1, [("571100", 5000000, 0), ("101000", 0, 5000000)], accs):
        s.add(l)

    # ── Écriture 2 : Décaissement crédit (janv 2024)
    e2 = make_entry(jnls["CR"], p1, date(2024, 1, 15),
                    "Décaissement crédit client A",
                    [("251100", 1000000, 0), ("571100", 0, 1000000)], 2)
    s.add(e2)
    await s.flush()
    for l in make_lines(e2, [("251100", 1000000, 0), ("571100", 0, 1000000)], accs):
        s.add(l)

    # ── Écriture 3 : Dépôt épargne (janv 2024)
    e3 = make_entry(jnls["EP"], p1, date(2024, 1, 20),
                    "Dépôt épargne client B",
                    [("571100", 500000, 0), ("371100", 0, 500000)], 3)
    s.add(e3)
    await s.flush()
    for l in make_lines(e3, [("571100", 500000, 0), ("371100", 0, 500000)], accs):
        s.add(l)

    # ── Écriture 4 : Remboursement crédit avec intérêts (juin 2024)
    e4 = make_entry(jnls["CR"], p2, date(2024, 6, 10),
                    "Remboursement crédit + intérêts client A",
                    [
                        ("571100", 200000, 0),
                        ("251100", 0, 180000),
                        ("701100", 0, 20000),
                    ], 4)
    s.add(e4)
    await s.flush()
    for l in make_lines(e4, [
        ("571100", 200000, 0),
        ("251100", 0, 180000),
        ("701100", 0, 20000),
    ], accs):
        s.add(l)

    # ── Écriture 5 : Intérêts sur dépôts (juin 2024)
    e5 = make_entry(jnls["EP"], p2, date(2024, 6, 30),
                    "Intérêts sur dépôts Q2",
                    [("663100", 12500, 0), ("371100", 0, 12500)], 5)
    s.add(e5)
    await s.flush()
    for l in make_lines(e5, [("663100", 12500, 0), ("371100", 0, 12500)], accs):
        s.add(l)

    # ── Écriture 6 : Dotation provision (juin 2024)
    e6 = make_entry(jnls["OD"], p2, date(2024, 6, 30),
                    "Dotation provision créances douteuses",
                    [("694100", 50000, 0), ("257000", 0, 50000)], 6)
    s.add(e6)
    await s.flush()
    for l in make_lines(e6, [("694100", 50000, 0), ("257000", 0, 50000)], accs):
        s.add(l)

    await s.commit()
    return {"fy": fy, "fy_prev": fy_prev, "accs": accs, "jnls": jnls}


@pytest_asyncio.fixture(scope="module")
async def client(db_session, seeded_db):
    """Client HTTP avec injection de la session de test."""
    app.dependency_overrides[get_session] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


# ─── Tests santé ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "healthy"
    assert data["mode"] == "read-only"


@pytest.mark.asyncio
async def test_root(client):
    r = await client.get("/")
    assert r.status_code == 200
    assert r.json()["reports"] == 10


# ─── Tests Balance générale ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_trial_balance_json(client):
    r = await client.get(
        "/api/v1/reports/trial-balance",
        params={"start_date": "2024-01-01", "end_date": "2024-06-30"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "lines" in data
    assert data["account_count"] > 0
    assert "total_period_debit" in data
    assert "total_period_credit" in data
    # La balance doit être équilibrée
    assert data["is_balanced"] is True


@pytest.mark.asyncio
async def test_trial_balance_excel(client):
    r = await client.get(
        "/api/v1/reports/trial-balance",
        params={
            "start_date": "2024-01-01",
            "end_date": "2024-06-30",
            "format": "excel",
        },
    )
    assert r.status_code == 200
    assert "spreadsheet" in r.headers["content-type"]
    assert r.headers["content-disposition"].startswith("attachment")
    assert len(r.content) > 1000  # Le fichier Excel a une taille minimum


@pytest.mark.asyncio
async def test_trial_balance_invalid_dates(client):
    r = await client.get(
        "/api/v1/reports/trial-balance",
        params={"start_date": "2024-12-31", "end_date": "2024-01-01"},
    )
    assert r.status_code == 422


# ─── Tests Grand livre ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_general_ledger_by_code(client):
    r = await client.get(
        "/api/v1/reports/general-ledger",
        params={
            "start_date": "2024-01-01",
            "end_date": "2024-06-30",
            "account_code": "571100",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["account_code"] == "571100"
    assert "movements" in data
    assert data["movement_count"] >= 3  # 3 écritures touchent la caisse


@pytest.mark.asyncio
async def test_general_ledger_running_balance(client):
    """Le solde progressif doit être cohérent avec les mouvements."""
    r = await client.get(
        "/api/v1/reports/general-ledger",
        params={
            "start_date": "2024-01-01",
            "end_date": "2024-06-30",
            "account_code": "251100",
        },
    )
    assert r.status_code == 200
    data = r.json()
    # Caisse : débit 1 000 000 en janv, crédit 180 000 en juin → solde = 820 000
    closing = Decimal(str(data["closing_balance"]))
    assert closing == Decimal("820000")


@pytest.mark.asyncio
async def test_general_ledger_missing_params(client):
    r = await client.get(
        "/api/v1/reports/general-ledger",
        params={"start_date": "2024-01-01", "end_date": "2024-06-30"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_general_ledger_unknown_account(client):
    r = await client.get(
        "/api/v1/reports/general-ledger",
        params={
            "start_date": "2024-01-01",
            "end_date": "2024-06-30",
            "account_code": "999999",
        },
    )
    assert r.status_code == 404


# ─── Tests Compte de résultat ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_income_statement(client):
    r = await client.get(
        "/api/v1/reports/income-statement",
        params={"start_date": "2024-01-01", "end_date": "2024-06-30"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "produit_net_bancaire" in data
    assert "resultat_net" in data
    assert "total_produits" in data
    assert "total_charges" in data
    # Produits = 20 000 (intérêts crédits)
    total_prod = Decimal(str(data["total_produits"]))
    assert total_prod == Decimal("20000")
    # Charges = 12 500 (intérêts dépôts) + 50 000 (provisions) = 62 500
    total_chg = Decimal(str(data["total_charges"]))
    assert total_chg == Decimal("62500")
    # Résultat = 20 000 - 62 500 = -42 500
    resultat = Decimal(str(data["resultat_net"]))
    assert resultat == Decimal("-42500")


@pytest.mark.asyncio
async def test_income_statement_pnb(client):
    """PNB = produits financiers - charges financières."""
    r = await client.get(
        "/api/v1/reports/income-statement",
        params={"start_date": "2024-01-01", "end_date": "2024-06-30"},
    )
    data = r.json()
    pnb = Decimal(str(data["produit_net_bancaire"]))
    # PNB = 20 000 (intérêts crédits) - 12 500 (intérêts dépôts) = 7 500
    assert pnb == Decimal("7500")


# ─── Tests Portefeuille crédits ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_credit_portfolio(client):
    r = await client.get(
        "/api/v1/reports/credit-portfolio",
        params={"as_of_date": "2024-06-30"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "total_portefeuille" in data
    assert "taux_impayés" in data
    assert "provisions_constituees" in data
    assert "deficit_provisionnement" in data


# ─── Tests Dashboard ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dashboard_structure(client):
    r = await client.get(
        "/api/v1/reports/dashboard",
        params={"as_of_date": "2024-06-30"},
    )
    assert r.status_code == 200
    data = r.json()
    kpis = [
        "kpi_encours_credits", "kpi_encours_epargne", "kpi_tresorerie",
        "kpi_produit_net_bancaire", "kpi_taux_impayes", "kpi_taux_couverture",
        "kpi_resultat_net", "kpi_roe", "kpi_roa",
        "kpi_ratio_liquidite", "kpi_ratio_credits_depots",
    ]
    for kpi in kpis:
        assert kpi in data, f"KPI manquant : {kpi}"
        assert "value" in data[kpi]
        assert "label" in data[kpi]
        assert "unit" in data[kpi]


@pytest.mark.asyncio
async def test_dashboard_excel(client):
    r = await client.get(
        "/api/v1/reports/dashboard",
        params={"as_of_date": "2024-06-30", "format": "excel"},
    )
    assert r.status_code == 200
    assert "spreadsheet" in r.headers["content-type"]


# ─── Tests BCEAO ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bceao_ratios_present(client):
    r = await client.get(
        "/api/v1/reports/bceao-prudential",
        params={
            "as_of_date": "2024-06-30",
            "numero_agrement": "IMF-BJ-2024-001",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert "ratio_solvabilite" in data
    assert "ratio_liquidite" in data
    assert "ratio_transformation" in data
    assert "ratio_division_risques" in data
    assert "ratio_couverture_risques" in data
    assert data["total_ratios"] == 5
    assert "ratios_conformes" in data
    assert "fonds_propres_nets" in data


@pytest.mark.asyncio
async def test_bceao_pdf_export(client):
    r = await client.get(
        "/api/v1/reports/bceao-prudential",
        params={
            "as_of_date": "2024-06-30",
            "numero_agrement": "IMF-BJ-2024-001",
            "format": "pdf",
        },
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"  # Magic bytes PDF


# ─── Tests Journal centralisateur ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_journal_centralizer(client):
    r = await client.get(
        "/api/v1/reports/journal-centralizer",
        params={"start_date": "2024-01-01", "end_date": "2024-06-30"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "lines" in data
    assert data["total_ecritures"] >= 6
    assert data["is_balanced"] is True
    assert data["grand_total_debit"] == data["grand_total_credit"]


@pytest.mark.asyncio
async def test_journal_centralizer_excel(client):
    r = await client.get(
        "/api/v1/reports/journal-centralizer",
        params={
            "start_date": "2024-01-01",
            "end_date": "2024-06-30",
            "format": "excel",
        },
    )
    assert r.status_code == 200
    assert "spreadsheet" in r.headers["content-type"]


# ─── Tests exercices fiscaux ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fiscal_years_list(client):
    r = await client.get("/api/v1/reports/fiscal-years")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 2
    names = [fy["name"] for fy in data]
    assert "2024" in names
    assert "2023" in names
