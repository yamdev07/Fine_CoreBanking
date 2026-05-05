"""
Configuration centrale du microservice comptabilité.
Chargée depuis les variables d'environnement (12-Factor App).
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Application
    APP_NAME: str = "accounting-service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"  # development | staging | production

    # Base de données PostgreSQL (async)
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/accounting_db"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_ECHO: bool = False

    # Redis (cache + verrous distribués)
    REDIS_URL: str = "redis://localhost:6379/0"

    # Kafka (événements inter-microservices)
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_CONSUMER_GROUP: str = "accounting-service"
    KAFKA_TOPIC_CREDIT_EVENTS: str = "credit.events"
    KAFKA_TOPIC_SAVINGS_EVENTS: str = "savings.events"
    KAFKA_TOPIC_CASH_EVENTS: str = "cash.events"
    KAFKA_TOPIC_ACCOUNTING_EVENTS: str = "accounting.events"

    # Sécurité JWT (validé par l'API Gateway)
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    # CORS (comma-separated list of allowed origins)
    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]

    # Rate limiting
    RATE_LIMIT_LOGIN: str = "10/minute"

    # Monnaie par défaut
    DEFAULT_CURRENCY: str = "XOF"  # Franc CFA BCEAO
    DEFAULT_DECIMAL_PLACES: int = 0  # XOF n'a pas de centimes

    # Exercice fiscal
    FISCAL_YEAR_START_MONTH: int = 1  # Janvier

    # Pagination
    DEFAULT_PAGE_SIZE: int = 50
    MAX_PAGE_SIZE: int = 500


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
