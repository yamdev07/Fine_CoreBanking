"""
Script de seed — Plan de comptes SYSCOHADA adapté IMF/Banque BCEAO.
À exécuter une seule fois après la migration initiale.

Usage: python scripts/seed_chart_of_accounts.py
"""
import asyncio
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionFactory
from app.models.accounting import (
    AccountClass, AccountNature, AccountPlan, AccountType,
    Journal, JournalCode,
)


@dataclass
class AccountDef:
    code: str
    name: str
    account_class: AccountClass
    account_type: AccountType
    account_nature: AccountNature
    parent_code: str | None = None
    is_leaf: bool = True
    allow_manual_entry: bool = True


# ─── Définition du plan de comptes ───────────────────────────────────────────

ACCOUNTS: list[AccountDef] = [
    # ── Classe 1 : Capitaux ────────────────────────────────────────────────
    AccountDef("1", "CAPITAUX", AccountClass.CAPITAL, AccountType.PASSIF, AccountNature.CREDITEUR, is_leaf=False),
    AccountDef("10", "Capital et réserves", AccountClass.CAPITAL, AccountType.PASSIF, AccountNature.CREDITEUR, "1", is_leaf=False),
    AccountDef("101000", "Capital social", AccountClass.CAPITAL, AccountType.PASSIF, AccountNature.CREDITEUR, "10"),
    AccountDef("106000", "Réserves", AccountClass.CAPITAL, AccountType.PASSIF, AccountNature.CREDITEUR, "10"),
    AccountDef("12", "Résultat de l'exercice", AccountClass.CAPITAL, AccountType.PASSIF, AccountNature.CREDITEUR, "1", is_leaf=False),
    AccountDef("120000", "Résultat net", AccountClass.CAPITAL, AccountType.PASSIF, AccountNature.CREDITEUR, "12"),

    # ── Classe 2 : Actifs immobilisés ─────────────────────────────────────
    AccountDef("2", "ACTIFS IMMOBILISÉS", AccountClass.IMMOBILISE, AccountType.ACTIF, AccountNature.DEBITEUR, is_leaf=False),
    AccountDef("21", "Immobilisations corporelles", AccountClass.IMMOBILISE, AccountType.ACTIF, AccountNature.DEBITEUR, "2", is_leaf=False),
    AccountDef("211000", "Terrains", AccountClass.IMMOBILISE, AccountType.ACTIF, AccountNature.DEBITEUR, "21"),
    AccountDef("213000", "Matériel et outillage", AccountClass.IMMOBILISE, AccountType.ACTIF, AccountNature.DEBITEUR, "21"),
    AccountDef("218000", "Matériel informatique", AccountClass.IMMOBILISE, AccountType.ACTIF, AccountNature.DEBITEUR, "21"),

    # ── Classe 3 : Opérations avec les institutions financières ───────────
    AccountDef("3", "OPÉRATIONS INTERBANCAIRES", AccountClass.STOCK, AccountType.ACTIF, AccountNature.DEBITEUR, is_leaf=False),
    AccountDef("31", "Comptes ordinaires BCEAO", AccountClass.STOCK, AccountType.ACTIF, AccountNature.DEBITEUR, "3", is_leaf=False),
    AccountDef("311000", "Compte courant BCEAO", AccountClass.STOCK, AccountType.ACTIF, AccountNature.DEBITEUR, "31"),

    # ── Classe 4 : Opérations avec la clientèle ───────────────────────────
    AccountDef("4", "OPÉRATIONS AVEC LA CLIENTÈLE", AccountClass.TIERS, AccountType.ACTIF, AccountNature.DEBITEUR, is_leaf=False),

    # Crédits accordés
    AccountDef("25", "Crédits à la clientèle", AccountClass.TIERS, AccountType.ACTIF, AccountNature.DEBITEUR, "4", is_leaf=False),
    AccountDef("251000", "Crédits à court terme", AccountClass.TIERS, AccountType.ACTIF, AccountNature.DEBITEUR, "25"),
    AccountDef("251100", "Crédits à court terme — Capital", AccountClass.TIERS, AccountType.ACTIF, AccountNature.DEBITEUR, "25"),
    AccountDef("252000", "Crédits à moyen terme", AccountClass.TIERS, AccountType.ACTIF, AccountNature.DEBITEUR, "25"),
    AccountDef("253000", "Crédits à long terme", AccountClass.TIERS, AccountType.ACTIF, AccountNature.DEBITEUR, "25"),
    AccountDef("257000", "Créances en souffrance", AccountClass.TIERS, AccountType.ACTIF, AccountNature.DEBITEUR, "25"),
    AccountDef("258000", "Créances irrécouvrables", AccountClass.TIERS, AccountType.ACTIF, AccountNature.DEBITEUR, "25"),

    # Dépôts de la clientèle (épargne)
    AccountDef("37", "Dépôts de la clientèle", AccountClass.TIERS, AccountType.PASSIF, AccountNature.CREDITEUR, "4", is_leaf=False),
    AccountDef("371000", "Dépôts à vue", AccountClass.TIERS, AccountType.PASSIF, AccountNature.CREDITEUR, "37"),
    AccountDef("371100", "Dépôts à vue — Épargne", AccountClass.TIERS, AccountType.PASSIF, AccountNature.CREDITEUR, "37"),
    AccountDef("372000", "Dépôts à terme", AccountClass.TIERS, AccountType.PASSIF, AccountNature.CREDITEUR, "37"),
    AccountDef("375000", "Plans d'épargne", AccountClass.TIERS, AccountType.PASSIF, AccountNature.CREDITEUR, "37"),

    # Tiers divers
    AccountDef("41", "Clients", AccountClass.TIERS, AccountType.ACTIF, AccountNature.DEBITEUR, "4", is_leaf=False),
    AccountDef("411000", "Clients — Comptes courants", AccountClass.TIERS, AccountType.ACTIF, AccountNature.DEBITEUR, "41"),
    AccountDef("411100", "Clients — Créances diverses", AccountClass.TIERS, AccountType.ACTIF, AccountNature.DEBITEUR, "41"),

    # ── Classe 5 : Trésorerie ─────────────────────────────────────────────
    AccountDef("5", "TRÉSORERIE", AccountClass.TRESORERIE, AccountType.ACTIF, AccountNature.DEBITEUR, is_leaf=False),
    AccountDef("57", "Caisse", AccountClass.TRESORERIE, AccountType.ACTIF, AccountNature.DEBITEUR, "5", is_leaf=False),
    AccountDef("571000", "Caisse principale", AccountClass.TRESORERIE, AccountType.ACTIF, AccountNature.DEBITEUR, "57"),
    AccountDef("571100", "Caisse principale — XOF", AccountClass.TRESORERIE, AccountType.ACTIF, AccountNature.DEBITEUR, "57"),
    AccountDef("572000", "Caisse secondaire", AccountClass.TRESORERIE, AccountType.ACTIF, AccountNature.DEBITEUR, "57"),
    AccountDef("52", "Banques", AccountClass.TRESORERIE, AccountType.ACTIF, AccountNature.DEBITEUR, "5", is_leaf=False),
    AccountDef("521000", "Banque principale", AccountClass.TRESORERIE, AccountType.ACTIF, AccountNature.DEBITEUR, "52"),

    # ── Classe 6 : Charges ────────────────────────────────────────────────
    AccountDef("6", "CHARGES", AccountClass.CHARGES, AccountType.CHARGE, AccountNature.DEBITEUR, is_leaf=False),
    AccountDef("66", "Charges financières", AccountClass.CHARGES, AccountType.CHARGE, AccountNature.DEBITEUR, "6", is_leaf=False),
    AccountDef("663000", "Charges d'intérêts sur dépôts", AccountClass.CHARGES, AccountType.CHARGE, AccountNature.DEBITEUR, "66"),
    AccountDef("663100", "Intérêts sur dépôts à vue", AccountClass.CHARGES, AccountType.CHARGE, AccountNature.DEBITEUR, "66"),
    AccountDef("663200", "Intérêts sur dépôts à terme", AccountClass.CHARGES, AccountType.CHARGE, AccountNature.DEBITEUR, "66"),
    AccountDef("69", "Dotations aux provisions", AccountClass.CHARGES, AccountType.CHARGE, AccountNature.DEBITEUR, "6", is_leaf=False),
    AccountDef("694000", "Dotations provisions créances", AccountClass.CHARGES, AccountType.CHARGE, AccountNature.DEBITEUR, "69"),
    AccountDef("694100", "Dotations provisions créances irrécouvrables", AccountClass.CHARGES, AccountType.CHARGE, AccountNature.DEBITEUR, "69"),

    # ── Classe 7 : Produits ───────────────────────────────────────────────
    AccountDef("7", "PRODUITS", AccountClass.PRODUITS, AccountType.PRODUIT, AccountNature.CREDITEUR, is_leaf=False),
    AccountDef("70", "Produits financiers", AccountClass.PRODUITS, AccountType.PRODUIT, AccountNature.CREDITEUR, "7", is_leaf=False),
    AccountDef("701000", "Intérêts sur crédits", AccountClass.PRODUITS, AccountType.PRODUIT, AccountNature.CREDITEUR, "70"),
    AccountDef("701100", "Intérêts sur crédits à court terme", AccountClass.PRODUITS, AccountType.PRODUIT, AccountNature.CREDITEUR, "70"),
    AccountDef("701200", "Intérêts sur crédits à moyen terme", AccountClass.PRODUITS, AccountType.PRODUIT, AccountNature.CREDITEUR, "70"),
    AccountDef("701900", "Pénalités et frais de recouvrement", AccountClass.PRODUITS, AccountType.PRODUIT, AccountNature.CREDITEUR, "70"),
    AccountDef("78", "Reprises sur provisions", AccountClass.PRODUITS, AccountType.PRODUIT, AccountNature.CREDITEUR, "7", is_leaf=False),
    AccountDef("781000", "Reprises sur provisions créances", AccountClass.PRODUITS, AccountType.PRODUIT, AccountNature.CREDITEUR, "78"),
]

# ─── Journaux ─────────────────────────────────────────────────────────────────

JOURNALS = [
    {"code": "GJ", "name": "Journal Général", "type": JournalCode.GJ, "prefix": "GJ"},
    {"code": "CJ", "name": "Journal de Caisse", "type": JournalCode.CJ, "prefix": "CJ"},
    {"code": "BJ", "name": "Journal de Banque", "type": JournalCode.BJ, "prefix": "BJ"},
    {"code": "OD", "name": "Opérations Diverses", "type": JournalCode.OD, "prefix": "OD"},
    {"code": "AN", "name": "À-Nouveau", "type": JournalCode.AN, "prefix": "AN"},
    {"code": "EX", "name": "Extournes", "type": JournalCode.EX, "prefix": "EX"},
    {"code": "CR", "name": "Journal Crédits", "type": JournalCode.CR, "prefix": "CR"},
    {"code": "EP", "name": "Journal Épargne", "type": JournalCode.EP, "prefix": "EP"},
]


async def seed(session: AsyncSession) -> None:
    print("Création du plan de comptes SYSCOHADA...")

    # Index code → id pour la hiérarchie
    code_to_id: dict[str, str] = {}

    for acc_def in ACCOUNTS:
        existing = (
            await session.execute(
                __import__("sqlalchemy", fromlist=["select"]).select(AccountPlan).where(
                    AccountPlan.code == acc_def.code
                )
            )
        ).scalar_one_or_none()

        if existing:
            code_to_id[acc_def.code] = existing.id
            continue

        parent_id = code_to_id.get(acc_def.parent_code) if acc_def.parent_code else None
        level = 1
        path = ""

        if parent_id:
            parent = await session.get(AccountPlan, parent_id)
            level = parent.level + 1
            path = f"{parent.path}{parent_id}/"
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
        print(f"  ✓ {acc_def.code} — {acc_def.name}")

    print("\nCréation des journaux...")
    for j in JOURNALS:
        from sqlalchemy import select
        existing = (
            await session.execute(select(Journal).where(Journal.code == j["code"]))
        ).scalar_one_or_none()
        if existing:
            continue
        journal = Journal(
            id=str(uuid.uuid4()),
            code=j["code"],
            name=j["name"],
            journal_type=j["type"],
            sequence_prefix=j["prefix"] + "-",
        )
        session.add(journal)
        print(f"  ✓ {j['code']} — {j['name']}")

    await session.commit()
    print("\n✅ Seed terminé avec succès.")


async def main() -> None:
    async with AsyncSessionFactory() as session:
        await seed(session)


if __name__ == "__main__":
    asyncio.run(main())
