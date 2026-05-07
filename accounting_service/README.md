# Microservice Comptabilité — Fine_CoreBanking

Service central de comptabilité en partie double. Il gère le plan de comptes,
les exercices fiscaux, les périodes comptables, les écritures et les rapports.

---

## Rôle

- Plan de comptes paramétrable (PCIMF microfinance / PCEC banque / Custom)
- Gestion des exercices fiscaux et périodes comptables
- Écritures comptables (créer, valider, extourner) avec règle de la partie double
- Journaux auxiliaires (Caisse, Banque, Crédits, Épargne, Interbancaire…)
- Lettrage de comptes tiers
- Rapports : balance générale, grand livre, bilan, compte de résultat
- Publication d'événements Kafka pour le service Reporting

---

## Stack technique

| Composant | Version | Rôle |
|-----------|---------|------|
| Python | 3.11 | Runtime |
| FastAPI | 0.111+ | Framework web async |
| SQLAlchemy | 2.0 | ORM async |
| Alembic | 1.13+ | Migrations de base de données |
| Pydantic v2 | 2.x | Validation des schémas |
| PostgreSQL | 16 | Base de données |
| Redis | 7 | Cache et sessions |
| Kafka | 7.6 (Confluent) | Événements inter-services |
| JWT (HS256) | — | Authentification et autorisation |

---

## Endpoints principaux

Base URL : `http://localhost:8000/api/v1`

### Plan de comptes

| Méthode | Endpoint | Rôle | Auth |
|---------|----------|------|------|
| POST | `/accounts/` | Créer un compte | ADMIN, ACCOUNTANT |
| GET | `/accounts/` | Lister (filtré, paginé) | Tous |
| GET | `/accounts/{id}` | Détail d'un compte | Tous |
| PATCH | `/accounts/{id}` | Modifier | ADMIN, ACCOUNTANT |
| DELETE | `/accounts/{id}` | Désactiver | ADMIN |
| GET | `/accounts/{id}/balance` | Solde sur période | Tous |
| GET | `/accounts/templates/list` | Templates disponibles | Tous |
| POST | `/accounts/templates/{id}/load` | Charger un template | ADMIN |
| POST | `/accounts/import/csv` | Import CSV | ADMIN, ACCOUNTANT |

### Exercices fiscaux

| Méthode | Endpoint | Rôle |
|---------|----------|------|
| POST | `/fiscal-years/` | Créer un exercice |
| GET | `/fiscal-years/` | Lister |
| POST | `/fiscal-years/{id}/close` | Clôturer |

### Écritures comptables

| Méthode | Endpoint | Rôle |
|---------|----------|------|
| POST | `/journal-entries/` | Créer (DRAFT) |
| GET | `/journal-entries/` | Lister (filtré, paginé) |
| GET | `/journal-entries/{id}` | Détail avec lignes |
| POST | `/journal-entries/{id}/post` | Valider (DRAFT → POSTED) |
| POST | `/journal-entries/{id}/reverse` | Extourner (POSTED → REVERSED) |
| POST | `/journal-entries/letter` | Lettrage de lignes |

### Journaux

| Méthode | Endpoint | Rôle |
|---------|----------|------|
| GET | `/journals/` | Lister les journaux actifs |

---

## Cycle de vie d'une écriture

```
DRAFT ──[POST]──► POSTED ──[REVERSE]──► REVERSED
                              └──── crée écriture miroir POSTED
```

---

## Variables d'environnement

| Variable | Requis | Description |
|----------|--------|-------------|
| `DATABASE_URL` | ✅ | `postgresql+asyncpg://postgres:postgres@postgres:5432/accounting_db` |
| `REDIS_URL` | ✅ | `redis://redis-accounting:6379/0` |
| `JWT_SECRET_KEY` | ✅ | Clé secrète HS256 (min 32 octets hex) |
| `KAFKA_BOOTSTRAP_SERVERS` | ✅ | `kafka:9093` |
| `KAFKA_TOPIC_CREDIT_EVENTS` | — | `credit.events` |
| `KAFKA_TOPIC_SAVINGS_EVENTS` | — | `savings.events` |
| `KAFKA_TOPIC_CASH_EVENTS` | — | `cash.events` |
| `KAFKA_TOPIC_ACCOUNTING_EVENTS` | — | `accounting.events` |
| `ENVIRONMENT` | — | `development` / `production` |
| `CORS_ALLOWED_ORIGINS` | — | `http://localhost:3000` |
| `DEFAULT_CURRENCY` | — | `XOF` |

---

## Lancer en standalone

### Avec Docker

```bash
cd accounting_service
docker build -t accounting-service .
docker run -p 8000:8000 \
  -e DATABASE_URL="postgresql+asyncpg://postgres:postgres@host.docker.internal:5432/accounting_db" \
  -e REDIS_URL="redis://host.docker.internal:6379/0" \
  -e JWT_SECRET_KEY="your-secret" \
  -e KAFKA_BOOTSTRAP_SERVERS="host.docker.internal:9092" \
  accounting-service
```

### Avec Poetry (développement)

```bash
cd accounting_service
poetry install

# Appliquer les migrations
poetry run alembic upgrade head

# Seed du plan de comptes (optionnel)
poetry run python scripts/seed_chart_of_accounts.py

# Lancer le serveur
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Swagger UI disponible sur : http://localhost:8000/docs

---

## Tests

```bash
cd accounting_service
poetry run pytest tests/ -v --cov=app --cov-report=term-missing
```

---

## Rôles et permissions

| Rôle | Description | Permissions |
|------|-------------|-------------|
| `ADMIN` | Administrateur | Toutes les opérations |
| `ACCOUNTANT` | Comptable | Créer/valider/extourner écritures |
| `AUDITOR` | Auditeur | Lecture seule |
| `SERVICE_CREDIT` | Service Crédit | Créer écritures (API) |
| `SERVICE_SAVINGS` | Service Épargne | Créer écritures (API) |
| `SERVICE_CASH` | Service Caisse | Créer écritures (API) |

---

## Architecture interne

```
accounting_service/
├── app/
│   ├── api/v1/
│   │   ├── accounts.py      # Plan de comptes + templates + import CSV
│   │   ├── journals.py      # Journaux + écritures comptables
│   │   ├── periods.py       # Exercices fiscaux + périodes
│   │   └── reports.py       # Balance, grand livre, bilan, résultat
│   ├── core/
│   │   ├── config.py        # Pydantic Settings
│   │   ├── exceptions.py    # Exceptions métier typées
│   │   └── security.py      # JWT RBAC
│   ├── data/
│   │   └── plan_templates.py # Définitions PCIMF / PCEC
│   ├── db/
│   │   └── session.py       # AsyncSession factory
│   ├── models/
│   │   └── accounting.py    # SQLAlchemy ORM (tous les modèles)
│   ├── repositories/
│   │   └── accounting.py    # Accès données (pattern Repository)
│   ├── schemas/
│   │   └── accounting.py    # Pydantic v2 (Create/Update/Response)
│   └── services/
│       └── accounting.py    # Logique métier (AccountService, JournalEntryService)
├── migrations/              # Alembic (0001 → 0005)
├── scripts/
│   └── seed_chart_of_accounts.py
└── tests/
    ├── conftest.py
    ├── unit/
    └── integration/
```
