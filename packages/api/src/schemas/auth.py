"""
Schémas Pydantic v2 pour l'authentification
Conformes aux règles : Create ≠ Response ≠ Update
"""
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, ConfigDict


# ============================================================
# SCHÉMAS USER
# ============================================================

class UserBase(BaseModel):
    """Champs communs User."""
    email: EmailStr = Field(
        ...,
        description="Email unique de l'utilisateur",
        max_length=255
    )


class UserCreate(UserBase):
    """Création d'utilisateur."""
    password: str = Field(
        ...,
        description="Mot de passe en clair (sera hashé)",
        min_length=8,
        max_length=128
    )
    role: str = Field(
        default="client",
        description="Rôle RBAC",
        regex=r"^(admin|notaire|clerc|client)$"
    )

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )


class UserLogin(BaseModel):
    """Connexion utilisateur."""
    email: EmailStr = Field(
        ...,
        description="Email de connexion"
    )
    password: str = Field(
        ...,
        description="Mot de passe",
        min_length=1,
        max_length=128
    )
    totp_code: Optional[str] = Field(
        default=None,
        description="Code TOTP 2FA (6 chiffres)",
        regex=r"^\d{6}$"
    )

    model_config = ConfigDict(
        str_strip_whitespace=True
    )


class UserResponse(UserBase):
    """Réponse User publique (sans password_hash)."""
    id: UUID
    role: str
    is_active: bool
    is_verified: bool
    totp_enabled: bool
    failed_login_count: int
    locked_until: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )


class UserUpdate(BaseModel):
    """Mise à jour utilisateur."""
    email: Optional[EmailStr] = Field(
        default=None,
        max_length=255
    )
    role: Optional[str] = Field(
        default=None,
        regex=r"^(admin|notaire|clerc|client)$"
    )
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )


# ============================================================
# SCHÉMAS TOKENS JWT
# ============================================================

class TokenPair(BaseModel):
    """Paire de tokens JWT."""
    access_token: str = Field(
        ...,
        description="JWT access token (15 min)"
    )
    refresh_token: str = Field(
        ...,
        description="Refresh token UUID (7 jours)"
    )
    expires_in: int = Field(
        ...,
        description="Durée de vie access_token en secondes"
    )
    token_type: str = Field(
        default="bearer",
        description="Type de token"
    )

    model_config = ConfigDict(
        str_strip_whitespace=True
    )


class RefreshRequest(BaseModel):
    """Demande de rafraîchissement token."""
    refresh_token: str = Field(
        ...,
        description="Refresh token à renouveler",
        min_length=36,
        max_length=36
    )

    model_config = ConfigDict(
        str_strip_whitespace=True
    )


# ============================================================
# SCHÉMAS 2FA TOTP
# ============================================================

class TOTPSetupResponse(BaseModel):
    """Réponse setup 2FA."""
    secret: str = Field(
        ...,
        description="Secret TOTP base32"
    )
    qr_code_uri: str = Field(
        ...,
        description="URI pour QR code Google Authenticator"
    )
    backup_codes: list[str] = Field(
        ...,
        description="Codes de récupération à usage unique"
    )


class TOTPVerifyRequest(BaseModel):
    """Vérification code TOTP."""
    code: str = Field(
        ...,
        description="Code TOTP 6 chiffres",
        regex=r"^\d{6}$"
    )

    model_config = ConfigDict(
        str_strip_whitespace=True
    )


class TOTPEnableRequest(TOTPVerifyRequest):
    """Activation 2FA avec vérification."""
    pass


# ============================================================
# SCHÉMAS PASSWORD & SECURITY
# ============================================================

class PasswordChangeRequest(BaseModel):
    """Changement de mot de passe."""
    current_password: str = Field(
        ...,
        description="Mot de passe actuel",
        min_length=1
    )
    new_password: str = Field(
        ...,
        description="Nouveau mot de passe",
        min_length=8,
        max_length=128
    )
    new_password_confirm: str = Field(
        ...,
        description="Confirmation nouveau mot de passe"
    )

    model_config = ConfigDict(
        str_strip_whitespace=True
    )

    def validate_passwords_match(self) -> "PasswordChangeRequest":
        """Valider que les mots de passe correspondent."""
        if self.new_password != self.new_password_confirm:
            raise ValueError("Les mots de passe ne correspondent pas")
        return self


class PasswordResetRequest(BaseModel):
    """Demande de réinitialisation mot de passe."""
    email: EmailStr = Field(
        ...,
        description="Email du compte à réinitialiser"
    )


class PasswordResetConfirm(BaseModel):
    """Confirmation réinitialisation avec token."""
    token: str = Field(
        ...,
        description="Token de réinitialisation",
        min_length=32
    )
    new_password: str = Field(
        ...,
        description="Nouveau mot de passe",
        min_length=8,
        max_length=128
    )

    model_config = ConfigDict(
        str_strip_whitespace=True
    )


# ============================================================
# SCHÉMAS AUDIT LOG
# ============================================================

class AuditLogResponse(BaseModel):
    """Réponse log d'audit."""
    id: UUID
    user_id: Optional[UUID]
    action: str
    resource_type: Optional[str]
    resource_id: Optional[UUID]
    ip_address: Optional[str]
    details: Dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )


class AuditLogCreate(BaseModel):
    """Création log d'audit."""
    user_id: Optional[UUID] = None
    action: str = Field(
        ...,
        max_length=100,
        description="Action effectuée"
    )
    resource_type: Optional[str] = Field(
        default=None,
        max_length=50
    )
    resource_id: Optional[UUID] = None
    ip_address: Optional[str] = Field(
        default=None,
        max_length=45
    )
    details: Dict[str, Any] = Field(
        default_factory=dict,
        description="Contexte JSON"
    )

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )


# ============================================================
# SCHÉMAS DE RÉPONSE MÉTIER
# ============================================================

class LoginResponse(TokenPair):
    """Réponse complète login."""
    user: UserResponse = Field(
        ...,
        description="Informations utilisateur connecté"
    )
    requires_totp: bool = Field(
        default=False,
        description="Indique si 2FA requis"
    )


class SecurityStatus(BaseModel):
    """État de sécurité du compte."""
    totp_enabled: bool
    failed_login_count: int
    is_locked: bool
    locked_until: Optional[datetime]
    last_login: Optional[datetime]
    active_sessions: int = Field(
        description="Nombre de sessions actives"
    )

    model_config = ConfigDict(
        from_attributes=True
    )