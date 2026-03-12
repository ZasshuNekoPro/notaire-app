"""
Modèles d'authentification et sécurité
Conformes aux tests dans test_auth_models.py
"""
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID

from sqlalchemy import (
    Boolean, String, Integer, DateTime, Text, CheckConstraint,
    ForeignKey, Index
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, BaseModel


class User(BaseModel, Base):
    """
    Modèle utilisateur avec authentification sécurisée.

    Rôles : admin, notaire, clerc, client
    Protection brute-force avec failed_login_count et locked_until
    Support 2FA TOTP avec totp_secret et totp_enabled
    """
    __tablename__ = "users"

    # Identité
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Bcrypt hash avec rounds=12 minimum"
    )

    # RBAC
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="client",
        comment="admin|notaire|clerc|client"
    )

    # États du compte
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )

    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Email vérifié"
    )

    # Protection brute-force
    failed_login_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    locked_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Compte verrouillé jusqu'à cette date"
    )

    # 2FA TOTP
    totp_secret: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Secret TOTP base32 pour Google Authenticator"
    )

    totp_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )

    # Relations
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="user",
        lazy="select"
    )

    # Contraintes
    __table_args__ = (
        CheckConstraint(
            "role IN ('admin', 'notaire', 'clerc', 'client')",
            name="check_user_role"
        ),
        Index("idx_users_email", "email"),
        Index("idx_users_role", "role"),
        Index("idx_users_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<User {self.email} role={self.role} active={self.is_active}>"


class RefreshToken(Base):
    """
    Token de rafraîchissement JWT.

    Stocké hashé (SHA256) dans Redis pour révocation instantanée.
    Rotation automatique : révoquer l'ancien, émettre nouveau.
    """
    __tablename__ = "refresh_tokens"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=lambda: __import__("uuid").uuid4()
    )

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    token_hash: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        comment="SHA256 du token original"
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Expiration (7 jours par défaut)"
    )

    revoked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )

    # Métadonnées de sécurité
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
        comment="IPv4 ou IPv6"
    )

    user_agent: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=__import__("sqlalchemy").func.now(),
        nullable=False
    )

    # Relations
    user: Mapped["User"] = relationship(
        "User",
        back_populates="refresh_tokens"
    )

    # Index
    __table_args__ = (
        Index("idx_refresh_tokens_user_id", "user_id"),
        Index("idx_refresh_tokens_expires", "expires_at"),
        Index("idx_refresh_tokens_hash", "token_hash"),
    )

    def __repr__(self) -> str:
        status = "revoked" if self.revoked else "active"
        return f"<RefreshToken user_id={self.user_id} status={status}>"


class AuditLog(Base):
    """
    Journal d'audit pour traçabilité RGPD.

    Logs toutes les actions sensibles :
    - LOGIN, LOGOUT, LOGIN_FAILED
    - USER_CREATE, USER_UPDATE, USER_DELETE
    - DOSSIER_ACCESS, DOCUMENT_DOWNLOAD
    - SYSTEM_* pour actions automatiques
    """
    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=lambda: __import__("uuid").uuid4()
    )

    # Association optionnelle à un user
    user_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="NULL pour les actions système"
    )

    # Action effectuée
    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="LOGIN, USER_UPDATE, DOSSIER_ACCESS, etc."
    )

    # Ressource affectée
    resource_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="user, dossier, document, etc."
    )

    resource_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        comment="ID de la ressource"
    )

    # Context réseau
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True
    )

    # Détails JSON flexibles
    details: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Contexte et métadonnées JSON"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=__import__("sqlalchemy").func.now(),
        nullable=False,
        index=True
    )

    # Relations
    user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="audit_logs"
    )

    # Index pour recherche et performance
    __table_args__ = (
        Index("idx_audit_logs_user_action", "user_id", "action"),
        Index("idx_audit_logs_resource", "resource_type", "resource_id"),
        Index("idx_audit_logs_created", "created_at"),
        Index("idx_audit_logs_ip", "ip_address"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} user_id={self.user_id} at={self.created_at}>"