# Microservice Comptabilité — Core Banking

## Architecture

```
accounting_service/
├── app/
│   ├── api/v1/             # Endpoints REST (FastAPI)
│   │   ├── accounts.py     # Plan de comptes
│   │   ├── journals.py     # Journaux comptables
│   │   ├── ledger.py       # Grand livre
│   │   ├── periods.py      # Périodes comptables
│   │   └── reports.py      # Rapports (Balance, Bilan, Résultat)
│   ├── core/               # Config, sécurité, exceptions
│   ├── db/                 # Session, base, init
│   ├── models/             # Modèles SQLAlchemy (ORM)
│   ├── schemas/            # Pydantic (validation I/O)
│   ├── services/           # Logique métier
│   ├── repositories/       # Accès données (pattern Repository)
│   └── utils/              # Helpers (date, montants, ...)
├── migrations/             # Alembic
├── tests/
└── docker-compose.yml
```

## Stack technique
- **Framework**: FastAPI + Uvicorn
- **ORM**: SQLAlchemy 2.0 (async)
- **DB**: PostgreSQL
- **Validation**: Pydantic v2
- **Migrations**: Alembic
- **Auth**: JWT (via API Gateway)
- **Messaging**: Apache Kafka (événements inter-microservices)
- **Tests**: Pytest + pytest-asyncio

## Concepts comptables implémentés
- Plan de comptes (PCG) avec classes 1-9
- Partie double obligatoire (Débit = Crédit)
- Journaux : Général, Caisse, Banque, Opérations diverses
- Exercices et périodes comptables
- Lettrage des écritures
- Balance générale, Grand livre, Bilan, Compte de résultat
- Écritures générées automatiquement depuis les événements (crédits, épargne, caisse)
