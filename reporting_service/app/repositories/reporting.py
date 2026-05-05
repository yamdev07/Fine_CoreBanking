"""
Repository Reporting — Requêtes SQL en lecture seule sur la base comptabilité.
Toutes les requêtes utilisent des vues agrégées pour la performance.
"""
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class ReportingRepository:
    """
    Couche d'accès aux données pour les rapports.
    Toutes les méthodes sont en lecture seule (SELECT uniquement).
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def _fetch(self, sql: str, params: dict) -> list[dict]:
        result = await self.session.execute(text(sql), params)
        return [dict(r) for r in result.mappings().all()]

    async def _fetch_one(self, sql: str, params: dict) -> dict | None:
        result = await self.session.execute(text(sql), params)
        row = result.mappings().one_or_none()
        return dict(row) if row else None

    # ─── Exercice fiscal ──────────────────────────────────────────────────────

    async def get_fiscal_years(self) -> list[dict]:
        return await self._fetch(
            "SELECT * FROM fiscal_years ORDER BY start_date DESC", {}
        )

    async def get_fiscal_year_by_id(self, fiscal_year_id: str) -> dict | None:
        return await self._fetch_one(
            "SELECT * FROM fiscal_years WHERE id = :id",
            {"id": fiscal_year_id},
        )

    async def get_fiscal_year_for_date(self, d: date) -> dict | None:
        return await self._fetch_one(
            """
            SELECT * FROM fiscal_years
            WHERE start_date <= :d AND end_date >= :d
            LIMIT 1
            """,
            {"d": d},
        )

    async def get_previous_fiscal_year(self, current_start: date) -> dict | None:
        return await self._fetch_one(
            """
            SELECT * FROM fiscal_years
            WHERE end_date < :current_start
            ORDER BY end_date DESC
            LIMIT 1
            """,
            {"current_start": current_start},
        )

    # ─── Balance générale ─────────────────────────────────────────────────────

    async def get_trial_balance(
        self, start_date: date, end_date: date
    ) -> list[dict]:
        """
        Balance avec soldes d'ouverture, mouvements de période, et soldes de clôture.
        L'ouverture = cumul de toutes les écritures AVANT start_date.
        """
        sql = """
        WITH
        opening AS (
            SELECT
                jl.account_id,
                COALESCE(SUM(jl.debit_amount),  0) AS open_debit,
                COALESCE(SUM(jl.credit_amount), 0) AS open_credit
            FROM journal_lines jl
            JOIN journal_entries je ON je.id = jl.entry_id
            WHERE je.status = 'POSTED'
              AND je.entry_date < :start_date
            GROUP BY jl.account_id
        ),
        period AS (
            SELECT
                jl.account_id,
                COALESCE(SUM(jl.debit_amount),  0) AS per_debit,
                COALESCE(SUM(jl.credit_amount), 0) AS per_credit
            FROM journal_lines jl
            JOIN journal_entries je ON je.id = jl.entry_id
            WHERE je.status = 'POSTED'
              AND je.entry_date BETWEEN :start_date AND :end_date
            GROUP BY jl.account_id
        )
        SELECT
            ap.id            AS account_id,
            ap.code          AS account_code,
            ap.name          AS account_name,
            ap.account_class,
            ap.account_type,
            ap.account_nature,
            ap.currency,
            COALESCE(o.open_debit,  0) AS opening_debit,
            COALESCE(o.open_credit, 0) AS opening_credit,
            COALESCE(p.per_debit,   0) AS period_debit,
            COALESCE(p.per_credit,  0) AS period_credit,
            COALESCE(o.open_debit,  0) + COALESCE(p.per_debit,  0) AS cumulative_debit,
            COALESCE(o.open_credit, 0) + COALESCE(p.per_credit, 0) AS cumulative_credit
        FROM account_plans ap
        LEFT JOIN opening o ON o.account_id = ap.id
        LEFT JOIN period  p ON p.account_id = ap.id
        WHERE ap.is_leaf = TRUE
          AND ap.is_active = TRUE
          AND (
              COALESCE(o.open_debit, 0)  > 0 OR
              COALESCE(o.open_credit, 0) > 0 OR
              COALESCE(p.per_debit, 0)   > 0 OR
              COALESCE(p.per_credit, 0)  > 0
          )
        ORDER BY ap.code
        """
        return await self._fetch(sql, {"start_date": start_date, "end_date": end_date})

    # ─── Grand livre ──────────────────────────────────────────────────────────

    async def get_account_opening_balance(
        self, account_id: str, before_date: date
    ) -> dict:
        row = await self._fetch_one(
            """
            SELECT
                COALESCE(SUM(jl.debit_amount),  0) AS total_debit,
                COALESCE(SUM(jl.credit_amount), 0) AS total_credit
            FROM journal_lines jl
            JOIN journal_entries je ON je.id = jl.entry_id
            WHERE jl.account_id = :account_id
              AND je.status = 'POSTED'
              AND je.entry_date < :before_date
            """,
            {"account_id": account_id, "before_date": before_date},
        )
        return row or {"total_debit": Decimal("0"), "total_credit": Decimal("0")}

    async def get_general_ledger(
        self, account_id: str, start_date: date, end_date: date,
        offset: int = 0, limit: int = 500,
    ) -> list[dict]:
        return await self._fetch(
            """
            SELECT
                je.entry_number,
                je.entry_date,
                je.value_date,
                j.code   AS journal_code,
                je.description,
                je.reference,
                jl.third_party_id,
                jl.debit_amount,
                jl.credit_amount
            FROM journal_lines jl
            JOIN journal_entries je ON je.id = jl.entry_id
            JOIN journals j ON j.id = je.journal_id
            WHERE jl.account_id = :account_id
              AND je.status = 'POSTED'
              AND je.entry_date BETWEEN :start_date AND :end_date
            ORDER BY je.entry_date, je.entry_number, jl.line_number
            OFFSET :offset LIMIT :limit
            """,
            {
                "account_id": account_id,
                "start_date": start_date,
                "end_date": end_date,
                "offset": offset,
                "limit": limit,
            },
        )

    async def get_account_by_code(self, code: str) -> dict | None:
        return await self._fetch_one(
            "SELECT * FROM account_plans WHERE code = :code", {"code": code}
        )

    async def get_account_by_id(self, account_id: str) -> dict | None:
        return await self._fetch_one(
            "SELECT * FROM account_plans WHERE id = :id", {"id": account_id}
        )

    # ─── Bilan — agrégat par classe de comptes ────────────────────────────────

    async def get_balance_by_account_class(
        self, end_date: date, account_classes: list[str],
        account_type: str | None = None,
    ) -> list[dict]:
        """Soldes à une date donnée, filtrés par classe(s) et optionnellement par type (ACTIF/PASSIF)."""
        placeholders = ", ".join(f":cls{i}" for i in range(len(account_classes)))
        params = {"end_date": end_date}
        for i, cls in enumerate(account_classes):
            params[f"cls{i}"] = cls

        type_filter = ""
        if account_type:
            params["account_type"] = account_type
            type_filter = "AND ap.account_type = :account_type"

        sql = f"""
        SELECT
            ap.code          AS account_code,
            ap.name          AS account_name,
            ap.account_class,
            ap.account_type,
            ap.account_nature,
            COALESCE(SUM(jl.debit_amount),  0) AS total_debit,
            COALESCE(SUM(jl.credit_amount), 0) AS total_credit
        FROM account_plans ap
        LEFT JOIN journal_lines jl ON jl.account_id = ap.id
        LEFT JOIN journal_entries je ON je.id = jl.entry_id
            AND je.status = 'POSTED'
            AND je.entry_date <= :end_date
        WHERE ap.is_leaf = TRUE
          AND ap.is_active = TRUE
          AND ap.account_class IN ({placeholders})
          {type_filter}
        GROUP BY ap.id, ap.code, ap.name, ap.account_class, ap.account_type, ap.account_nature
        HAVING COALESCE(SUM(jl.debit_amount), 0) > 0
            OR COALESCE(SUM(jl.credit_amount), 0) > 0
        ORDER BY ap.code
        """
        return await self._fetch(sql, params)

    async def get_largest_credit_exposure(self, as_of_date: date) -> Decimal:
        """Plus grande exposition crédit individuelle par tiers (pour ratio R4 BCEAO)."""
        row = await self._fetch_one(
            """
            SELECT COALESCE(MAX(exposure), 0) AS max_exposure
            FROM (
                SELECT
                    jl.third_party_id,
                    COALESCE(SUM(jl.debit_amount), 0) -
                    COALESCE(SUM(jl.credit_amount), 0) AS exposure
                FROM journal_lines jl
                JOIN journal_entries je ON je.id = jl.entry_id
                JOIN account_plans ap ON ap.id = jl.account_id
                WHERE je.status = 'POSTED'
                  AND je.entry_date <= :as_of_date
                  AND ap.code LIKE '25%'
                  AND ap.is_leaf = TRUE
                  AND jl.third_party_id IS NOT NULL
                GROUP BY jl.third_party_id
                HAVING COALESCE(SUM(jl.debit_amount), 0) -
                       COALESCE(SUM(jl.credit_amount), 0) > 0
            ) exposures
            """,
            {"as_of_date": as_of_date},
        )
        return Decimal(str(row["max_exposure"])) if row else Decimal("0")

    # ─── Compte de résultat ───────────────────────────────────────────────────

    async def get_charges_produits(
        self, start_date: date, end_date: date
    ) -> list[dict]:
        """Mouvements des classes 6 (charges) et 7 (produits) sur la période."""
        return await self._fetch(
            """
            SELECT
                ap.code          AS account_code,
                ap.name          AS account_name,
                ap.account_class,
                ap.account_type,
                COALESCE(SUM(jl.debit_amount),  0) AS total_debit,
                COALESCE(SUM(jl.credit_amount), 0) AS total_credit
            FROM account_plans ap
            JOIN journal_lines jl ON jl.account_id = ap.id
            JOIN journal_entries je ON je.id = jl.entry_id
            WHERE je.status = 'POSTED'
              AND je.entry_date BETWEEN :start_date AND :end_date
              AND ap.account_class IN ('CHARGES', 'PRODUITS')
              AND ap.is_leaf = TRUE
            GROUP BY ap.id, ap.code, ap.name, ap.account_class, ap.account_type
            ORDER BY ap.code
            """,
            {"start_date": start_date, "end_date": end_date},
        )

    # ─── Portefeuille crédits ─────────────────────────────────────────────────

    async def get_credit_portfolio(self, as_of_date: date) -> list[dict]:
        """Encours de chaque sous-compte crédits (classe 25x)."""
        return await self._fetch(
            """
            SELECT
                ap.code          AS account_code,
                ap.name          AS account_name,
                COALESCE(SUM(jl.debit_amount),  0) -
                COALESCE(SUM(jl.credit_amount), 0) AS encours
            FROM account_plans ap
            LEFT JOIN journal_lines jl ON jl.account_id = ap.id
            LEFT JOIN journal_entries je ON je.id = jl.entry_id
                AND je.status = 'POSTED'
                AND je.entry_date <= :as_of_date
            WHERE ap.is_leaf = TRUE
              AND ap.code LIKE '25%'
            GROUP BY ap.id, ap.code, ap.name
            ORDER BY ap.code
            """,
            {"as_of_date": as_of_date},
        )

    async def get_provisions(self, as_of_date: date) -> Decimal:
        """Provisions constituées (compte 694xxx)."""
        row = await self._fetch_one(
            """
            SELECT COALESCE(SUM(jl.debit_amount), 0) -
                   COALESCE(SUM(jl.credit_amount), 0) AS provisions
            FROM journal_lines jl
            JOIN journal_entries je ON je.id = jl.entry_id
            JOIN account_plans ap ON ap.id = jl.account_id
            WHERE je.status = 'POSTED'
              AND je.entry_date <= :as_of_date
              AND ap.code LIKE '694%'
            """,
            {"as_of_date": as_of_date},
        )
        return Decimal(str(row["provisions"])) if row else Decimal("0")

    # ─── Dépôts / Épargne ────────────────────────────────────────────────────

    async def get_deposits_by_type(self, as_of_date: date) -> list[dict]:
        """Encours de chaque type de dépôt (classe 37x)."""
        return await self._fetch(
            """
            SELECT
                ap.code,
                ap.name,
                COALESCE(SUM(jl.credit_amount), 0) -
                COALESCE(SUM(jl.debit_amount),  0) AS encours
            FROM account_plans ap
            LEFT JOIN journal_lines jl ON jl.account_id = ap.id
            LEFT JOIN journal_entries je ON je.id = jl.entry_id
                AND je.status = 'POSTED'
                AND je.entry_date <= :as_of_date
            WHERE ap.is_leaf = TRUE
              AND ap.code LIKE '37%'
            GROUP BY ap.id, ap.code, ap.name
            ORDER BY ap.code
            """,
            {"as_of_date": as_of_date},
        )

    async def get_interest_charges(
        self, start_date: date, end_date: date
    ) -> Decimal:
        """Charges d'intérêts sur dépôts (663xxx) de la période."""
        row = await self._fetch_one(
            """
            SELECT COALESCE(SUM(jl.debit_amount), 0) AS charges
            FROM journal_lines jl
            JOIN journal_entries je ON je.id = jl.entry_id
            JOIN account_plans ap ON ap.id = jl.account_id
            WHERE je.status = 'POSTED'
              AND je.entry_date BETWEEN :start_date AND :end_date
              AND ap.code LIKE '663%'
            """,
            {"start_date": start_date, "end_date": end_date},
        )
        return Decimal(str(row["charges"])) if row else Decimal("0")

    # ─── Trésorerie ───────────────────────────────────────────────────────────

    async def get_cash_balance(self, as_of_date: date) -> Decimal:
        """Solde de trésorerie (classes 57x + 52x)."""
        row = await self._fetch_one(
            """
            SELECT
                COALESCE(SUM(jl.debit_amount),  0) -
                COALESCE(SUM(jl.credit_amount), 0) AS solde
            FROM journal_lines jl
            JOIN journal_entries je ON je.id = jl.entry_id
            JOIN account_plans ap ON ap.id = jl.account_id
            WHERE je.status = 'POSTED'
              AND je.entry_date <= :as_of_date
              AND (ap.code LIKE '57%' OR ap.code LIKE '52%')
              AND ap.is_leaf = TRUE
            """,
            {"as_of_date": as_of_date},
        )
        return Decimal(str(row["solde"])) if row else Decimal("0")

    async def get_cash_flows(
        self, start_date: date, end_date: date, account_prefix: str
    ) -> Decimal:
        """Flux de trésorerie sur des comptes spécifiques."""
        row = await self._fetch_one(
            """
            SELECT
                COALESCE(SUM(jl.debit_amount),  0) -
                COALESCE(SUM(jl.credit_amount), 0) AS flux
            FROM journal_lines jl
            JOIN journal_entries je ON je.id = jl.entry_id
            JOIN account_plans ap ON ap.id = jl.account_id
            WHERE je.status = 'POSTED'
              AND je.entry_date BETWEEN :start_date AND :end_date
              AND ap.code LIKE :prefix
              AND ap.is_leaf = TRUE
            """,
            {
                "start_date": start_date,
                "end_date": end_date,
                "prefix": f"{account_prefix}%",
            },
        )
        return Decimal(str(row["flux"])) if row else Decimal("0")

    # ─── Journal centralisateur ───────────────────────────────────────────────

    async def get_journal_centralizer(
        self, start_date: date, end_date: date
    ) -> list[dict]:
        return await self._fetch(
            """
            SELECT
                j.code           AS journal_code,
                j.name           AS journal_name,
                COUNT(je.id)     AS nb_ecritures,
                COALESCE(SUM(je.total_debit),  0) AS total_debit,
                COALESCE(SUM(je.total_credit), 0) AS total_credit
            FROM journals j
            LEFT JOIN journal_entries je ON je.journal_id = j.id
                AND je.status = 'POSTED'
                AND je.entry_date BETWEEN :start_date AND :end_date
            GROUP BY j.id, j.code, j.name
            ORDER BY j.code
            """,
            {"start_date": start_date, "end_date": end_date},
        )

    # ─── KPIs rapides ─────────────────────────────────────────────────────────

    async def get_net_income(
        self, start_date: date, end_date: date
    ) -> Decimal:
        """Résultat net = Produits (cl.7) - Charges (cl.6)."""
        row = await self._fetch_one(
            """
            SELECT
                COALESCE(SUM(CASE WHEN ap.account_class = 'PRODUITS'
                    THEN jl.credit_amount - jl.debit_amount ELSE 0 END), 0) -
                COALESCE(SUM(CASE WHEN ap.account_class = 'CHARGES'
                    THEN jl.debit_amount - jl.credit_amount ELSE 0 END), 0)
                AS resultat_net
            FROM journal_lines jl
            JOIN journal_entries je ON je.id = jl.entry_id
            JOIN account_plans ap ON ap.id = jl.account_id
            WHERE je.status = 'POSTED'
              AND je.entry_date BETWEEN :start_date AND :end_date
              AND ap.account_class IN ('CHARGES', 'PRODUITS')
            """,
            {"start_date": start_date, "end_date": end_date},
        )
        return Decimal(str(row["resultat_net"])) if row else Decimal("0")

    async def get_equity(self, as_of_date: date) -> Decimal:
        """Capitaux propres (classe 1 — hors résultat courant)."""
        row = await self._fetch_one(
            """
            SELECT
                COALESCE(SUM(jl.credit_amount), 0) -
                COALESCE(SUM(jl.debit_amount),  0) AS equity
            FROM journal_lines jl
            JOIN journal_entries je ON je.id = jl.entry_id
            JOIN account_plans ap ON ap.id = jl.account_id
            WHERE je.status = 'POSTED'
              AND je.entry_date <= :as_of_date
              AND ap.account_class = 'CAPITAL'
              AND ap.is_leaf = TRUE
            """,
            {"as_of_date": as_of_date},
        )
        return Decimal(str(row["equity"])) if row else Decimal("0")

    async def get_total_assets(self, as_of_date: date) -> Decimal:
        """Total actif (classes 2, 3, 4 actif, 5)."""
        row = await self._fetch_one(
            """
            SELECT
                COALESCE(SUM(jl.debit_amount),  0) -
                COALESCE(SUM(jl.credit_amount), 0) AS total_assets
            FROM journal_lines jl
            JOIN journal_entries je ON je.id = jl.entry_id
            JOIN account_plans ap ON ap.id = jl.account_id
            WHERE je.status = 'POSTED'
              AND je.entry_date <= :as_of_date
              AND ap.account_type = 'ACTIF'
              AND ap.is_leaf = TRUE
            """,
            {"as_of_date": as_of_date},
        )
        return Decimal(str(row["total_assets"])) if row else Decimal("0")
