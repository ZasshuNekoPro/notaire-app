#!/usr/bin/env python3
"""
Router pour les consultations juridiques via RAG
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..middleware.auth_middleware import require_role, get_current_user
from ..database import get_db
from ..schemas.juridique import (
    QuestionJuridiqueRequest,
    QuestionJuridiqueResponse,
    StatistiquesJuridiques
)
from ..services import juridique_service
from ..models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/juridique", tags=["juridique"])


@router.post(
    "/question",
    response_model=QuestionJuridiqueResponse,
    dependencies=[Depends(require_role("notaire", "clerc", "admin"))],
    summary="Consultation juridique via RAG",
    description="Pose une question juridique et reçoit une réponse basée sur les sources légales"
)
async def poser_question_juridique(
    request: QuestionJuridiqueRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> QuestionJuridiqueResponse:
    """
    Effectue une consultation juridique via le système RAG

    - **question**: Question juridique (5-1000 caractères)
    - **source_types**: Types de sources à filtrer (optionnel)
    - **dossier_id**: ID du dossier pour sauvegarder l'interaction (optionnel)

    Retourne une réponse avec sources citées et score de confiance.
    """
    try:
        logger.info(f"Question juridique de {current_user.id}: {request.question[:100]}...")

        # Validation des source_types si fournis
        if request.source_types:
            valid_types = {"loi", "bofip", "jurisprudence", "acte_type"}
            invalid_types = set(request.source_types) - valid_types
            if invalid_types:
                raise HTTPException(
                    status_code=400,
                    detail=f"Types de sources invalides: {', '.join(invalid_types)}"
                )

        # Effectuer la consultation via le service
        response = await juridique_service.consulter_juridique(
            request=request,
            user_id=str(current_user.id),
            db=db
        )

        logger.info(f"Consultation terminée avec confiance {response.confiance}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la consultation juridique: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Erreur interne lors de la consultation juridique"
        )


@router.get(
    "/stats",
    response_model=StatistiquesJuridiques,
    summary="Statistiques base de connaissances",
    description="Retourne les statistiques de la base de connaissances juridiques"
)
async def obtenir_statistiques_juridiques() -> StatistiquesJuridiques:
    """
    Obtient les statistiques de la base de connaissances juridiques

    Accessible publiquement pour vérifier l'état du système.
    """
    try:
        logger.info("Récupération des statistiques juridiques")

        stats = await juridique_service.get_statistiques_juridiques()

        return StatistiquesJuridiques(
            total_chunks=stats["total_chunks"],
            by_source_type=stats["by_source_type"]
        )

    except Exception as e:
        logger.error(f"Erreur lors de la récupération des stats: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Erreur lors de la récupération des statistiques"
        )