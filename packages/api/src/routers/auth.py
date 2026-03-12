"""
Router d'authentification FastAPI
Conforme aux conventions et tests d'intégration
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis

from ..models.auth import User
from ..schemas.auth import (
    UserCreate, UserLogin, UserResponse, TokenPair,
    RefreshRequest, TOTPSetupResponse, TOTPVerifyRequest,
    LoginResponse, SecurityStatus
)
from ..services.auth_service import AuthService, create_auth_service
from ..middleware.auth_middleware import (
    get_current_user, require_authenticated, oauth2_scheme
)


# ============================================================
# CONFIGURATION ROUTER
# ============================================================

router = APIRouter(
    prefix="/auth",
    tags=["Authentification"],
    responses={
        401: {"description": "Non authentifié"},
        403: {"description": "Accès refusé"},
        422: {"description": "Données invalides"}
    }
)


# ============================================================
# DÉPENDANCES
# ============================================================

async def get_db():
    """Dépendance pour la session DB (sera override dans main.py)."""
    raise NotImplementedError("get_db doit être configuré dans main.py")


async def get_redis() -> redis.Redis:
    """Dépendance pour Redis (sera override dans main.py)."""
    raise NotImplementedError("get_redis doit être configuré dans main.py")


async def get_auth_service(
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
) -> AuthService:
    """
    Dépendance pour obtenir le service d'authentification.

    Args:
        db: Session de base de données
        redis_client: Client Redis

    Returns:
        AuthService: Service d'authentification configuré
    """
    return create_auth_service(db, redis_client=redis_client)


# ============================================================
# ENDPOINTS PUBLICS
# ============================================================

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Inscription d'un nouvel utilisateur",
    description="Crée un compte utilisateur avec email et mot de passe. L'email doit être vérifié avant connexion."
)
async def register(
    user_data: UserCreate,
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Inscription d'un nouvel utilisateur.

    Args:
        user_data: Données d'inscription (email, password, role)
        auth_service: Service d'authentification

    Returns:
        UserResponse: Utilisateur créé (sans password_hash)

    Raises:
        HTTPException 400: Données invalides
        HTTPException 409: Email déjà utilisé
    """
    try:
        return await auth_service.register(
            email=user_data.email,
            password=user_data.password,
            role=user_data.role
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'inscription: {str(e)}"
        )


@router.post(
    "/login",
    response_model=TokenPair,
    summary="Connexion utilisateur",
    description="Authentifie un utilisateur et retourne les tokens JWT."
)
async def login(
    login_data: UserLogin,
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Connexion d'un utilisateur.

    Args:
        login_data: Identifiants de connexion
        auth_service: Service d'authentification

    Returns:
        TokenPair: Access token + refresh token

    Raises:
        HTTPException 401: Identifiants invalides
        HTTPException 403: Compte non vérifié ou inactif
        HTTPException 423: Compte verrouillé
    """
    try:
        return await auth_service.login(
            email=login_data.email,
            password=login_data.password,
            totp_code=login_data.totp_code,
            ip_address="unknown",  # TODO: Extraire IP de la requête
            user_agent="unknown"   # TODO: Extraire User-Agent
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la connexion: {str(e)}"
        )


@router.post(
    "/refresh",
    response_model=TokenPair,
    summary="Rafraîchissement des tokens",
    description="Renouvelle les tokens avec rotation automatique."
)
async def refresh_tokens(
    refresh_data: RefreshRequest,
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Rafraîchit les tokens JWT.

    Args:
        refresh_data: Token de rafraîchissement
        auth_service: Service d'authentification

    Returns:
        TokenPair: Nouveaux tokens

    Raises:
        HTTPException 401: Token invalide ou expiré
    """
    try:
        return await auth_service.refresh(refresh_data.refresh_token)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du rafraîchissement: {str(e)}"
        )


# ============================================================
# ENDPOINTS AUTHENTIFIÉS
# ============================================================

@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Déconnexion utilisateur",
    description="Révoque le refresh token et invalide la session."
)
async def logout(
    refresh_data: RefreshRequest,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Déconnexion d'un utilisateur.

    Args:
        refresh_data: Token à révoquer
        current_user: Utilisateur authentifié
        auth_service: Service d'authentification

    Returns:
        dict: Message de confirmation
    """
    try:
        await auth_service.logout(refresh_data.refresh_token)
        return {"message": "Déconnexion réussie"}
    except Exception as e:
        # Le logout ne doit pas échouer même si le token n'existe pas
        return {"message": "Déconnexion réussie"}


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Profil utilisateur actuel",
    description="Récupère les informations du profil de l'utilisateur connecté."
)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    """
    Profil de l'utilisateur authentifié.

    Args:
        current_user: Utilisateur authentifié

    Returns:
        UserResponse: Profil utilisateur (sans password_hash)
    """
    return UserResponse.model_validate(current_user)


@router.get(
    "/me/security",
    response_model=SecurityStatus,
    summary="État de sécurité du compte",
    description="Informations de sécurité : 2FA, tentatives de connexion, etc."
)
async def get_security_status(
    current_user: User = Depends(get_current_user)
):
    """
    État de sécurité du compte utilisateur.

    Args:
        current_user: Utilisateur authentifié

    Returns:
        SecurityStatus: État de sécurité
    """
    return SecurityStatus(
        totp_enabled=current_user.totp_enabled,
        failed_login_count=current_user.failed_login_count,
        is_locked=current_user.locked_until is not None and current_user.locked_until > datetime.utcnow(),
        locked_until=current_user.locked_until,
        last_login=None,  # TODO: Implémenter tracking dernière connexion
        active_sessions=0  # TODO: Compter les sessions actives
    )


# ============================================================
# ENDPOINTS 2FA
# ============================================================

@router.post(
    "/2fa/setup",
    response_model=TOTPSetupResponse,
    summary="Configuration 2FA TOTP",
    description="Configure l'authentification à deux facteurs avec Google Authenticator."
)
async def setup_2fa(
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Configuration de la 2FA TOTP.

    Args:
        current_user: Utilisateur authentifié
        auth_service: Service d'authentification

    Returns:
        TOTPSetupResponse: Secret, QR code URI et codes de récupération

    Raises:
        HTTPException 404: Utilisateur non trouvé
    """
    try:
        setup_data = await auth_service.setup_2fa(current_user.id)
        return TOTPSetupResponse(
            secret=setup_data["secret"],
            qr_code_uri=setup_data["qr_code_uri"],
            backup_codes=setup_data["backup_codes"]
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la configuration 2FA: {str(e)}"
        )


@router.post(
    "/2fa/verify",
    summary="Vérification code TOTP",
    description="Vérifie un code TOTP généré par l'application d'authentification."
)
async def verify_2fa_code(
    verify_data: TOTPVerifyRequest,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Vérification d'un code TOTP.

    Args:
        verify_data: Code TOTP à vérifier
        current_user: Utilisateur authentifié
        auth_service: Service d'authentification

    Returns:
        dict: Résultat de la vérification

    Raises:
        HTTPException 404: 2FA non configurée
    """
    try:
        is_valid = await auth_service.verify_2fa(current_user.id, verify_data.code)
        return {
            "valid": is_valid,
            "message": "Code valide" if is_valid else "Code invalide"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la vérification 2FA: {str(e)}"
        )


@router.delete(
    "/2fa/disable",
    summary="Désactiver 2FA",
    description="Désactive l'authentification à deux facteurs pour le compte."
)
async def disable_2fa(
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Désactivation de la 2FA.

    Args:
        current_user: Utilisateur authentifié
        auth_service: Service d'authentification

    Returns:
        dict: Message de confirmation
    """
    # TODO: Implémenter la désactivation 2FA dans AuthService
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Fonctionnalité non encore implémentée"
    )


# ============================================================
# ENDPOINTS DE GESTION DES TOKENS
# ============================================================

@router.post(
    "/tokens/revoke",
    summary="Révoquer un token JWT",
    description="Révoque un token JWT spécifique (blacklist)."
)
async def revoke_token(
    credentials: HTTPAuthorizationCredentials = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    redis_client: redis.Redis = Depends(get_redis)
):
    """
    Révocation d'un token JWT.

    Args:
        credentials: Token à révoquer
        current_user: Utilisateur authentifié
        redis_client: Client Redis

    Returns:
        dict: Message de confirmation
    """
    try:
        import jwt
        from ..middleware.auth_middleware import JWT_SECRET, revoke_jwt_token

        # Décoder le token pour récupérer le JTI
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        jti = payload.get("jti")

        if jti:
            await revoke_jwt_token(jti, redis_client, ttl_seconds=3600)

        return {"message": "Token révoqué avec succès"}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erreur lors de la révocation: {str(e)}"
        )


@router.get(
    "/tokens/info",
    summary="Informations sur le token actuel",
    description="Récupère les informations du token JWT utilisé."
)
async def get_token_info(
    credentials: HTTPAuthorizationCredentials = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user)
):
    """
    Informations sur le token actuel.

    Args:
        credentials: Token JWT
        current_user: Utilisateur authentifié

    Returns:
        dict: Informations du token
    """
    try:
        import jwt
        from ..middleware.auth_middleware import JWT_SECRET

        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])

        return {
            "user_id": payload.get("sub"),
            "role": payload.get("role"),
            "issued_at": datetime.fromtimestamp(payload.get("iat", 0)),
            "expires_at": datetime.fromtimestamp(payload.get("exp", 0)),
            "jti": payload.get("jti")
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erreur lors de la lecture du token: {str(e)}"
        )


# ============================================================
# ENDPOINTS DE DÉVELOPPEMENT (OPTIONNELS)
# ============================================================

@router.get(
    "/health",
    summary="Statut du service d'authentification",
    description="Vérifie la santé du service d'auth (DB + Redis).",
    tags=["Développement"]
)
async def auth_health_check(
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Vérification de santé du service d'authentification.

    Args:
        auth_service: Service d'authentification

    Returns:
        dict: État des services
    """
    try:
        # Test de connexion DB
        from sqlalchemy import text
        await auth_service.db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {str(e)}"

    try:
        # Test de connexion Redis
        await auth_service.redis.ping()
        redis_status = "ok"
    except Exception as e:
        redis_status = f"error: {str(e)}"

    return {
        "service": "auth",
        "status": "ok" if db_status == "ok" and redis_status == "ok" else "degraded",
        "database": db_status,
        "redis": redis_status,
        "timestamp": datetime.utcnow()
    }