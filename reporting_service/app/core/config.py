"""
Configuration du microservice Reporting.
Se connecte à la base de données comptabilité en LECTURE SEULE.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    APP_NAME: str = "reporting-service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"

    # Connexion en lecture seule sur la DB comptabilité
    # En production : utiliser un user PostgreSQL avec GRANT SELECT uniquement
    ACCOUNTING_DB_URL: str = (
        "postgresql+asyncpg://reporting_ro:reporting_ro@localhost:5432/accounting_db"
    )
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_ECHO: bool = False

    # Redis — cache des rapports lourds (balance, bilan)
    REDIS_URL: str = "redis://localhost:6379/1"
    CACHE_TTL_SECONDS: int = 300  # 5 minutes par défaut
    CACHE_TTL_ANNUAL_REPORT: int = 3600  # 1h pour les rapports annuels

    # Sécurité JWT (partagée avec l'API Gateway)
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"

    # CORS
    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]

    # Monnaie
    DEFAULT_CURRENCY: str = "XOF"
    INSTITUTION_NAME: str = "Institution de Microfinance"
    INSTITUTION_COUNTRY: str = "BJ"  # Bénin

    # Pagination
    DEFAULT_PAGE_SIZE: int = 50
    MAX_PAGE_SIZE: int = 1000

    # OpenTelemetry
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://jaeger:4317"
    OTEL_ENABLED: bool = False

    # Kafka — écoute les événements de l'accounting pour invalider le cache
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_TOPIC_ACCOUNTING_EVENTS: str = "accounting.events"

    # Formats export
    EXPORT_PDF_LOGO_PATH: str = "assets/logo.png"
    EXPORT_AUTHOR: str = "Système Core Banking"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
