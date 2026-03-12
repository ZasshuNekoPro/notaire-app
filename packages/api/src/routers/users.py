"""
Router de gestion des utilisateurs (admin uniquement)
Conforme aux conventions FastAPI et RBAC
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from ..models.auth import User, AuditLog
from ..schemas.auth import UserResponse, UserUpdate, AuditLogResponse
from ..middleware.auth_middleware import (
    require_admin, get_current_user, RBACPermissions
)


# ============================================================
# CONFIGURATION ROUTER
# ============================================================

router = APIRouter(
    prefix="/users",
    tags=["Gestion des utilisateurs"],
    dependencies=[Depends(require_admin())],  # Admin uniquement pour tous les endpoints
    responses={
        401: {"description": "Non authentifié"},
        403: {"description": "Accès refusé - Admin requis"},
        404: {"description": "Utilisateur non trouvé"},
        422: {"description": "Données invalides"}
    }
)


# ============================================================
# SCHÉMAS SPÉCIFIQUES
# ============================================================

class PaginatedUsers(BaseModel):
    """Réponse paginée pour la liste des utilisateurs."""
    items: List[UserResponse]
    total: int
    page: int
    limit: int
    pages: int


class UserStats(BaseModel):
    """Statistiques globales des utilisateurs."""
    total_users: int
    active_users: int
    verified_users: int
    by_role: dict[str, int]
    recent_signups: int


class UserSearchFilters(BaseModel):
    """Filtres de recherche pour les utilisateurs."""
    search: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None


# ============================================================
# DÉPENDANCES
# ============================================================

async def get_db():
    """Dépendance pour la session DB (sera override dans main.py)."""
    raise NotImplementedError("get_db doit être configuré dans main.py")


# ============================================================
# ENDPOINTS CRUD UTILISATEURS
# ============================================================

@router.get(
    "/",
    response_model=PaginatedUsers,
    summary="Liste des utilisateurs avec pagination",
    description="Récupère la liste paginée de tous les utilisateurs du système."
)
async def list_users(
    page: int = Query(1, ge=1, description="Numéro de page"),
    limit: int = Query(20, ge=1, le=100, description="Nombre d'éléments par page"),
    search: Optional[str] = Query(None, description="Recherche par email ou nom"),
    role: Optional[str] = Query(None, description="Filtrer par rôle"),
    is_active: Optional[bool] = Query(None, description="Filtrer par statut actif"),
    is_verified: Optional[bool] = Query(None, description="Filtrer par statut vérifié"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Liste paginée des utilisateurs avec filtres.

    Args:
        page: Numéro de page (1-based)
        limit: Nombre d'éléments par page
        search: Terme de recherche (email)
        role: Filtrer par rôle
        is_active: Filtrer par statut actif
        is_verified: Filtrer par statut vérifié
        db: Session de base de données
        current_user: Admin authentifié

    Returns:
        PaginatedUsers: Liste paginée avec métadonnées
    """
    try:
        # Construire la requête de base
        query = select(User)

        # Appliquer les filtres
        if search:
            query = query.where(User.email.ilike(f"%{search}%"))

        if role:
            query = query.where(User.role == role)

        if is_active is not None:
            query = query.where(User.is_active == is_active)

        if is_verified is not None:
            query = query.where(User.is_verified == is_verified)

        # Compter le total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()

        # Appliquer la pagination
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit).order_by(desc(User.created_at))

        # Exécuter la requête
        result = await db.execute(query)
        users = result.scalars().all()

        # Calculer le nombre de pages
        pages = (total + limit - 1) // limit

        return PaginatedUsers(
            items=[UserResponse.model_validate(user) for user in users],
            total=total,
            page=page,
            limit=limit,
            pages=pages
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des utilisateurs: {str(e)}"
        )


@router.get(
    "/stats",
    response_model=UserStats,
    summary="Statistiques des utilisateurs",
    description="Récupère les statistiques globales des utilisateurs du système."
)
async def get_users_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Statistiques globales des utilisateurs.

    Args:
        db: Session de base de données
        current_user: Admin authentifié

    Returns:
        UserStats: Statistiques agrégées
    """
    try:
        # Requêtes de statistiques
        total_result = await db.execute(select(func.count(User.id)))
        total_users = total_result.scalar()

        active_result = await db.execute(select(func.count(User.id)).where(User.is_active == True))
        active_users = active_result.scalar()

        verified_result = await db.execute(select(func.count(User.id)).where(User.is_verified == True))
        verified_users = verified_result.scalar()

        # Statistiques par rôle
        role_stats_result = await db.execute(
            select(User.role, func.count(User.id))
            .group_by(User.role)
        )
        by_role = {role: count for role, count in role_stats_result.fetchall()}

        # Inscriptions récentes (7 derniers jours)
        from datetime import datetime, timedelta
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_result = await db.execute(
            select(func.count(User.id)).where(User.created_at >= week_ago)
        )
        recent_signups = recent_result.scalar()

        return UserStats(
            total_users=total_users,
            active_users=active_users,
            verified_users=verified_users,
            by_role=by_role,
            recent_signups=recent_signups
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du calcul des statistiques: {str(e)}"
        )


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Détails d'un utilisateur",
    description="Récupère les informations complètes d'un utilisateur spécifique."
)
async def get_user_by_id(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Détails d'un utilisateur par ID.

    Args:
        user_id: ID de l'utilisateur
        db: Session de base de données
        current_user: Admin authentifié

    Returns:
        UserResponse: Détails de l'utilisateur

    Raises:
        HTTPException 404: Utilisateur non trouvé
    """
    try:
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Utilisateur non trouvé"
            )

        return UserResponse.model_validate(user)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération de l'utilisateur: {str(e)}"
        )


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Modifier un utilisateur",
    description="Modifie les propriétés d'un utilisateur (rôle, statut actif, etc.)."
)
async def update_user(
    user_id: UUID,
    user_update: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Modification d'un utilisateur.

    Args:
        user_id: ID de l'utilisateur à modifier
        user_update: Données de mise à jour
        db: Session de base de données
        current_user: Admin authentifié

    Returns:
        UserResponse: Utilisateur modifié

    Raises:
        HTTPException 404: Utilisateur non trouvé
        HTTPException 400: Modification non autorisée
    """
    try:
        # Récupérer l'utilisateur
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Utilisateur non trouvé"
            )

        # Empêcher la modification de son propre compte
        if user.id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Impossible de modifier son propre compte"
            )

        # Sauvegarder les valeurs originales pour l'audit
        original_values = {
            "role": user.role,
            "is_active": user.is_active,
            "is_verified": user.is_verified
        }

        # Appliquer les modifications
        update_data = user_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(user, field):
                setattr(user, field, value)

        # Sauvegarder en base
        await db.commit()
        await db.refresh(user)

        # Créer un log d'audit
        from ..models.auth import AuditLog
        audit_log = AuditLog(
            user_id=current_user.id,
            action="USER_UPDATE",
            resource_type="user",
            resource_id=user.id,
            details={
                "target_user": str(user.id),
                "changes": {
                    "before": original_values,
                    "after": {field: getattr(user, field) for field in update_data.keys()}
                }
            }
        )
        db.add(audit_log)
        await db.commit()

        return UserResponse.model_validate(user)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la modification: {str(e)}"
        )


@router.delete(
    "/{user_id}",
    summary="Supprimer un utilisateur",
    description="Supprime définitivement un utilisateur du système."
)
async def delete_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Suppression d'un utilisateur.

    Args:
        user_id: ID de l'utilisateur à supprimer
        db: Session de base de données
        current_user: Admin authentifié

    Returns:
        dict: Message de confirmation

    Raises:
        HTTPException 404: Utilisateur non trouvé
        HTTPException 400: Suppression non autorisée
    """
    try:
        # Récupérer l'utilisateur
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Utilisateur non trouvé"
            )

        # Empêcher la suppression de son propre compte
        if user.id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Impossible de supprimer son propre compte"
            )

        # Créer un log d'audit avant suppression
        from ..models.auth import AuditLog
        audit_log = AuditLog(
            user_id=current_user.id,
            action="USER_DELETE",
            resource_type="user",
            resource_id=user.id,
            details={
                "deleted_user": {
                    "email": user.email,
                    "role": user.role,
                    "created_at": user.created_at.isoformat()
                }
            }
        )
        db.add(audit_log)

        # Supprimer l'utilisateur
        await db.delete(user)
        await db.commit()

        return {"message": f"Utilisateur {user.email} supprimé avec succès"}

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la suppression: {str(e)}"
        )


# ============================================================
# ENDPOINTS AUDIT LOG
# ============================================================

@router.get(
    "/{user_id}/audit",
    response_model=List[AuditLogResponse],
    summary="Historique d'audit d'un utilisateur",
    description="Récupère l'historique complet des actions liées à un utilisateur."
)
async def get_user_audit_log(
    user_id: UUID,
    limit: int = Query(50, ge=1, le=200, description="Nombre d'entrées à retourner"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Historique d'audit pour un utilisateur.

    Args:
        user_id: ID de l'utilisateur
        limit: Nombre maximum d'entrées
        db: Session de base de données
        current_user: Admin authentifié

    Returns:
        List[AuditLogResponse]: Historique des actions

    Raises:
        HTTPException 404: Utilisateur non trouvé
    """
    try:
        # Vérifier que l'utilisateur existe
        user_result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Utilisateur non trouvé"
            )

        # Récupérer les logs d'audit
        query = select(AuditLog).where(
            or_(
                AuditLog.user_id == user_id,  # Actions de l'utilisateur
                AuditLog.resource_id == user_id  # Actions sur l'utilisateur
            )
        ).order_by(desc(AuditLog.created_at)).limit(limit)

        result = await db.execute(query)
        audit_logs = result.scalars().all()

        return [AuditLogResponse.model_validate(log) for log in audit_logs]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération de l'audit: {str(e)}"
        )


@router.get(
    "/{user_id}/audit/export",
    summary="Exporter l'audit en CSV",
    description="Exporte l'historique d'audit d'un utilisateur en format CSV."
)
async def export_user_audit(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Export de l'audit en CSV.

    Args:
        user_id: ID de l'utilisateur
        db: Session de base de données
        current_user: Admin authentifié

    Returns:
        Response: Fichier CSV
    """
    # TODO: Implémenter l'export CSV
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Export CSV non encore implémenté"
    )


# ============================================================
# ENDPOINTS DE GESTION AVANCÉE
# ============================================================

@router.post(
    "/{user_id}/activate",
    summary="Activer un utilisateur",
    description="Active un compte utilisateur désactivé."
)
async def activate_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Activation d'un compte utilisateur.

    Args:
        user_id: ID de l'utilisateur à activer
        db: Session de base de données
        current_user: Admin authentifié

    Returns:
        dict: Message de confirmation
    """
    return await _toggle_user_status(user_id, True, "activate", db, current_user)


@router.post(
    "/{user_id}/deactivate",
    summary="Désactiver un utilisateur",
    description="Désactive un compte utilisateur actif."
)
async def deactivate_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Désactivation d'un compte utilisateur.

    Args:
        user_id: ID de l'utilisateur à désactiver
        db: Session de base de données
        current_user: Admin authentifié

    Returns:
        dict: Message de confirmation
    """
    return await _toggle_user_status(user_id, False, "deactivate", db, current_user)


@router.post(
    "/{user_id}/unlock",
    summary="Déverrouiller un compte",
    description="Déverrouille un compte bloqué par protection brute-force."
)
async def unlock_user_account(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Déverrouillage forcé d'un compte.

    Args:
        user_id: ID de l'utilisateur à déverrouiller
        db: Session de base de données
        current_user: Admin authentifié

    Returns:
        dict: Message de confirmation
    """
    try:
        # Récupérer l'utilisateur
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Utilisateur non trouvé"
            )

        # Réinitialiser le verrouillage
        user.failed_login_count = 0
        user.locked_until = None

        await db.commit()

        # Audit log
        from ..models.auth import AuditLog
        audit_log = AuditLog(
            user_id=current_user.id,
            action="USER_UNLOCK",
            resource_type="user",
            resource_id=user.id,
            details={
                "target_user": user.email,
                "admin": current_user.email
            }
        )
        db.add(audit_log)
        await db.commit()

        return {"message": f"Compte {user.email} déverrouillé avec succès"}

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du déverrouillage: {str(e)}"
        )


# ============================================================
# FONCTIONS UTILITAIRES
# ============================================================

async def _toggle_user_status(
    user_id: UUID,
    is_active: bool,
    action: str,
    db: AsyncSession,
    current_user: User
) -> dict:
    """
    Fonction utilitaire pour activer/désactiver un utilisateur.

    Args:
        user_id: ID de l'utilisateur
        is_active: Nouveau statut
        action: Action effectuée (pour l'audit)
        db: Session de base de données
        current_user: Admin authentifié

    Returns:
        dict: Message de confirmation
    """
    try:
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Utilisateur non trouvé"
            )

        if user.id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Impossible de modifier son propre statut"
            )

        user.is_active = is_active
        await db.commit()

        # Audit log
        from ..models.auth import AuditLog
        audit_log = AuditLog(
            user_id=current_user.id,
            action=f"USER_{action.upper()}",
            resource_type="user",
            resource_id=user.id,
            details={
                "target_user": user.email,
                "new_status": is_active
            }
        )
        db.add(audit_log)
        await db.commit()

        status_word = "activé" if is_active else "désactivé"
        return {"message": f"Utilisateur {user.email} {status_word} avec succès"}

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la modification du statut: {str(e)}"
        )