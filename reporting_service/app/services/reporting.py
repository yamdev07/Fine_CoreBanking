"""
Service Reporting — Logique de génération de tous les rapports.
"""

from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    AccountNotFoundError,
    FiscalYearNotFoundError,
    InvalidDateRangeError,
)
from app.repositories.reporting import ReportingRepository
from app.schemas.reports import (
    BceaoRatioLine,
    BceaoReport,
    BilanLine,
    BilanReport,
    BilanSection,
    CompteDeResultatReport,
    CreditPortfolioLine,
    CreditPortfolioReport,
    DashboardReport,
    DepositReport,
    FluxTresorerieReport,
    GeneralLedgerReport,
    JournalCentralisateurLine,
    JournalCentralisateurReport,
    KPIValue,
    LedgerMovement,
    ReportHeader,
    ResultatLine,
    ResultatSection,
    TrialBalanceLine,
    TrialBalanceReport,
)


def utcnow() -> datetime:
    return datetime.now(UTC)


def pct(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    if denominator == 0:
        return None
    return (numerator / denominator * 100).quantize(Decimal("0.01"), ROUND_HALF_UP)


def variation_pct(current: Decimal, previous: Decimal) -> Decimal | None:
    if previous == 0:
        return None
    return ((current - previous) / abs(previous) * 100).quantize(Decimal("0.01"), ROUND_HALF_UP)


def make_header(title: str, start_date: date, end_date: date) -> ReportHeader:
    return ReportHeader(
        institution_name=settings.INSTITUTION_NAME,
        report_title=title,
        period_start=start_date,
        period_end=end_date,
        currency=settings.DEFAULT_CURRENCY,
        generated_at=utcnow(),
    )


class ReportingService:
    def __init__(self, session: AsyncSession):
        self.repo = ReportingRepository(session)

    def _validate_dates(self, start_date: date, end_date: date) -> None:
        if end_date < start_date:
            raise InvalidDateRangeError(
                f"La date de fin ({end_date}) doit être >= la date de début ({start_date})."
            )

    # ─── 1. Balance générale ──────────────────────────────────────────────────

    async def trial_balance(self, start_date: date, end_date: date) -> TrialBalanceReport:
        self._validate_dates(start_date, end_date)
        rows = await self.repo.get_trial_balance(start_date, end_date)

        lines = []
        t_open_d = t_open_c = t_per_d = t_per_c = t_cl_d = t_cl_c = Decimal("0")

        for r in rows:
            od = Decimal(str(r["opening_debit"]))
            oc = Decimal(str(r["opening_credit"]))
            pd = Decimal(str(r["period_debit"]))
            pc = Decimal(str(r["period_credit"]))
            cum_d = od + pd
            cum_c = oc + pc
            cl_d = max(cum_d - cum_c, Decimal("0"))
            cl_c = max(cum_c - cum_d, Decimal("0"))

            t_open_d += od
            t_open_c += oc
            t_per_d += pd
            t_per_c += pc
            t_cl_d += cl_d
            t_cl_c += cl_c

            lines.append(
                TrialBalanceLine(
                    account_code=r["account_code"],
                    account_name=r["account_name"],
                    account_class=r["account_class"],
                    account_type=r["account_type"],
                    account_nature=r["account_nature"],
                    opening_debit=od,
                    opening_credit=oc,
                    period_debit=pd,
                    period_credit=pc,
                    cumulative_debit=cum_d,
                    cumulative_credit=cum_c,
                    closing_debit=cl_d,
                    closing_credit=cl_c,
                )
            )

        return TrialBalanceReport(
            header=make_header("Balance Générale", start_date, end_date),
            lines=lines,
            total_opening_debit=t_open_d,
            total_opening_credit=t_open_c,
            total_period_debit=t_per_d,
            total_period_credit=t_per_c,
            total_closing_debit=t_cl_d,
            total_closing_credit=t_cl_c,
            is_balanced=(t_cl_d == t_cl_c),
            account_count=len(lines),
        )

    # ─── 2. Grand livre ───────────────────────────────────────────────────────

    async def general_ledger(
        self,
        account_id: str | None,
        account_code: str | None,
        start_date: date,
        end_date: date,
        page: int = 1,
        size: int = 500,
    ) -> GeneralLedgerReport:
        self._validate_dates(start_date, end_date)

        if account_id:
            account = await self.repo.get_account_by_id(account_id)
        elif account_code:
            account = await self.repo.get_account_by_code(account_code)
        else:
            raise AccountNotFoundError("Fournir account_id ou account_code.")

        if not account:
            raise AccountNotFoundError("Compte introuvable.")

        opening = await self.repo.get_account_opening_balance(account["id"], start_date)
        open_d = Decimal(str(opening["total_debit"]))
        open_c = Decimal(str(opening["total_credit"]))
        is_debiteur = account["account_nature"] == "DEBITEUR"
        running = open_d - open_c if is_debiteur else open_c - open_d
        open_bal = abs(running)
        open_nature = "DEBITEUR" if running >= 0 else "CREDITEUR"
        if not is_debiteur:
            open_nature = "CREDITEUR" if running >= 0 else "DEBITEUR"

        rows = await self.repo.get_general_ledger(
            account["id"],
            start_date,
            end_date,
            offset=(page - 1) * size,
            limit=size,
        )

        movements = []
        total_d = total_c = Decimal("0")
        balance = open_d - open_c if is_debiteur else open_c - open_d

        for r in rows:
            d = Decimal(str(r["debit_amount"]))
            c = Decimal(str(r["credit_amount"]))
            total_d += d
            total_c += c
            balance += (d - c) if is_debiteur else (c - d)
            movements.append(
                LedgerMovement(
                    entry_number=r["entry_number"],
                    entry_date=r["entry_date"],
                    value_date=r["value_date"],
                    journal_code=r["journal_code"],
                    description=r["description"],
                    reference=r.get("reference"),
                    third_party_id=r.get("third_party_id"),
                    debit_amount=d,
                    credit_amount=c,
                    running_balance=abs(balance),
                    balance_nature="DEBITEUR" if balance >= 0 else "CREDITEUR",
                )
            )

        closing = (
            open_d + total_d - open_c - total_c
            if is_debiteur
            else open_c + total_c - open_d - total_d
        )
        closing_nature = "DEBITEUR" if closing >= 0 else "CREDITEUR"
        if not is_debiteur:
            closing_nature = "CREDITEUR" if closing >= 0 else "DEBITEUR"

        return GeneralLedgerReport(
            header=make_header(
                f"Grand Livre — {account['code']} {account['name']}",
                start_date,
                end_date,
            ),
            account_code=account["code"],
            account_name=account["name"],
            account_class=account["account_class"],
            account_nature=account["account_nature"],
            opening_balance=open_bal,
            opening_balance_nature=open_nature,
            closing_balance=abs(closing),
            closing_balance_nature=closing_nature,
            total_debit=total_d,
            total_credit=total_c,
            movement_count=len(movements),
            movements=movements,
        )

    # ─── 3. Bilan comptable ───────────────────────────────────────────────────

    async def bilan(self, as_of_date: date) -> BilanReport:
        prev_fy = await self.repo.get_previous_fiscal_year(date(as_of_date.year, 1, 1))
        prev_date = (
            date(prev_fy["end_date"].year, prev_fy["end_date"].month, prev_fy["end_date"].day)
            if prev_fy
            else date(as_of_date.year - 1, 12, 31)
        )

        async def section(
            title: str,
            classes: list[str],
            nature: str,
            account_type: str | None = None,
        ) -> BilanSection:
            rows_cur = await self.repo.get_balance_by_account_class(
                as_of_date,
                classes,
                account_type=account_type,
            )
            rows_prev = await self.repo.get_balance_by_account_class(
                prev_date,
                classes,
                account_type=account_type,
            )
            prev_map = {r["account_code"]: r for r in rows_prev}
            lines = []
            subtotal_cur = subtotal_prev = Decimal("0")

            for r in rows_cur:
                d = Decimal(str(r["total_debit"]))
                c = Decimal(str(r["total_credit"]))
                cur = (d - c) if nature == "DEBITEUR" else (c - d)
                prev_r = prev_map.get(r["account_code"])
                if prev_r:
                    pd = Decimal(str(prev_r["total_debit"]))
                    pc = Decimal(str(prev_r["total_credit"]))
                    prev = (pd - pc) if nature == "DEBITEUR" else (pc - pd)
                else:
                    prev = Decimal("0")

                subtotal_cur += cur
                subtotal_prev += prev
                lines.append(
                    BilanLine(
                        account_code=r["account_code"],
                        account_name=r["account_name"],
                        account_class=r["account_class"],
                        current_year=cur,
                        previous_year=prev,
                        variation=cur - prev,
                        variation_pct=variation_pct(cur, prev),
                    )
                )

            return BilanSection(
                label=title,
                lines=lines,
                subtotal_current=subtotal_cur,
                subtotal_previous=subtotal_prev,
            )

        # ACTIF — filtré account_type=ACTIF pour éviter le double-counting des classes mixtes
        actif_immo = await section("Actif immobilisé", ["IMMOBILISE"], "DEBITEUR", "ACTIF")
        actif_circ = await section("Actif circulant", ["TIERS"], "DEBITEUR", "ACTIF")
        trso_actif = await section("Trésorerie — Actif", ["TRESORERIE"], "DEBITEUR", "ACTIF")

        # PASSIF — filtré account_type=PASSIF
        cap_propres = await section("Capitaux propres", ["CAPITAL"], "CREDITEUR", "PASSIF")
        dettes_cl = await section("Dettes clientèle", ["STOCK"], "CREDITEUR", "PASSIF")
        dettes_exp = await section("Dettes d'exploitation", ["TIERS"], "CREDITEUR", "PASSIF")

        # Trésorerie passif (découverts bancaires = solde créditeur en classe 5)
        rows_trso = await self.repo.get_balance_by_account_class(
            as_of_date, ["TRESORERIE"], "PASSIF"
        )
        rows_trso_prev = await self.repo.get_balance_by_account_class(
            prev_date, ["TRESORERIE"], "PASSIF"
        )
        trso_passif_cur = sum(
            max(Decimal(str(r["total_credit"])) - Decimal(str(r["total_debit"])), Decimal("0"))
            for r in rows_trso
        )
        trso_passif_prev_val = sum(
            max(Decimal(str(r["total_credit"])) - Decimal(str(r["total_debit"])), Decimal("0"))
            for r in rows_trso_prev
        )
        trso_passif = BilanSection(
            label="Trésorerie — Passif",
            lines=[],
            subtotal_current=trso_passif_cur,
            subtotal_previous=trso_passif_prev_val,
        )

        total_actif = (
            actif_immo.subtotal_current + actif_circ.subtotal_current + trso_actif.subtotal_current
        )
        total_passif = (
            cap_propres.subtotal_current
            + dettes_cl.subtotal_current
            + dettes_exp.subtotal_current
            + trso_passif.subtotal_current
        )
        total_actif_prev = (
            actif_immo.subtotal_previous
            + actif_circ.subtotal_previous
            + trso_actif.subtotal_previous
        )
        total_passif_prev = (
            cap_propres.subtotal_previous
            + dettes_cl.subtotal_previous
            + dettes_exp.subtotal_previous
            + trso_passif.subtotal_previous
        )

        return BilanReport(
            header=make_header("Bilan Comptable", as_of_date, as_of_date),
            actif_immobilise=actif_immo,
            actif_circulant=actif_circ,
            tresorerie_actif=trso_actif,
            total_actif=total_actif,
            total_actif_previous=total_actif_prev,
            capitaux_propres=cap_propres,
            dettes_financieres=dettes_cl,
            dettes_exploitation=dettes_exp,
            tresorerie_passif=trso_passif,
            total_passif=total_passif,
            total_passif_previous=total_passif_prev,
            is_balanced=abs(total_actif - total_passif) < Decimal("1"),
            reference_year=as_of_date.year - 1,
            current_year=as_of_date.year,
        )

    # ─── 4. Compte de résultat ────────────────────────────────────────────────

    async def compte_de_resultat(self, start_date: date, end_date: date) -> CompteDeResultatReport:
        self._validate_dates(start_date, end_date)
        prev_fy = await self.repo.get_previous_fiscal_year(start_date)
        prev_start = prev_end = None
        if prev_fy:
            prev_start = prev_fy["start_date"]
            prev_end = prev_fy["end_date"]

        rows = await self.repo.get_charges_produits(start_date, end_date)
        prev_rows = await self.repo.get_charges_produits(prev_start, prev_end) if prev_start else []
        prev_map = {r["account_code"]: r for r in prev_rows}

        def build_section(
            title: str,
            code_prefix: list[str],
            is_charge: bool,
        ) -> ResultatSection:
            lines = []
            subtotal_cur = subtotal_prev = Decimal("0")

            for r in rows:
                if not any(r["account_code"].startswith(p) for p in code_prefix):
                    continue
                d = Decimal(str(r["total_debit"]))
                c = Decimal(str(r["total_credit"]))
                cur = d - c if is_charge else c - d

                prev_r = prev_map.get(r["account_code"])
                if prev_r:
                    pd2 = Decimal(str(prev_r["total_debit"]))
                    pc2 = Decimal(str(prev_r["total_credit"]))
                    prev = pd2 - pc2 if is_charge else pc2 - pd2
                else:
                    prev = Decimal("0")

                subtotal_cur += cur
                subtotal_prev += prev
                lines.append(
                    ResultatLine(
                        account_code=r["account_code"],
                        account_name=r["account_name"],
                        current_year=cur,
                        previous_year=prev,
                        variation=cur - prev,
                        variation_pct=variation_pct(cur, prev),
                    )
                )
            return ResultatSection(
                label=title,
                lines=lines,
                subtotal_current=subtotal_cur,
                subtotal_previous=subtotal_prev,
            )

        produits_fin = build_section("Produits financiers", ["701", "702"], False)
        produits_acc = build_section("Produits accessoires", ["706", "707"], False)
        reprises = build_section("Reprises sur provisions", ["781"], False)
        charges_fin = build_section("Charges financières", ["663"], True)
        charges_exp = build_section(
            "Charges d'exploitation", ["60", "61", "62", "63", "64", "65"], True
        )
        dotations = build_section("Dotations aux provisions", ["694"], True)

        total_produits = (
            produits_fin.subtotal_current
            + produits_acc.subtotal_current
            + reprises.subtotal_current
        )
        total_charges = (
            charges_fin.subtotal_current + charges_exp.subtotal_current + dotations.subtotal_current
        )
        total_produits_prev = (
            produits_fin.subtotal_previous
            + produits_acc.subtotal_previous
            + reprises.subtotal_previous
        )
        total_charges_prev = (
            charges_fin.subtotal_previous
            + charges_exp.subtotal_previous
            + dotations.subtotal_previous
        )

        pnb = produits_fin.subtotal_current - charges_fin.subtotal_current
        rbe = total_produits - charges_fin.subtotal_current - charges_exp.subtotal_current
        resultat_net = total_produits - total_charges
        resultat_prev = total_produits_prev - total_charges_prev

        return CompteDeResultatReport(
            header=make_header("Compte de Résultat", start_date, end_date),
            produits_financiers=produits_fin,
            produits_accessoires=produits_acc,
            reprises_provisions=reprises,
            total_produits=total_produits,
            total_produits_previous=total_produits_prev,
            charges_financieres=charges_fin,
            charges_exploitation=charges_exp,
            dotations_provisions=dotations,
            total_charges=total_charges,
            total_charges_previous=total_charges_prev,
            produit_net_bancaire=pnb,
            resultat_brut_exploitation=rbe,
            resultat_net=resultat_net,
            resultat_net_previous=resultat_prev,
            variation_resultat_pct=variation_pct(resultat_net, resultat_prev),
        )

    # ─── 5. Flux de trésorerie ────────────────────────────────────────────────

    async def flux_tresorerie(self, start_date: date, end_date: date) -> FluxTresorerieReport:
        self._validate_dates(start_date, end_date)

        # Exploitation : variation des créances et dépôts
        var_credits = await self.repo.get_cash_flows(start_date, end_date, "251")
        var_depots = -(await self.repo.get_cash_flows(start_date, end_date, "371"))
        int_percus = await self.repo.get_cash_flows(start_date, end_date, "701")
        int_payes = -(await self.repo.get_cash_flows(start_date, end_date, "663"))
        flux_exp = var_credits + var_depots + int_percus + int_payes

        # Investissement : variation immobilisations
        var_immo = -(await self.repo.get_cash_flows(start_date, end_date, "21"))
        flux_inv = var_immo

        # Financement : variation capitaux propres
        var_cap = await self.repo.get_cash_flows(start_date, end_date, "10")
        flux_fin = var_cap

        trso_ouv = await self.repo.get_cash_balance(start_date)
        trso_clo = await self.repo.get_cash_balance(end_date)

        return FluxTresorerieReport(
            header=make_header("Tableau de Flux de Trésorerie", start_date, end_date),
            flux_exploitation=flux_exp,
            flux_exploitation_detail=[
                {"label": "Décaissements crédits (nets)", "montant": str(var_credits)},
                {"label": "Variation dépôts clients", "montant": str(var_depots)},
                {"label": "Intérêts perçus", "montant": str(int_percus)},
                {"label": "Intérêts payés", "montant": str(int_payes)},
            ],
            flux_investissement=flux_inv,
            flux_investissement_detail=[
                {"label": "Variation immobilisations", "montant": str(var_immo)},
            ],
            flux_financement=flux_fin,
            flux_financement_detail=[
                {"label": "Variation capitaux propres", "montant": str(var_cap)},
            ],
            variation_nette_tresorerie=flux_exp + flux_inv + flux_fin,
            tresorerie_ouverture=trso_ouv,
            tresorerie_cloture=trso_clo,
        )

    # ─── 6. Portefeuille crédits ──────────────────────────────────────────────

    async def credit_portfolio(self, as_of_date: date) -> CreditPortfolioReport:
        prev_date = date(as_of_date.year - 1, as_of_date.month, as_of_date.day)
        rows = await self.repo.get_credit_portfolio(as_of_date)
        rows_prev = await self.repo.get_credit_portfolio(prev_date)
        {r["account_code"]: r for r in rows_prev}
        provisions = await self.repo.get_provisions(as_of_date)

        def by_prefix(prefix: str) -> tuple[Decimal, Decimal]:
            cur = sum(
                Decimal(str(r["encours"])) for r in rows if r["account_code"].startswith(prefix)
            )
            prev = sum(
                Decimal(str(r["encours"]))
                for r in rows_prev
                if r["account_code"].startswith(prefix)
            )
            return cur, prev

        def portfolio_line(
            code: str, name: str, prefix: str, total: Decimal
        ) -> CreditPortfolioLine:
            cur, prev = by_prefix(prefix)
            return CreditPortfolioLine(
                account_code=code,
                account_name=name,
                encours=cur,
                encours_previous=prev,
                variation=cur - prev,
                pct_portefeuille=pct(cur, total) or Decimal("0"),
            )

        total_cur = sum(Decimal(str(r["encours"])) for r in rows if r["encours"] > 0)
        total_prev = sum(Decimal(str(r["encours"])) for r in rows_prev if r["encours"] > 0)

        ct = portfolio_line("251000", "Crédits court terme", "2510", total_cur)
        mt = portfolio_line("252000", "Crédits moyen terme", "2520", total_cur)
        lt = portfolio_line("253000", "Crédits long terme", "2530", total_cur)
        souf = portfolio_line("257000", "Créances en souffrance", "2570", total_cur)
        irr = portfolio_line("258000", "Créances irrécouvrables", "2580", total_cur)

        taux_imp = pct(souf.encours, total_cur) or Decimal("0")
        taux_dout = pct(souf.encours + irr.encours, total_cur) or Decimal("0")
        taux_couv = (
            pct(provisions, souf.encours + irr.encours)
            if (souf.encours + irr.encours) > 0
            else Decimal("100")
        )
        req = (souf.encours + irr.encours) * Decimal("0.5")  # 50% minimum

        return CreditPortfolioReport(
            header=make_header("État du Portefeuille de Crédits", as_of_date, as_of_date),
            credits_court_terme=ct,
            credits_moyen_terme=mt,
            credits_long_terme=lt,
            creances_souffrance=souf,
            creances_irrecouvrable=irr,
            total_portefeuille=total_cur,
            total_portefeuille_previous=total_prev,
            taux_impayés=taux_imp,
            taux_creances_douteuses=taux_dout,
            taux_couverture_provisions=taux_couv or Decimal("0"),
            provisions_constituees=provisions,
            provisions_requises=req,
            deficit_provisionnement=max(req - provisions, Decimal("0")),
        )

    # ─── 7. État des dépôts ───────────────────────────────────────────────────

    async def deposits(self, as_of_date: date, start_date: date, end_date: date) -> DepositReport:
        prev_date = date(as_of_date.year - 1, as_of_date.month, as_of_date.day)
        rows = await self.repo.get_deposits_by_type(as_of_date)
        rows_prev = await self.repo.get_deposits_by_type(prev_date)
        charges = await self.repo.get_interest_charges(start_date, end_date)

        def by_prefix(data: list[dict], prefix: str) -> Decimal:
            return sum(
                Decimal(str(r["encours"])) for r in data if r["code"].startswith(prefix)
            ) or Decimal("0")

        vue_cur = by_prefix(rows, "371")
        vue_prev = by_prefix(rows_prev, "371")
        terme_cur = by_prefix(rows, "372")
        terme_prev = by_prefix(rows_prev, "372")
        plan_cur = by_prefix(rows, "375")
        plan_prev = by_prefix(rows_prev, "375")

        total_cur = vue_cur + terme_cur + plan_cur
        total_prev = vue_prev + terme_prev + plan_prev

        credits_total = sum(
            Decimal(str(r["encours"]))
            for r in await self.repo.get_credit_portfolio(as_of_date)
            if r["encours"] > 0
        ) or Decimal("0")

        taux_remun = pct(charges, total_cur) or Decimal("0")
        ratio_cd = pct(credits_total, total_cur) or Decimal("0")

        return DepositReport(
            header=make_header("État des Dépôts", as_of_date, as_of_date),
            depots_vue=vue_cur,
            depots_vue_previous=vue_prev,
            depots_terme=terme_cur,
            depots_terme_previous=terme_prev,
            plans_epargne=plan_cur,
            plans_epargne_previous=plan_prev,
            total_depots=total_cur,
            total_depots_previous=total_prev,
            variation_pct=variation_pct(total_cur, total_prev),
            charges_interets_periode=charges,
            taux_moyen_remuneration=taux_remun,
            ratio_credits_depots=ratio_cd,
        )

    # ─── 8. Tableau de bord exécutif ─────────────────────────────────────────

    async def dashboard(self, as_of_date: date) -> DashboardReport:
        fy = await self.repo.get_fiscal_year_for_date(as_of_date)
        if not fy:
            raise FiscalYearNotFoundError(f"Aucun exercice fiscal pour la date {as_of_date}.")
        start = fy["start_date"]

        credits_rows = await self.repo.get_credit_portfolio(as_of_date)
        deposits_rows = await self.repo.get_deposits_by_type(as_of_date)
        tresorerie = await self.repo.get_cash_balance(as_of_date)
        resultat = await self.repo.get_net_income(start, as_of_date)
        equity = await self.repo.get_equity(as_of_date)
        total_assets = await self.repo.get_total_assets(as_of_date)
        provisions = await self.repo.get_provisions(as_of_date)
        await self.repo.get_interest_charges(start, as_of_date)
        pnb_rows = await self.repo.get_charges_produits(start, as_of_date)

        credits_total = sum(
            Decimal(str(r["encours"])) for r in credits_rows if r["encours"] > 0
        ) or Decimal("0")
        depots_vue = sum(
            Decimal(str(r["encours"])) for r in deposits_rows if r["code"].startswith("371")
        ) or Decimal("0")
        total_depots = sum(Decimal(str(r["encours"])) for r in deposits_rows) or Decimal("0")

        souffrance = sum(
            Decimal(str(r["encours"])) for r in credits_rows if r["account_code"].startswith("257")
        ) or Decimal("0")

        pnb_produits = sum(
            Decimal(str(r["total_credit"])) - Decimal(str(r["total_debit"]))
            for r in pnb_rows
            if r["account_class"] == "PRODUITS"
        ) or Decimal("0")
        pnb_charges = sum(
            Decimal(str(r["total_debit"])) - Decimal(str(r["total_credit"]))
            for r in pnb_rows
            if r["account_class"] == "CHARGES" and r["account_code"].startswith("663")
        ) or Decimal("0")
        pnb = pnb_produits - pnb_charges

        def kpi(label: str, val: Decimal, unit: str, prev: Decimal | None = None) -> KPIValue:
            vp = variation_pct(val, prev) if prev else None
            trend = None
            if vp is not None:
                trend = "UP" if vp > 0 else ("DOWN" if vp < 0 else "STABLE")
            return KPIValue(
                label=label,
                value=val,
                unit=unit,
                previous_value=prev,
                variation_pct=vp,
                trend=trend,
            )

        roe = pct(resultat, equity) or Decimal("0")
        roa = pct(resultat, total_assets) or Decimal("0")
        taux_imp = pct(souffrance, credits_total) or Decimal("0")
        taux_couv = pct(provisions, souffrance) if souffrance > 0 else Decimal("100")
        liq_ratio = pct(tresorerie, depots_vue) or Decimal("0")
        cd_ratio = pct(credits_total, total_depots) or Decimal("0")

        return DashboardReport(
            header=make_header("Tableau de Bord Exécutif", start, as_of_date),
            as_of_date=as_of_date,
            kpi_encours_credits=kpi("Encours crédits", credits_total, "XOF"),
            kpi_encours_epargne=kpi("Encours épargne", total_depots, "XOF"),
            kpi_tresorerie=kpi("Trésorerie", tresorerie, "XOF"),
            kpi_produit_net_bancaire=kpi("PNB", pnb, "XOF"),
            kpi_taux_impayes=kpi("Taux d'impayés", taux_imp, "%"),
            kpi_taux_couverture=kpi("Taux de couverture", taux_couv or Decimal("0"), "%"),
            kpi_resultat_net=kpi("Résultat net", resultat, "XOF"),
            kpi_roe=kpi("ROE", roe, "%"),
            kpi_roa=kpi("ROA", roa, "%"),
            kpi_ratio_liquidite=kpi("Ratio liquidité", liq_ratio, "%"),
            kpi_ratio_credits_depots=kpi("Crédits/Dépôts", cd_ratio, "%"),
        )

    # ─── 9. Rapport BCEAO prudentiel ─────────────────────────────────────────

    async def bceao_report(self, as_of_date: date, numero_agrement: str) -> BceaoReport:
        fy = await self.repo.get_fiscal_year_for_date(as_of_date)
        if not fy:
            raise FiscalYearNotFoundError(f"Aucun exercice fiscal pour la date {as_of_date}.")
        fy["start_date"]

        equity = await self.repo.get_equity(as_of_date)
        total_assets = await self.repo.get_total_assets(as_of_date)
        tresorerie = await self.repo.get_cash_balance(as_of_date)
        credits_rows = await self.repo.get_credit_portfolio(as_of_date)
        depots_rows = await self.repo.get_deposits_by_type(as_of_date)

        credits_total = sum(
            Decimal(str(r["encours"])) for r in credits_rows if r["encours"] > 0
        ) or Decimal("0")
        depots_ct = sum(
            Decimal(str(r["encours"]))
            for r in depots_rows
            if r["code"].startswith("371") or r["code"].startswith("372")
        ) or Decimal("0")

        fonds_propres = equity  # FPN = Capitaux propres (approx SYSCOHADA)
        largest_exposure = await self.repo.get_largest_credit_exposure(as_of_date)

        def ratio(
            code: str,
            libelle: str,
            num: Decimal,
            den: Decimal,
            norme: str,
            norme_val: Decimal,
            gte: bool = True,
        ) -> BceaoRatioLine:
            val = pct(num, den) or Decimal("0")
            conforme = val >= norme_val if gte else val <= norme_val
            return BceaoRatioLine(
                code_ratio=code,
                libelle=libelle,
                numerateur=num,
                denominateur=den,
                valeur=val,
                norme=norme,
                conforme=conforme,
            )

        r1 = ratio(
            "R1",
            "Ratio de solvabilité (Fonds propres / Actifs pondérés)",
            fonds_propres,
            total_assets,
            ">= 8%",
            Decimal("8"),
        )
        r2 = ratio(
            "R2",
            "Ratio de liquidité (Actifs liquides / Passifs CT)",
            tresorerie,
            depots_ct,
            ">= 75%",
            Decimal("75"),
        )
        r3 = ratio(
            "R3",
            "Ratio de transformation (Crédits LT / Ressources LT)",
            credits_total,
            fonds_propres + depots_ct,
            "<= 100%",
            Decimal("100"),
            gte=False,
        )
        r4 = ratio(
            "R4",
            "Division des risques (Plus gros risque individuel / FPN)",
            largest_exposure,
            fonds_propres,
            "<= 75%",
            Decimal("75"),
            gte=False,
        )
        r5 = ratio(
            "R5",
            "Couverture des risques (FPN / Encours crédits)",
            fonds_propres,
            credits_total,
            ">= 10%",
            Decimal("10"),
        )

        ratios = [r1, r2, r3, r4, r5]
        conformes = sum(1 for r in ratios if r.conforme)
        non_conformes = len(ratios) - conformes

        obs = None
        if non_conformes > 0:
            noms = [r.libelle for r in ratios if not r.conforme]
            obs = f"Ratios hors norme : {'; '.join(noms)}. Action corrective requise."

        return BceaoReport(
            header=make_header("États Prudentiels BCEAO/UEMOA", as_of_date, as_of_date),
            institution_agree=numero_agrement,
            date_arrete=as_of_date,
            fonds_propres_nets=fonds_propres,
            ratio_solvabilite=r1,
            ratio_liquidite=r2,
            ratio_transformation=r3,
            ratio_division_risques=r4,
            ratio_couverture_risques=r5,
            total_ratios=len(ratios),
            ratios_conformes=conformes,
            ratios_non_conformes=non_conformes,
            observations=obs,
        )

    # ─── 10. Journal centralisateur ───────────────────────────────────────────

    async def journal_centralizer(
        self, start_date: date, end_date: date
    ) -> JournalCentralisateurReport:
        self._validate_dates(start_date, end_date)
        rows = await self.repo.get_journal_centralizer(start_date, end_date)

        lines = []
        grand_d = grand_c = Decimal("0")
        total_ecr = 0

        for r in rows:
            d = Decimal(str(r["total_debit"]))
            c = Decimal(str(r["total_credit"]))
            grand_d += d
            grand_c += c
            total_ecr += int(r["nb_ecritures"])
            lines.append(
                JournalCentralisateurLine(
                    journal_code=r["journal_code"],
                    journal_name=r["journal_name"],
                    nb_ecritures=int(r["nb_ecritures"]),
                    total_debit=d,
                    total_credit=c,
                    is_balanced=(d == c),
                )
            )

        return JournalCentralisateurReport(
            header=make_header("Journal Centralisateur", start_date, end_date),
            lines=lines,
            total_ecritures=total_ecr,
            grand_total_debit=grand_d,
            grand_total_credit=grand_c,
            is_balanced=(grand_d == grand_c),
        )
