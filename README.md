# Fine_CoreBanking

[![CI](https://github.com/yamdev07/core-banking/actions/workflows/ci.yml/badge.svg)](https://github.com/yamdev07/core-banking/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11](https://img.shields.io/badge/Python-3.11-blue)](https://www.python.org/)
[![Next.js 14](https://img.shields.io/badge/Next.js-14-black)](https://nextjs.org/)

Système de **core banking** conçu pour les institutions financières de la zone **UEMOA/BCEAO** (monnaie XOF). Architecture microservices avec comptabilité en partie double, reporting réglementaire et interface web moderne.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                         UTILISATEURS                                 │
│          Comptable · Admin · Auditeur · Services internes            │
└───────────────────────────┬──────────────────────────────────────────┘
                            │ HTTPS :3000
                            ▼
               ┌────────────────────────┐
               │   Frontend Next.js 14  │  :3000
               │   (App Router, TS,     │
               │    Tailwind CSS)       │
               └─────────┬──────────────┘
                         │ REST API
          ┌──────────────┴────────────────┐
          │                               │
          ▼ :8000                         ▼ :8001
┌─────────────────────┐       ┌───────────────────────┐
│  accounting-service │       │   reporting-service   │
│  FastAPI / Python   │       │   FastAPI / Python    │
│  SQLAlchemy async   │       │   Jinja2 + Redis      │
│  Alembic            │       │   (lecture seule)     │
└──────────┬──────────┘       └──────────┬────────────┘
           │                             │
           │         Kafka Events        │
           │  ┌──────────────────────┐   │
           └─►│  Apache Kafka :9092  │◄──┘
              │  Zookeeper :2181     │
              └──────────────────────┘
           │                             │
           └──────────┬──────────────────┘
                      ▼
          ┌───────────────────────────┐
          │  PostgreSQL 16  :5432     │
          │  accounting_db            │
          │  ┌─────────────────────┐  │
          │  │  reporting_ro (RO)  │  │
          │  └─────────────────────┘  │
          └───────────────────────────┘
          ┌───────────────────────────┐
          │  Redis 7  :6379           │
          │  (cache reporting)        │
          └───────────────────────────┘
```

---

## Services

| Service | Port | Rôle |
|---------|------|------|
| `frontend` | **3000** | Interface web Next.js |
| `accounting-service` | **8000** | Comptabilité, plan de comptes, écritures |
| `reporting-service` | **8001** | Rapports financiers (bilan, résultat, BCEAO) |
| `postgres` | **5432** | Base de données principale |
| `redis-accounting` | **6379** | Cache Redis (accounting) |
| `kafka` | **9092** | Broker d'événements inter-services |
| `kafka-ui` | **8080** | Interface Kafka (dev) |

---

## Topics Kafka

| Topic | Producteur | Consommateur | Rôle |
|-------|-----------|--------------|------|
| `credit.events` | Service Crédit | accounting-service | Déblocages et remboursements de prêts |
| `savings.events` | Service Épargne | accounting-service | Dépôts et retraits d'épargne |
| `cash.events` | Service Caisse | accounting-service | Opérations de caisse |
| `accounting.events` | accounting-service | reporting-service | Notification après validation d'écriture |

L'idempotence est garantie via `source_event_id` — un même événement ne génère jamais deux écritures.

---

## Plan comptable

Le système supporte deux référentiels BCEAO/UEMOA sélectionnables à l'initialisation :

| Template | Cible | Classes |
|----------|-------|---------|
| **PCIMF** | IMF, coopératives, mutuelles | 1-Capitaux · 2-Immobilisations · 3-Interbancaire · 4-Membres/Clientèle · 5-Trésorerie · 6-Charges · 7-Produits |
| **PCEC** | Banques commerciales agréées | 1-Trésorerie/Interbancaire · 2-Clientèle · 3-Titres · 4-Immobilisations · 5-Fonds propres · 6-Charges · 7-Produits |
| **Custom** | Libre | Aucun compte pré-chargé |

Règles fondamentales :
- **Partie double** : ΣDébit = ΣCrédit obligatoire
- **Intangibilité** : écriture validée (POSTED) → immuable
- **Extourne** : seule façon de corriger une écriture validée

---

## Démarrage rapide

### Prérequis

- Docker Desktop ≥ 24
- Docker Compose v2

### Variables d'environnement

```bash
cp .env.example .env
# Éditez .env — changez au minimum JWT_SECRET_KEY
```

### Lancer tous les services

```bash
docker compose up -d
```

### Vérifier que tout tourne

```bash
docker compose ps
# Tous les services doivent être healthy
```

### Initialiser le plan comptable (première fois)

```
# Depuis l'interface : http://localhost:3000
# Administration > Plan comptable > Choisir PCIMF ou PCEC > Charger
```

---

## URLs de développement

| Service | URL | Description |
|---------|-----|-------------|
| Frontend | http://localhost:3000 | Interface utilisateur |
| Accounting API | http://localhost:8000/docs | Swagger UI |
| Accounting Health | http://localhost:8000/health | Healthcheck |
| Reporting API | http://localhost:8001/docs | Swagger UI |
| Reporting Health | http://localhost:8001/health | Healthcheck |
| Kafka UI | http://localhost:8080 | Monitoring Kafka |

**Identifiants de test (dev uniquement)**

```
Email    : admin@bank.local
Password : Admin1234!
```

---

## Variables d'environnement

| Variable | Service | Requis | Description |
|----------|---------|--------|-------------|
| `JWT_SECRET_KEY` | accounting | ✅ | Clé secrète JWT (min 32 octets hex) |
| `DATABASE_URL` | accounting, reporting | ✅ | URL PostgreSQL asyncpg |
| `REDIS_URL` | accounting | ✅ | URL Redis |
| `KAFKA_BOOTSTRAP_SERVERS` | accounting | ✅ | Adresse Kafka |
| `CORS_ALLOWED_ORIGINS` | accounting, reporting | ✅ | Origines CORS autorisées |
| `ENVIRONMENT` | tous | ✅ | `development` / `production` |
| `INSTITUTION_NAME` | reporting | — | Nom de l'institution (rapports) |
| `INSTITUTION_COUNTRY` | reporting | — | Code pays ISO (ex: `BJ`) |
| `DEFAULT_CURRENCY` | accounting | — | Monnaie par défaut (défaut: `XOF`) |

---

## Développement

### Lancer les tests

```bash
# Accounting service
cd accounting_service && poetry run pytest tests/ -v --cov=app

# Reporting service
cd reporting_service && poetry run pytest tests/ -v --cov=app
```

### Lint

```bash
cd accounting_service && poetry run ruff check app/ tests/
cd reporting_service && poetry run ruff check app/ tests/
```

### Reconstruire les images

```bash
docker compose build --no-cache
```

### Reset complet (dev)

```bash
bash scripts/reset_dev.sh
```

---

## Structure du projet

```
Fine_CoreBanking/
├── accounting_service/      # Microservice comptabilité (FastAPI)
│   ├── app/
│   │   ├── api/v1/          # Endpoints REST
│   │   ├── core/            # Sécurité, exceptions
│   │   ├── data/            # Templates plan comptable
│   │   ├── db/              # Session SQLAlchemy
│   │   ├── models/          # Modèles ORM
│   │   ├── repositories/    # Accès données
│   │   ├── schemas/         # Pydantic v2
│   │   └── services/        # Logique métier
│   ├── migrations/          # Alembic
│   ├── scripts/             # Seed, utilitaires
│   └── tests/               # pytest (unit + integration)
├── reporting_service/       # Microservice reporting (FastAPI)
│   ├── app/                 # Même structure
│   └── tests/
├── frontend/                # Application Next.js 14
│   ├── app/                 # App Router
│   ├── components/          # Composants réutilisables
│   └── lib/                 # Utilitaires, API client
├── scripts/                 # Scripts d'administration
│   ├── init_db.sql          # Création user reporting_ro
│   └── reset_dev.sh         # Reset environnement dev
├── .env.example             # Template variables d'environnement
├── docker-compose.yml       # Orchestration complète
├── Makefile                 # Commandes dev courantes
└── .github/workflows/ci.yml # Pipeline CI/CD
```

---

## Roadmap

- [ ] Module Crédits (origination, remboursement, impayés)
- [ ] Module Épargne (dépôts, retraits, calcul intérêts)
- [ ] Module Caisse (opérations espèces, réconciliation)
- [ ] Reporting BCEAO automatisé (états financiers réglementaires)
- [ ] Authentification multi-facteurs (TOTP)
- [ ] Notifications temps réel (WebSocket)
- [ ] Application mobile (React Native)
- [ ] Déploiement Kubernetes (Helm charts)

---

## Licence

MIT — voir [LICENSE](LICENSE)
