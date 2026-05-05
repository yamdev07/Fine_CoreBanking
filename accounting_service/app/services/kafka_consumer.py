"""
Consommateur Kafka — Traitement des événements inter-microservices.

Ce module écoute les topics des autres microservices et génère
automatiquement les écritures comptables correspondantes.

Exemples d'événements traités :
  - credit.events : CREDIT_DISBURSED, CREDIT_REPAYMENT, CREDIT_WRITEOFF
  - savings.events : SAVINGS_DEPOSIT, SAVINGS_WITHDRAWAL, INTEREST_CREDITED
  - cash.events    : CASH_DEPOSIT, CASH_WITHDRAWAL, CASH_TRANSFER
"""
import json
import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Any

from aiokafka import AIOKafkaConsumer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import AsyncSessionFactory
from app.repositories.accounting import AccountRepository, JournalRepository
from app.schemas.accounting import JournalEntryCreate, JournalLineCreate
from app.services.accounting import JournalEntryService

logger = logging.getLogger(__name__)

# Mapping strict topic → service autorisé.
# Un message sur credit.events provenant d'un autre service est rejeté.
TOPIC_ALLOWED_SOURCES: dict[str, str] = {
    settings.KAFKA_TOPIC_CREDIT_EVENTS:  "credit-service",
    settings.KAFKA_TOPIC_SAVINGS_EVENTS: "savings-service",
    settings.KAFKA_TOPIC_CASH_EVENTS:    "cash-service",
}


class EventType(StrEnum):
    # Crédits
    CREDIT_DISBURSED = "CREDIT_DISBURSED"
    CREDIT_REPAYMENT = "CREDIT_REPAYMENT"
    CREDIT_WRITEOFF = "CREDIT_WRITEOFF"
    CREDIT_INTEREST_ACCRUAL = "CREDIT_INTEREST_ACCRUAL"
    CREDIT_PENALTY_APPLIED = "CREDIT_PENALTY_APPLIED"

    # Épargne
    SAVINGS_DEPOSIT = "SAVINGS_DEPOSIT"
    SAVINGS_WITHDRAWAL = "SAVINGS_WITHDRAWAL"
    SAVINGS_INTEREST_CREDITED = "SAVINGS_INTEREST_CREDITED"

    # Caisse
    CASH_DEPOSIT = "CASH_DEPOSIT"
    CASH_WITHDRAWAL = "CASH_WITHDRAWAL"
    CASH_TRANSFER = "CASH_TRANSFER"


@dataclass
class AccountingEvent:
    event_id: str
    event_type: EventType
    source_service: str
    occurred_at: str
    payload: dict[str, Any]


class AccountingRules:
    """
    Règles de comptabilisation par type d'événement.

    Chaque règle retourne une liste de (compte_code, sens, montant).
    Les comptes doivent exister dans le plan de comptes.

    Convention SYSCOHADA adapté aux IMF/banques BCEAO :
      411xxx = Clients (débiteurs)
      251xxx = Crédits accordés
      401xxx = Fournisseurs
      521xxx = Banques
      571xxx = Caisse
      701xxx = Produits financiers (intérêts)
      663xxx = Charges d'intérêts sur dépôts
      371xxx = Dépôts de la clientèle (épargne)
      781xxx = Reprises sur provisions
      694xxx = Dotations aux provisions
    """

    @staticmethod
    def credit_disbursed(payload: dict) -> list[tuple[str, str, Decimal]]:
        """
        Décaissement d'un crédit :
          Débit  : 251100 Crédits à court terme — montant décaissé
          Crédit : 571100 Caisse principale
        """
        amount = Decimal(str(payload["amount"]))
        return [
            ("251100", "debit", amount),
            ("571100", "credit", amount),
        ]

    @staticmethod
    def credit_repayment(payload: dict) -> list[tuple[str, str, Decimal]]:
        """
        Remboursement d'une échéance :
          - Capital
          - Intérêts
          - Pénalités de retard éventuelles
        """
        principal = Decimal(str(payload.get("principal", 0)))
        interest = Decimal(str(payload.get("interest", 0)))
        penalty = Decimal(str(payload.get("penalty", 0)))
        movements = []

        if principal > 0:
            movements += [
                ("571100", "debit", principal),
                ("251100", "credit", principal),
            ]
        if interest > 0:
            movements += [
                ("571100", "debit", interest),
                ("701100", "credit", interest),
            ]
        if penalty > 0:
            movements += [
                ("571100", "debit", penalty),
                ("701900", "credit", penalty),
            ]
        return movements

    @staticmethod
    def credit_writeoff(payload: dict) -> list[tuple[str, str, Decimal]]:
        """
        Passage en perte d'un crédit :
          Débit  : 694100 Dotation aux provisions
          Crédit : 251100 Crédits accordés
        """
        amount = Decimal(str(payload["amount"]))
        return [
            ("694100", "debit", amount),
            ("251100", "credit", amount),
        ]

    @staticmethod
    def savings_deposit(payload: dict) -> list[tuple[str, str, Decimal]]:
        """
        Dépôt d'épargne :
          Débit  : 571100 Caisse
          Crédit : 371100 Dépôts à vue
        """
        amount = Decimal(str(payload["amount"]))
        return [
            ("571100", "debit", amount),
            ("371100", "credit", amount),
        ]

    @staticmethod
    def savings_withdrawal(payload: dict) -> list[tuple[str, str, Decimal]]:
        """
        Retrait d'épargne :
          Débit  : 371100 Dépôts à vue
          Crédit : 571100 Caisse
        """
        amount = Decimal(str(payload["amount"]))
        return [
            ("371100", "debit", amount),
            ("571100", "credit", amount),
        ]

    @staticmethod
    def savings_interest_credited(payload: dict) -> list[tuple[str, str, Decimal]]:
        """
        Capitalisation des intérêts sur épargne :
          Débit  : 663100 Charges d'intérêts sur dépôts
          Crédit : 371100 Dépôts à vue
        """
        amount = Decimal(str(payload["amount"]))
        return [
            ("663100", "debit", amount),
            ("371100", "credit", amount),
        ]

    @staticmethod
    def cash_deposit(payload: dict) -> list[tuple[str, str, Decimal]]:
        amount = Decimal(str(payload["amount"]))
        return [
            ("571100", "debit", amount),
            ("411100", "credit", amount),
        ]

    @staticmethod
    def cash_withdrawal(payload: dict) -> list[tuple[str, str, Decimal]]:
        amount = Decimal(str(payload["amount"]))
        return [
            ("411100", "debit", amount),
            ("571100", "credit", amount),
        ]

    RULE_MAP = {
        EventType.CREDIT_DISBURSED: credit_disbursed.__func__,
        EventType.CREDIT_REPAYMENT: credit_repayment.__func__,
        EventType.CREDIT_WRITEOFF: credit_writeoff.__func__,
        EventType.SAVINGS_DEPOSIT: savings_deposit.__func__,
        EventType.SAVINGS_WITHDRAWAL: savings_withdrawal.__func__,
        EventType.SAVINGS_INTEREST_CREDITED: savings_interest_credited.__func__,
        EventType.CASH_DEPOSIT: cash_deposit.__func__,
        EventType.CASH_WITHDRAWAL: cash_withdrawal.__func__,
    }

    @classmethod
    def get_movements(
        cls, event_type: EventType, payload: dict
    ) -> list[tuple[str, str, Decimal]]:
        rule = cls.RULE_MAP.get(event_type)
        if not rule:
            raise ValueError(f"Aucune règle de comptabilisation pour {event_type}")
        return rule(payload)


async def process_event(event: AccountingEvent, session: AsyncSession) -> None:
    """
    Traite un événement et génère l'écriture comptable correspondante.
    Idempotent : si l'événement a déjà été traité, on ignore silencieusement.
    """
    try:
        movements = AccountingRules.get_movements(event.event_type, event.payload)
    except ValueError as e:
        logger.warning("Événement ignoré — règle manquante: %s", e)
        return

    account_repo = AccountRepository(session)
    lines = []

    for code, sens, amount in movements:
        account = await account_repo.get_by_code(code)
        if not account:
            raise ValueError(
                f"Compte {code} introuvable dans le plan — événement {event.event_id} rejeté."
            )
        if not account.is_active:
            raise ValueError(
                f"Compte {code} inactif — événement {event.event_id} rejeté."
            )

        lines.append(
            JournalLineCreate(
                account_id=account.id,
                debit_amount=amount if sens == "debit" else Decimal("0"),
                credit_amount=amount if sens == "credit" else Decimal("0"),
                description=event.payload.get("description"),
                third_party_id=event.payload.get("client_id"),
                third_party_type="CLIENT",
            )
        )

    # Trouver le journal selon le service source
    journal_map = {
        "credit-service": "CR",
        "savings-service": "EP",
        "cash-service": "CJ",
    }
    journal_code = journal_map.get(event.source_service, "OD")

    journal_repo = JournalRepository(session)
    journal = await journal_repo.get_by_code(journal_code)

    entry_date = date.fromisoformat(event.payload.get("date", date.today().isoformat()))

    entry_data = JournalEntryCreate(
        journal_id=journal.id,
        entry_date=entry_date,
        description=f"{event.event_type} — {event.payload.get('reference', event.event_id)}",
        reference=event.payload.get("reference"),
        lines=lines,
    )

    svc = JournalEntryService(session)
    entry = await svc.create_entry(
        entry_data,
        created_by="kafka-consumer",
        source_service=event.source_service,
        source_event_id=event.event_id,
    )

    # Auto-valider les écritures issues d'événements (elles sont déjà contrôlées)
    await svc.post_entry(entry.id, posted_by="kafka-consumer")
    logger.info(
        "Écriture %s générée depuis l'événement %s/%s",
        entry.entry_number, event.source_service, event.event_id,
    )


async def run_consumer() -> None:
    """Démarre le consommateur Kafka en boucle infinie."""
    consumer = AIOKafkaConsumer(
        settings.KAFKA_TOPIC_CREDIT_EVENTS,
        settings.KAFKA_TOPIC_SAVINGS_EVENTS,
        settings.KAFKA_TOPIC_CASH_EVENTS,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id=settings.KAFKA_CONSUMER_GROUP,
        auto_offset_reset="earliest",
        enable_auto_commit=False,  # Commit manuel après traitement
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
    )

    await consumer.start()
    logger.info("Kafka consumer démarré — en attente d'événements...")

    try:
        async for msg in consumer:
            raw = msg.value
            try:
                # Zero Trust : vérifier que la source déclarée correspond au topic.
                # Le champ source_service du payload ne suffit pas —
                # on le confirme via le topic de provenance.
                topic = msg.topic
                declared_source = raw.get("source_service", "")
                expected_source = TOPIC_ALLOWED_SOURCES.get(topic, "")
                if declared_source != expected_source:
                    logger.warning(
                        "Kafka source mismatch — topic=%s déclaré=%s attendu=%s — message rejeté",
                        topic, declared_source, expected_source,
                    )
                    # Ne pas commiter : message potentiellement forgé, laisser en queue
                    continue

                event = AccountingEvent(
                    event_id=raw["event_id"],
                    event_type=EventType(raw["event_type"]),
                    source_service=expected_source,   # source fiable (topic), pas le payload
                    occurred_at=raw["occurred_at"],
                    payload=raw.get("payload", {}),
                )

                async with AsyncSessionFactory() as session:
                    async with session.begin():
                        await process_event(event, session)

                await consumer.commit()

            except Exception as exc:
                logger.exception(
                    "Erreur traitement événement %s: %s",
                    raw.get("event_id", "?"), exc
                )
                # On continue pour ne pas bloquer la file — Dead Letter Queue à implémenter
    finally:
        await consumer.stop()
