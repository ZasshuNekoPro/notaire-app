"""
Middleware d'authentification et autorisation RBAC
Conforme aux conventions FastAPI et tests d'intégration
"""
import os
from typing import List, Optional, Set
from datetime import datetime
from uuid import UUID

import jwt
import redis.asyncio as redis
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.auth import User
from ..services.auth_service import AuthService


# ============================================================
# CONFIGURATION SÉCURITÉ
# ============================================================

# Schéma Bearer Token
oauth2_scheme = HTTPBearer(
    scheme_name="JWT",
    description="Token JWT d'authentification",
    auto_error=False  # Gestion manuelle des erreurs
)

# Configuration JWT
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = "HS256"

if not JWT_SECRET:
    raise ValueError("JWT_SECRET doit être défini dans les variables d'environnement")

if len(JWT_SECRET) < 32:
    raise ValueError("JWT_SECRET doit contenir au moins 32 caractères")


# ============================================================
# DÉPENDANCES DE BASE
# ============================================================

async def get_redis() -> redis.Redis:
    """
    Dépendance pour obtenir le client Redis.

    Returns:
        redis.Redis: Client Redis configuré
    """
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    client = redis.from_url(redis_url, decode_responses=True)
    try:
        yield client
    finally:
        await client.close()


# Cette dépendance sera injectée depuis main.py
async def get_db():
    """Dépendance pour la session de base de données."""
    # Cette fonction sera override dans main.py avec la vraie session
    raise NotImplementedError("get_db doit être configuré dans main.py")


# ============================================================
# VALIDATION JWT
# ============================================================

async def verify_jwt_token(
    token: str,
    redis_client: redis.Redis
) -> dict:
    """
    Vérifie et décode un token JWT.

    Args:
        token: Token JWT à vérifier
        redis_client: Client Redis pour vérifier révocation

    Returns:
        dict: Payload du JWT décodé

    Raises:
        HTTPException: Si le token est invalide, expiré ou révoqué
    """
    try:
        # Décoder le JWT
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

        # Vérifier les champs obligatoires
        required_fields = ["sub", "role", "exp", "jti"]
        for field in required_fields:
            if field not in payload:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Token invalide: champ {field} manquant",
                    headers={"WWW-Authenticate": "Bearer"}
                )

        # Vérifier que le JTI n'est pas révoqué dans Redis
        jti = payload["jti"]
        is_revoked = await redis_client.exists(f"revoked_jwt:{jti}")

        if is_revoked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token révoqué",
                headers={"WWW-Authenticate": "Bearer"}
            )

        # Vérifier l'expiration (déjà fait par jwt.decode mais double check)
        exp_timestamp = payload["exp"]
        if datetime.utcnow().timestamp() > exp_timestamp:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expiré",
                headers={"WWW-Authenticate": "Bearer"}
            )

        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expiré",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except jwt.JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token invalide: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Erreur de validation du token",
            headers={"WWW-Authenticate": "Bearer"}
        )


# ============================================================
# GET CURRENT USER
# ============================================================

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
) -> User:
    """
    Récupère l'utilisateur authentifié actuel.

    Args:
        credentials: Credentials HTTP Bearer
        db: Session de base de données
        redis_client: Client Redis

    Returns:
        User: Utilisateur authentifié

    Raises:
        HTTPException 401: Si l'authentification échoue
    """
    # Vérifier la présence du token
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token d'authentification manquant",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Valider le JWT
    payload = await verify_jwt_token(credentials.credentials, redis_client)

    # Extraire l'ID utilisateur
    try:
        user_id = UUID(payload["sub"])
    except (ValueError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide: ID utilisateur manquant ou invalide",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Récupérer l'utilisateur en base
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur non trouvé",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Vérifier que l'utilisateur est actif
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Compte utilisateur désactivé",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Vérifier la cohérence du rôle
    if user.role != payload.get("role"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide: rôle incohérent",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
) -> Optional[User]:
    """
    Récupère l'utilisateur authentifié actuel (optionnel).

    Returns:
        Optional[User]: Utilisateur authentifié ou None si pas authentifié
    """
    try:
        return await get_current_user(credentials, db, redis_client)
    except HTTPException:
        return None


# ============================================================
# RBAC - CONTRÔLE D'ACCÈS
# ============================================================

def require_role(*allowed_roles: str):
    """
    Factory pour créer une dépendance de validation de rôle.

    Args:
        *allowed_roles: Rôles autorisés (admin, notaire, clerc, client)

    Returns:
        Callable: Dépendance FastAPI pour validation RBAC

    Example:
        @router.get("/admin-only", dependencies=[Depends(require_role("admin"))])
        async def admin_endpoint():
            return {"message": "Admin access granted"}
    """
    allowed_roles_set: Set[str] = set(allowed_roles)

    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        """
        Vérifie que l'utilisateur a le rôle requis.

        Args:
            current_user: Utilisateur authentifié

        Returns:
            User: Utilisateur avec le bon rôle

        Raises:
            HTTPException 403: Si le rôle est insuffisant
        """
        if current_user.role not in allowed_roles_set:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Autorisation insuffisante. Rôles requis: {', '.join(allowed_roles)}"
            )

        return current_user

    return role_checker


def require_admin():
    """Dépendance pour les endpoints admin uniquement."""
    return require_role("admin")


def require_notaire_or_admin():
    """Dépendance pour les endpoints notaire/admin."""
    return require_role("notaire", "admin")


def require_staff():
    """Dépendance pour le personnel (admin, notaire, clerc)."""
    return require_role("admin", "notaire", "clerc")


def require_authenticated():
    """Dépendance pour vérifier uniquement l'authentification (tout rôle)."""
    return require_role("admin", "notaire", "clerc", "client")


# ============================================================
# UTILITAIRES RBAC
# ============================================================

class RBACPermissions:
    """
    Matrice des permissions RBAC selon le domaine métier notarial.

    Conforme à la skill auth-securite.
    """

    PERMISSIONS = {
        "admin": {
            "users": ["read", "write", "delete"],
            "dossiers": ["read_all", "write_all"],
            "estimations": ["read", "write"],
            "succession": ["read", "write"],
            "documents": ["read", "write", "delete"],
            "alertes": ["read", "write"],
            "admin_panel": ["access"]
        },
        "notaire": {
            "users": [],
            "dossiers": ["read_own", "write_own"],
            "estimations": ["read", "write"],
            "succession": ["read", "write"],
            "documents": ["read", "write"],
            "alertes": ["read", "write"],
            "admin_panel": []
        },
        "clerc": {
            "users": [],
            "dossiers": ["read_assigned", "write_assigned"],
            "estimations": ["read", "write"],
            "succession": [],
            "documents": ["read", "write"],
            "alertes": ["read"],
            "admin_panel": []
        },
        "client": {
            "users": [],
            "dossiers": ["read_own"],
            "estimations": [],
            "succession": [],
            "documents": ["read_own"],
            "alertes": [],
            "admin_panel": []
        }
    }

    @classmethod
    def has_permission(cls, role: str, resource: str, action: str) -> bool:
        """
        Vérifie si un rôle a une permission spécifique.

        Args:
            role: Rôle de l'utilisateur
            resource: Ressource (users, dossiers, etc.)
            action: Action (read, write, etc.)

        Returns:
            bool: True si autorisé
        """
        user_permissions = cls.PERMISSIONS.get(role, {})
        resource_permissions = user_permissions.get(resource, [])
        return action in resource_permissions

    @classmethod
    def can_access_user_data(cls, user_role: str, target_user_id: UUID, current_user_id: UUID) -> bool:
        """
        Vérifie si un utilisateur peut accéder aux données d'un autre.

        Args:
            user_role: Rôle de l'utilisateur qui demande l'accès
            target_user_id: ID de l'utilisateur cible
            current_user_id: ID de l'utilisateur connecté

        Returns:
            bool: True si l'accès est autorisé
        """
        # Admin peut tout voir
        if user_role == "admin":
            return True

        # Utilisateur peut voir ses propres données
        if target_user_id == current_user_id:
            return True

        # Autres cas interdits
        return False


def require_permission(resource: str, action: str):
    """
    Factory pour créer une dépendance de validation de permission.

    Args:
        resource: Ressource à vérifier
        action: Action à vérifier

    Returns:
        Callable: Dépendance FastAPI pour validation de permission
    """
    async def permission_checker(current_user: User = Depends(get_current_user)) -> User:
        """Vérifie la permission spécifique."""
        if not RBACPermissions.has_permission(current_user.role, resource, action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission refusée: {action} sur {resource}"
            )

        return current_user

    return permission_checker


# ============================================================
# RÉVOCATION DE TOKENS
# ============================================================

async def revoke_jwt_token(
    jti: str,
    redis_client: redis.Redis,
    ttl_seconds: int = 3600  # 1 heure par défaut
):
    """
    Révoque un token JWT en l'ajoutant à la blacklist Redis.

    Args:
        jti: JWT ID à révoquer
        redis_client: Client Redis
        ttl_seconds: Durée de vie de la blacklist
    """
    await redis_client.setex(f"revoked_jwt:{jti}", ttl_seconds, "1")


async def is_jwt_revoked(jti: str, redis_client: redis.Redis) -> bool:
    """
    Vérifie si un JWT est révoqué.

    Args:
        jti: JWT ID à vérifier
        redis_client: Client Redis

    Returns:
        bool: True si révoqué
    """
    return bool(await redis_client.exists(f"revoked_jwt:{jti}"))


# ============================================================
# MIDDLEWARES OPTIONNELS
# ============================================================

async def log_user_activity(
    current_user: User = Depends(get_current_user_optional)
):
    """
    Middleware optionnel pour logger l'activité utilisateur.

    Args:
        current_user: Utilisateur connecté (optionnel)
    """
    if current_user:
        # Ici on pourrait logger l'activité dans AuditLog
        # Pour l'instant, on fait juste passer
        pass

    return current_user