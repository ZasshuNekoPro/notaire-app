"""
Routes API pour la gestion des successions.
Extraction automatique, calculs fiscaux, CRUD complet.
"""
import logging
from typing import List, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database import get_db
from src.models.succession import Succession, Heritier, ActifSuccessoral, PassifSuccessoral
from src.schemas.succession import (
    SuccessionCreate, SuccessionResponse, SuccessionUpdate,
    HeritierCreate, HeritierResponse, HeritierUpdate,
    ActifSuccessoralCreate, ActifSuccessoralResponse, ActifSuccessoralUpdate,
    PassifSuccessoralCreate, PassifSuccessoralResponse, PassifSuccessoralUpdate,
    RapportSuccession, ExtractionDocumentRequest, ExtractionDocumentResponse
)
from src.services.calcul_succession import calculer_succession, mettre_a_jour_calculs_succession
from src.services.succession_auto import extraire_succession_documents
from src.auth.dependencies import get_current_user, require_role
from src.models.auth import User


router = APIRouter(prefix="/successions", tags=["successions"])
logger = logging.getLogger(__name__)


# === Routes d'extraction automatique === #

@router.post(
    "/analyser-documents",
    response_model=ExtractionDocumentResponse,
    summary="Analyser des documents de succession par IA"
)
async def analyser_documents_succession(
    request: ExtractionDocumentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["notaire", "clerc", "admin"]))
):
    """
    Analyse automatique de documents de succession par IA.

    - **documents**: Liste des chemins/URLs de documents
    - **seuil_confiance**: Seuil minimum pour création automatique (0.1-1.0)
    - **auto_creation**: Créer automatiquement si confiance >= seuil

    Retourne les données extraites avec niveau de confiance.
    """
    try:
        logger.info(f"Analyse documents succession par {current_user.email}")

        # TODO: Validation des documents uploadés
        # TODO: Scan antivirus et validation format
        # TODO: Limitation taille et nombre de documents

        result = await extraire_succession_documents(request, db)

        # Log audit pour traçabilité
        logger.info(
            f"Extraction succession - Confiance: {result.confiance_globale:.2f}, "
            f"Auto-créée: {result.succession_creee is not None}"
        )

        return result

    except Exception as e:
        logger.error(f"Erreur analyse documents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'analyse des documents"
        )


@router.post(
    "/upload-documents",
    summary="Upload de documents pour analyse"
)
async def upload_documents_succession(
    files: List[UploadFile] = File(...),
    current_user: User = Depends(require_role(["notaire", "clerc", "admin"]))
):
    """
    Upload de documents de succession pour analyse ultérieure.

    Formats acceptés : PDF, JPG, PNG
    Taille max : 10MB par fichier, 50MB total
    """
    try:
        if len(files) > 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum 10 fichiers simultanés"
            )

        chemins_fichiers = []
        taille_totale = 0

        for file in files:
            # Validation format
            if not file.content_type.startswith(('application/pdf', 'image/')):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Format non supporté : {file.content_type}"
                )

            # Validation taille
            content = await file.read()
            if len(content) > 10 * 1024 * 1024:  # 10MB
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Fichier {file.filename} trop volumineux (>10MB)"
                )

            taille_totale += len(content)
            if taille_totale > 50 * 1024 * 1024:  # 50MB total
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Taille totale des fichiers dépassée (>50MB)"
                )

            # TODO: Sauvegarde sécurisée
            # TODO: Scan antivirus
            # TODO: Génération chemin unique

            chemin_fichier = f"/tmp/succession_{file.filename}"  # Temporaire
            chemins_fichiers.append(chemin_fichier)

        logger.info(f"Upload {len(files)} documents par {current_user.email}")

        return {
            "fichiers_uploades": len(files),
            "taille_totale": taille_totale,
            "chemins": chemins_fichiers,
            "message": "Documents uploadés avec succès"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur upload documents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'upload des documents"
        )


@router.post(
    "/creer-auto",
    response_model=SuccessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Créer une succession automatiquement"
)
async def creer_succession_auto(
    succession_data: SuccessionCreate,
    forcer_creation: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["notaire", "admin"]))
):
    """
    Crée une succession automatiquement à partir de données structurées.

    Effectue automatiquement les calculs fiscaux après création.
    """
    try:
        logger.info(f"Création succession auto par {current_user.email}")

        # Validation unicité numéro dossier
        existing = await db.execute(
            select(Succession).where(Succession.numero_dossier == succession_data.numero_dossier)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Numéro de dossier {succession_data.numero_dossier} déjà existant"
            )

        # Création succession principale
        succession = Succession(
            numero_dossier=succession_data.numero_dossier,
            defunt_nom=succession_data.defunt_nom,
            defunt_prenom=succession_data.defunt_prenom,
            defunt_date_naissance=succession_data.defunt_date_naissance,
            defunt_date_deces=succession_data.defunt_date_deces,
            lieu_deces=succession_data.lieu_deces,
            statut=succession_data.statut,
            extraction_metadata={"created_by": current_user.id, "auto_created": True}
        )

        db.add(succession)
        await db.flush()

        # Création héritiers
        for h_data in succession_data.heritiers:
            heritier = Heritier(
                succession_id=succession.id,
                nom=h_data.nom,
                prenom=h_data.prenom,
                date_naissance=h_data.date_naissance,
                lien_parente=h_data.lien_parente,
                quote_part_legale=h_data.quote_part_legale,
                adresse=h_data.adresse,
                email=h_data.email,
                telephone=h_data.telephone
            )
            db.add(heritier)

        # Création actifs
        for a_data in succession_data.actifs:
            actif = ActifSuccessoral(
                succession_id=succession.id,
                type_actif=a_data.type_actif,
                description=a_data.description,
                valeur_estimee=a_data.valeur_estimee,
                date_estimation=a_data.date_estimation,
                adresse=a_data.adresse,
                surface=a_data.surface
            )
            db.add(actif)

        # Création passifs
        for p_data in succession_data.passifs:
            passif = PassifSuccessoral(
                succession_id=succession.id,
                type_passif=p_data.type_passif,
                description=p_data.description,
                montant=p_data.montant,
                creancier=p_data.creancier,
                date_echeance=p_data.date_echeance
            )
            db.add(passif)

        await db.commit()

        # Calculs fiscaux automatiques
        await mettre_a_jour_calculs_succession(succession.id, db)

        # Rechargement avec relations
        query = (
            select(Succession)
            .options(
                selectinload(Succession.heritiers),
                selectinload(Succession.actifs),
                selectinload(Succession.passifs)
            )
            .where(Succession.id == succession.id)
        )
        result = await db.execute(query)
        succession_complete = result.scalar_one()

        logger.info(f"Succession {succession.numero_dossier} créée avec succès")

        return SuccessionResponse.model_validate(succession_complete)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Erreur création succession auto: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la création de la succession"
        )


# === Routes de calcul fiscal === #

@router.get(
    "/{succession_id}/rapport",
    response_model=RapportSuccession,
    summary="Rapport complet de succession"
)
async def get_rapport_succession(
    succession_id: UUID,
    recalculer: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["notaire", "clerc", "admin", "client"]))
):
    """
    Génère le rapport complet de succession avec calculs fiscaux.

    - **recalculer**: Force le recalcul des droits de succession
    """
    try:
        # Vérification existence succession
        query = select(Succession).where(Succession.id == succession_id)
        result = await db.execute(query)
        succession = result.scalar_one_or_none()

        if not succession:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Succession non trouvée"
            )

        # TODO: Vérification droits d'accès selon RBAC
        # TODO: Les clients ne peuvent voir que leurs propres successions

        # Recalcul si demandé ou si jamais calculé
        if recalculer or not succession.actif_net:
            await mettre_a_jour_calculs_succession(succession_id, db)

        # Génération du rapport
        rapport = await calculer_succession(succession_id, db)

        logger.info(f"Rapport succession {succession.numero_dossier} généré")

        return RapportSuccession(**rapport)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur génération rapport: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la génération du rapport"
        )


@router.post(
    "/{succession_id}/calcul-fiscal",
    summary="Recalculer les droits de succession"
)
async def recalculer_droits_succession(
    succession_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["notaire", "clerc", "admin"]))
):
    """
    Force le recalcul des droits de succession.

    Utilisé après modification des actifs, passifs ou héritiers.
    """
    try:
        await mettre_a_jour_calculs_succession(succession_id, db)

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "Calculs fiscaux mis à jour avec succès",
                "succession_id": str(succession_id)
            }
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Erreur recalcul fiscal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors du recalcul fiscal"
        )


# === CRUD Successions === #

@router.get(
    "/",
    response_model=List[SuccessionResponse],
    summary="Lister les successions"
)
async def list_successions(
    skip: int = 0,
    limit: int = 50,
    statut: str = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["notaire", "clerc", "admin"]))
):
    """
    Liste les successions avec pagination et filtres.
    """
    try:
        query = select(Succession).options(
            selectinload(Succession.heritiers),
            selectinload(Succession.actifs),
            selectinload(Succession.passifs)
        )

        if statut:
            query = query.where(Succession.statut == statut)

        query = query.offset(skip).limit(limit).order_by(Succession.created_at.desc())

        result = await db.execute(query)
        successions = result.scalars().all()

        return [SuccessionResponse.model_validate(s) for s in successions]

    except Exception as e:
        logger.error(f"Erreur liste successions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération des successions"
        )


@router.get(
    "/{succession_id}",
    response_model=SuccessionResponse,
    summary="Récupérer une succession"
)
async def get_succession(
    succession_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["notaire", "clerc", "admin", "client"]))
):
    """
    Récupère une succession complète avec ses relations.
    """
    try:
        query = (
            select(Succession)
            .options(
                selectinload(Succession.heritiers),
                selectinload(Succession.actifs),
                selectinload(Succession.passifs)
            )
            .where(Succession.id == succession_id)
        )

        result = await db.execute(query)
        succession = result.scalar_one_or_none()

        if not succession:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Succession non trouvée"
            )

        # TODO: Vérification droits d'accès selon RBAC

        return SuccessionResponse.model_validate(succession)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur récupération succession: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération de la succession"
        )


@router.put(
    "/{succession_id}",
    response_model=SuccessionResponse,
    summary="Mettre à jour une succession"
)
async def update_succession(
    succession_id: UUID,
    succession_update: SuccessionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["notaire", "clerc", "admin"]))
):
    """
    Met à jour les informations d'une succession.

    Déclenche automatiquement le recalcul fiscal.
    """
    try:
        query = select(Succession).where(Succession.id == succession_id)
        result = await db.execute(query)
        succession = result.scalar_one_or_none()

        if not succession:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Succession non trouvée"
            )

        # Mise à jour des champs modifiés
        update_data = succession_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(succession, field, value)

        await db.commit()

        # Recalcul automatique si modification impactante
        if any(field in update_data for field in ["statut"]):
            await mettre_a_jour_calculs_succession(succession_id, db)

        # Rechargement avec relations
        query = (
            select(Succession)
            .options(
                selectinload(Succession.heritiers),
                selectinload(Succession.actifs),
                selectinload(Succession.passifs)
            )
            .where(Succession.id == succession_id)
        )
        result = await db.execute(query)
        succession_updated = result.scalar_one()

        logger.info(f"Succession {succession.numero_dossier} mise à jour")

        return SuccessionResponse.model_validate(succession_updated)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Erreur mise à jour succession: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la mise à jour"
        )


@router.delete(
    "/{succession_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer une succession"
)
async def delete_succession(
    succession_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["notaire", "admin"]))
):
    """
    Supprime une succession et toutes ses données associées.

    ⚠️ Action irréversible - Réservée aux notaires et admins.
    """
    try:
        query = select(Succession).where(Succession.id == succession_id)
        result = await db.execute(query)
        succession = result.scalar_one_or_none()

        if not succession:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Succession non trouvée"
            )

        # Suppression cascade (héritiers, actifs, passifs)
        await db.delete(succession)
        await db.commit()

        logger.warning(
            f"Succession {succession.numero_dossier} supprimée par {current_user.email}"
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Erreur suppression succession: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la suppression"
        )


# === Routes d'administration === #

@router.get(
    "/stats/dashboard",
    summary="Statistiques des successions"
)
async def get_stats_successions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["notaire", "admin"]))
):
    """
    Statistiques globales pour le tableau de bord.
    """
    try:
        # TODO: Implémenter requêtes statistiques
        # - Nombre de successions par statut
        # - Montant total des actifs nets
        # - Droits de succession moyens
        # - Évolution mensuelle

        return {
            "total_successions": 0,
            "en_cours": 0,
            "completes": 0,
            "actif_net_total": 0,
            "droits_total": 0,
            "message": "Statistiques à implémenter"
        }

    except Exception as e:
        logger.error(f"Erreur stats successions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors du calcul des statistiques"
        )