"""
Modèle AuditLog — trace immuable de toutes les mutations de l'API.
"""
import enum
import uuid

from sqlalchemy import DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.accounting import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=_new_uuid
    )
    timestamp: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # Qui
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_role: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Quoi
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    status_code: Mapped[int] = mapped_column(nullable=False)

    # Contexte
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)

    # Payload résumé (tronqué à 2 000 chars pour éviter les blobs)
    request_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_audit_logs_user_timestamp", "user_id", "timestamp"),
        Index("ix_audit_logs_path_method", "path", "method"),
    )
