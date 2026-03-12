"""
Service d'authentification sécurisé
Conforme aux tests TDD et règles de sécurité absolues
"""
import os
import json
import hashlib
import secrets
from datetime import datetime, timedelta
from uuid import uuid4, UUID
from typing import Optional, Dict, Any

import bcrypt
import jwt
import pyotp
import redis.asyncio as redis
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from ..models.auth import User, RefreshToken, AuditLog
from ..schemas.auth import UserResponse, TokenPair


class AuthService:
    """
    Service d'authentification avec sécurité renforcée.

    Fonctionnalités :
    - Inscription avec bcrypt rounds=12
    - Login avec protection brute-force
    - JWT + refresh tokens avec rotation
    - 2FA TOTP (Google Authenticator)
    - Audit log RGPD
    - Révocation Redis
    """

    def __init__(
        self,
        db: AsyncSession,
        redis: redis.Redis,
        jwt_secret: str,
        jwt_expire_minutes: int = 15,
        refresh_expire_days: int = 7
    ):
        self.db = db
        self.redis = redis
        self.jwt_secret = jwt_secret
        self.jwt_expire_minutes = jwt_expire_minutes
        self.refresh_expire_days = refresh_expire_days

        # Constantes de sécurité
        self.BCRYPT_ROUNDS = 12
        self.MAX_LOGIN_ATTEMPTS = 5
        self.LOCKOUT_DURATION_MINUTES = 30
        self.VALID_ROLES = {"admin", "notaire", "clerc", "client"}

    # ============================================================
    # REGISTRATION
    # ============================================================

    async def register(self, email: str, password: str, role: str = "client") -> UserResponse:
        """
        Enregistre un nouvel utilisateur.

        Args:
            email: Email unique de l'utilisateur
            password: Mot de passe en clair (sera hashé bcrypt rounds=12)
            role: Rôle RBAC (admin/notaire/clerc/client)

        Returns:
            UserResponse: Données utilisateur (sans password_hash)

        Raises:
            HTTPException 400: Données invalides
            HTTPException 409: Email déjà utilisé
        """
        # Validation des entrées
        await self._validate_registration_data(email, password, role)

        # Vérifier unicité email
        await self._check_email_availability(email)

        # Hash du mot de passe avec bcrypt rounds=12
        password_hash = self._hash_password(password)

        # Créer l'utilisateur
        user = User(
            email=email.lower().strip(),
            password_hash=password_hash,
            role=role,
            is_verified=False,  # Email non vérifié par défaut
            is_active=True
        )

        try:
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)

            # Audit log
            await self._create_audit_log(
                action="USER_REGISTER",
                user_id=user.id,
                resource_type="user",
                resource_id=user.id,
                details={"email": email, "role": role}
            )

            return UserResponse.model_validate(user)

        except IntegrityError:
            await self.db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Cette adresse email est déjà utilisée"
            )

    async def _validate_registration_data(self, email: str, password: str, role: str):
        """Valide les données d'inscription."""
        # Validation mot de passe
        if len(password) < 8:
            raise HTTPException(
                status_code=400,
                detail="Le mot de passe doit contenir au moins 8 caractères"
            )

        if len(password) > 128:
            raise HTTPException(
                status_code=400,
                detail="Le mot de passe est trop long (maximum 128 caractères)"
            )

        # Validation rôle
        if role not in self.VALID_ROLES:
            raise HTTPException(
                status_code=400,
                detail=f"Rôle invalide. Valeurs autorisées : {', '.join(self.VALID_ROLES)}"
            )

    async def _check_email_availability(self, email: str):
        """Vérifie que l'email n'est pas déjà utilisé."""
        result = await self.db.execute(
            select(User).where(User.email == email.lower().strip())
        )
        existing_user = result.scalar_one_or_none()

        if existing_user:
            raise HTTPException(
                status_code=409,
                detail="Cette adresse email est déjà utilisée"
            )

    def _hash_password(self, password: str) -> str:
        """Hash le mot de passe avec bcrypt rounds=12."""
        salt = bcrypt.gensalt(rounds=self.BCRYPT_ROUNDS)
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')

    # ============================================================
    # LOGIN
    # ============================================================

    async def login(
        self,
        email: str,
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> TokenPair:
        """
        Authentifie un utilisateur et génère les tokens.

        Args:
            email: Email de connexion
            password: Mot de passe en clair
            ip_address: Adresse IP du client
            user_agent: User agent du navigateur

        Returns:
            TokenPair: Access token JWT + refresh token

        Raises:
            HTTPException 401: Identifiants invalides
            HTTPException 403: Email non vérifié
            HTTPException 423: Compte verrouillé
        """
        # Récupérer l'utilisateur
        user = await self._get_user_by_email(email)

        if not user:
            await self._log_failed_login(email, ip_address, "USER_NOT_FOUND")
            raise HTTPException(
                status_code=401,
                detail="Identifiants invalides"
            )

        # Vérifier si le compte est verrouillé
        await self._check_account_lockout(user)

        # Vérifier si l'email est vérifié
        if not user.is_verified:
            raise HTTPException(
                status_code=403,
                detail="Veuillez vérifier votre adresse email avant de vous connecter"
            )

        # Vérifier si le compte est actif
        if not user.is_active:
            raise HTTPException(
                status_code=403,
                detail="Ce compte est désactivé"
            )

        # Vérifier le mot de passe
        if not self._verify_password(password, user.password_hash):
            await self._handle_failed_login(user, ip_address, user_agent)
            raise HTTPException(
                status_code=401,
                detail="Identifiants invalides"
            )

        # Connexion réussie - reset des tentatives échouées
        await self._reset_failed_logins(user)

        # Générer les tokens
        access_token = self._generate_jwt(user.id, user.role)
        refresh_token = await self._create_refresh_token(user.id, ip_address, user_agent)

        # Audit log succès
        await self._create_audit_log(
            action="LOGIN_SUCCESS",
            user_id=user.id,
            ip_address=ip_address,
            details={
                "user_agent": user_agent,
                "role": user.role
            }
        )

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self.jwt_expire_minutes * 60,
            token_type="bearer"
        )

    async def _get_user_by_email(self, email: str) -> Optional[User]:
        """Récupère un utilisateur par email."""
        result = await self.db.execute(
            select(User).where(User.email == email.lower().strip())
        )
        return result.scalar_one_or_none()

    async def _check_account_lockout(self, user: User):
        """Vérifie si le compte est verrouillé."""
        if (user.locked_until and
            user.locked_until > datetime.utcnow()):

            remaining_minutes = int((user.locked_until - datetime.utcnow()).total_seconds() / 60)
            raise HTTPException(
                status_code=423,
                detail=f"Compte verrouillé. Réessayez dans {remaining_minutes} minutes."
            )

    def _verify_password(self, password: str, hashed: str) -> bool:
        """Vérifie un mot de passe contre son hash bcrypt."""
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
        except Exception:
            return False

    async def _handle_failed_login(self, user: User, ip_address: str, user_agent: str):
        """Gère une tentative de connexion échouée."""
        user.failed_login_count += 1

        # Verrouillage après 5 tentatives
        if user.failed_login_count >= self.MAX_LOGIN_ATTEMPTS:
            user.locked_until = datetime.utcnow() + timedelta(minutes=self.LOCKOUT_DURATION_MINUTES)

        await self.db.commit()

        # Audit log échec
        await self._create_audit_log(
            action="LOGIN_FAILED",
            user_id=user.id,
            ip_address=ip_address,
            details={
                "user_agent": user_agent,
                "failed_attempts": user.failed_login_count,
                "locked": user.locked_until is not None
            }
        )

    async def _reset_failed_logins(self, user: User):
        """Remet à zéro les tentatives échouées."""
        user.failed_login_count = 0
        user.locked_until = None
        await self.db.commit()

    async def _log_failed_login(self, email: str, ip_address: str, reason: str):
        """Log une tentative de connexion échouée (user inexistant)."""
        await self._create_audit_log(
            action="LOGIN_FAILED",
            user_id=None,
            ip_address=ip_address,
            details={
                "email": email,
                "reason": reason
            }
        )

    # ============================================================
    # JWT TOKENS
    # ============================================================

    def _generate_jwt(self, user_id: UUID, role: str) -> str:
        """Génère un JWT access token."""
        now = datetime.utcnow()
        payload = {
            "sub": str(user_id),
            "role": role,
            "exp": now + timedelta(minutes=self.jwt_expire_minutes),
            "iat": now,
            "jti": str(uuid4())  # JWT ID unique pour révocation
        }

        return jwt.encode(payload, self.jwt_secret, algorithm="HS256")

    async def _create_refresh_token(
        self,
        user_id: UUID,
        ip_address: str = None,
        user_agent: str = None
    ) -> str:
        """Crée un refresh token et le stocke dans Redis."""
        refresh_token = str(uuid4())
        token_hash = self._hash_token(refresh_token)

        # Métadonnées du token
        token_data = {
            "user_id": str(user_id),
            "created_at": datetime.utcnow().isoformat(),
            "ip_address": ip_address,
            "user_agent": user_agent
        }

        # Stocker dans Redis avec TTL
        ttl_seconds = self.refresh_expire_days * 24 * 3600
        await self.redis.setex(
            f"refresh_token:{token_hash}",
            ttl_seconds,
            json.dumps(token_data)
        )

        return refresh_token

    def _hash_token(self, token: str) -> str:
        """Hash un token avec SHA256."""
        return hashlib.sha256(token.encode('utf-8')).hexdigest()

    # ============================================================
    # REFRESH TOKENS
    # ============================================================

    async def refresh(self, refresh_token: str) -> TokenPair:
        """
        Rafraîchit les tokens avec rotation.

        Args:
            refresh_token: Token de rafraîchissement

        Returns:
            TokenPair: Nouveaux tokens

        Raises:
            HTTPException 401: Token invalide ou expiré
        """
        token_hash = self._hash_token(refresh_token)

        # Récupérer les données du token depuis Redis
        token_data = await self.redis.get(f"refresh_token:{token_hash}")

        if not token_data:
            raise HTTPException(
                status_code=401,
                detail="Token de rafraîchissement invalide ou expiré"
            )

        try:
            data = json.loads(token_data)
            user_id = UUID(data["user_id"])
        except (json.JSONDecodeError, KeyError, ValueError):
            raise HTTPException(
                status_code=401,
                detail="Token de rafraîchissement corrompu"
            )

        # Vérifier que l'utilisateur existe toujours
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user or not user.is_active:
            raise HTTPException(
                status_code=401,
                detail="Utilisateur invalide"
            )

        # Rotation : révoquer l'ancien token
        await self.redis.delete(f"refresh_token:{token_hash}")

        # Générer nouveaux tokens
        new_access_token = self._generate_jwt(user.id, user.role)
        new_refresh_token = await self._create_refresh_token(
            user.id,
            data.get("ip_address"),
            data.get("user_agent")
        )

        # Audit log
        await self._create_audit_log(
            action="TOKEN_REFRESH",
            user_id=user.id,
            details={"rotated": True}
        )

        return TokenPair(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            expires_in=self.jwt_expire_minutes * 60,
            token_type="bearer"
        )

    # ============================================================
    # LOGOUT
    # ============================================================

    async def logout(self, refresh_token: str):
        """
        Déconnecte un utilisateur en révoquant le refresh token.

        Args:
            refresh_token: Token à révoquer
        """
        token_hash = self._hash_token(refresh_token)

        # Récupérer les données avant suppression pour l'audit
        token_data = await self.redis.get(f"refresh_token:{token_hash}")

        # Supprimer le token de Redis (pas d'erreur si inexistant)
        await self.redis.delete(f"refresh_token:{token_hash}")

        # Audit log si le token existait
        if token_data:
            try:
                data = json.loads(token_data)
                user_id = UUID(data["user_id"])

                await self._create_audit_log(
                    action="LOGOUT",
                    user_id=user_id,
                    details={"token_revoked": True}
                )
            except (json.JSONDecodeError, KeyError, ValueError):
                pass  # Ignore les erreurs de parsing pour le logout

    # ============================================================
    # 2FA TOTP
    # ============================================================

    async def setup_2fa(self, user_id: UUID) -> Dict[str, Any]:
        """
        Configure la 2FA TOTP pour un utilisateur.

        Args:
            user_id: ID de l'utilisateur

        Returns:
            Dict avec secret, qr_code_uri et backup_codes

        Raises:
            HTTPException 404: Utilisateur non trouvé
        """
        # Récupérer l'utilisateur
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

        # Générer un secret TOTP
        secret = pyotp.random_base32()

        # Créer l'instance TOTP
        totp = pyotp.TOTP(secret)

        # Générer l'URI pour le QR code
        qr_code_uri = totp.provisioning_uri(
            name=user.email,
            issuer_name="Notaire App"
        )

        # Générer des codes de récupération
        backup_codes = [secrets.token_hex(4).upper() for _ in range(8)]

        # Sauvegarder en base
        user.totp_secret = secret
        user.totp_enabled = True
        await self.db.commit()

        # Audit log
        await self._create_audit_log(
            action="2FA_SETUP",
            user_id=user.id,
            details={"method": "totp"}
        )

        return {
            "secret": secret,
            "qr_code_uri": qr_code_uri,
            "backup_codes": backup_codes
        }

    async def verify_2fa(self, user_id: UUID, code: str) -> bool:
        """
        Vérifie un code TOTP.

        Args:
            user_id: ID de l'utilisateur
            code: Code TOTP à vérifier

        Returns:
            bool: True si le code est valide

        Raises:
            HTTPException 404: Utilisateur non trouvé ou 2FA non configurée
        """
        # Récupérer l'utilisateur
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user or not user.totp_enabled or not user.totp_secret:
            raise HTTPException(
                status_code=404,
                detail="2FA non configurée pour cet utilisateur"
            )

        # Vérifier le code avec fenêtre de tolérance ±30s (window=1)
        totp = pyotp.TOTP(user.totp_secret)
        is_valid = totp.verify(code, valid_window=1)

        # Audit log
        await self._create_audit_log(
            action="2FA_VERIFY",
            user_id=user.id,
            details={"success": is_valid}
        )

        return is_valid

    # ============================================================
    # AUDIT LOGGING
    # ============================================================

    async def _create_audit_log(
        self,
        action: str,
        user_id: Optional[UUID] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Crée une entrée d'audit log."""
        audit_log = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            details=details or {}
        )

        self.db.add(audit_log)

        # Commit asynchrone pour ne pas bloquer
        try:
            await self.db.commit()
        except Exception:
            # En cas d'erreur, rollback mais ne pas faire échouer l'opération principale
            await self.db.rollback()


# ============================================================
# FACTORY FUNCTION
# ============================================================

def create_auth_service(
    db: AsyncSession,
    redis_url: str = None,
    jwt_secret: str = None
) -> AuthService:
    """
    Factory pour créer une instance d'AuthService.

    Args:
        db: Session de base de données
        redis_url: URL de connexion Redis
        jwt_secret: Clé secrète JWT

    Returns:
        AuthService: Instance configurée
    """
    # Configuration par défaut depuis les variables d'environnement
    redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
    jwt_secret = jwt_secret or os.getenv("JWT_SECRET")

    if not jwt_secret:
        raise ValueError("JWT_SECRET doit être défini dans les variables d'environnement")

    if len(jwt_secret) < 32:
        raise ValueError("JWT_SECRET doit contenir au moins 32 caractères")

    # Créer le client Redis
    redis_client = redis.from_url(redis_url, decode_responses=True)

    return AuthService(
        db=db,
        redis=redis_client,
        jwt_secret=jwt_secret,
        jwt_expire_minutes=int(os.getenv("JWT_EXPIRE_MINUTES", "15")),
        refresh_expire_days=int(os.getenv("JWT_REFRESH_EXPIRE_DAYS", "7"))
    )