# Microservice Reporting — Fine_CoreBanking

Service de génération des rapports financiers et états réglementaires BCEAO.
Il fonctionne en **lecture seule** sur la base de données comptable.

---

## Rôle

- Génère les états financiers (bilan, compte de résultat, balance, grand livre)
- Produit les états réglementaires BCEAO/UEMOA (ratios prudentiels)
- Met en cache les résultats dans Redis pour les rapports coûteux
- Se connecte à PostgreSQL avec l'utilisateur `reporting_ro` (lecture seule)

---

## Stack technique

| Composant | Version | Rôle |
|-----------|---------|------|
| Python | 3.11 | Runtime |
| FastAPI | 0.111+ | Framework web async |
| SQLAlchemy | 2.0 | ORM async (lecture seule) |
| Pydantic v2 | 2.x | Validation des schémas |
| Redis | 7 | Cache des rapports |
| Uvicorn | 0.29+ | Serveur ASGI |

---

## Endpoints principaux

Base URL : `http://localhost:8001/api/v1`

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/reports/trial-balance` | Balance générale des comptes |
| GET | `/reports/general-ledger` | Grand livre (mouvements par compte) |
| GET | `/reports/balance-sheet` | Bilan actif/passif |
| GET | `/reports/income-statement` | Compte de résultat |
| GET | `/reports/cash-flow` | Tableau des flux de trésorerie |
| GET | `/reports/credit-portfolio` | Portefeuille crédits |
| GET | `/reports/deposits` | Dépôts et épargne |
| GET | `/reports/dashboard` | KPIs du tableau de bord |
| GET | `/reports/bceao-prudential` | Ratios prudentiels BCEAO |
| GET | `/reports/journal-centralizer` | Journal centralisateur |
| GET | `/reports/fiscal-years` | Exercices fiscaux |
| GET | `/health` | Healthcheck |

### Paramètres communs

La plupart des endpoints acceptent :

```
start_date=YYYY-MM-DD   # Date de début (obligatoire)
end_date=YYYY-MM-DD     # Date de fin (obligatoire)
period_id=<uuid>        # Filtre par période comptable
currency=XOF            # Devise (défaut: XOF)
```

### Exemple

```bash
curl "http://localhost:8001/api/v1/reports/trial-balance?start_date=2025-01-01&end_date=2025-12-31" \
  -H "Authorization: Bearer <token>"
```

---

## Variables d'environnement

| Variable | Requis | Défaut | Description |
|----------|--------|--------|-------------|
| `DATABASE_URL` | ✅ | — | `postgresql+asyncpg://reporting_ro:reporting_ro@postgres:5432/accounting_db` |
| `REDIS_URL` | ✅ | — | `redis://redis-reporting:6380/0` |
| `JWT_SECRET_KEY` | ✅ | — | Clé secrète partagée avec accounting-service |
| `ENVIRONMENT` | — | `development` | `development` / `production` |
| `CORS_ALLOWED_ORIGINS` | — | `http://localhost:3000` | Origines CORS autorisées |
| `INSTITUTION_NAME` | — | `Ma Banque` | Nom affiché dans les rapports |
| `INSTITUTION_COUNTRY` | — | `BJ` | Code pays ISO |
| `CACHE_TTL_SECONDS` | — | `300` | Durée de vie du cache Redis (secondes) |

---

## Lancer en standalone

### Avec Docker

```bash
cd reporting_service
docker build -t reporting-service .
docker run -p 8001:8001 \
  -e DATABASE_URL="postgresql+asyncpg://reporting_ro:reporting_ro@host.docker.internal:5432/accounting_db" \
  -e REDIS_URL="redis://host.docker.internal:6379/0" \
  -e JWT_SECRET_KEY="your-secret" \
  reporting-service
```

### Avec Poetry (développement)

```bash
cd reporting_service
poetry install
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

Swagger UI disponible sur : http://localhost:8001/docs

---

## Tests

```bash
cd reporting_service
poetry run pytest tests/ -v --cov=app --cov-report=term-missing
```

---

## Architecture interne

```
reporting_service/
├── app/
│   ├── api/v1/
│   │   └── reports.py      # Tous les endpoints de rapport
│   ├── core/
│   │   ├── config.py       # Paramètres (Pydantic Settings)
│   │   └── security.py     # Validation JWT
│   ├── db/
│   │   └── session.py      # Session async SQLAlchemy
│   ├── models/             # Modèles ORM (miroir accounting)
│   ├── schemas/            # Schémas de réponse Pydantic
│   └── services/           # Logique de génération des rapports
├── tests/
│   ├── unit/               # Tests unitaires (mock DB/Redis)
│   └── integration/        # Tests d'intégration API
└── Dockerfile
```
