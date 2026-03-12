#!/usr/bin/env python3
"""
Service pour les consultations juridiques
"""
import logging
from uuid import UUID
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert

from packages.ai_core.src.rag import get_notaire_rag
from ..schemas.juridique import QuestionJuridiqueRequest, QuestionJuridiqueResponse

logger = logging.getLogger(__name__)


async def consulter_juridique(
    request: QuestionJuridiqueRequest,
    user_id: str,
    db: AsyncSession
) -> QuestionJuridiqueResponse:
    """
    Effectue une consultation juridique via RAG

    Args:
        request: Requête de consultation
        user_id: ID de l'utilisateur
        db: Session base de données

    Returns:
        Réponse structurée avec sources
    """
    try:
        # Obtenir l'instance RAG
        rag = get_notaire_rag()

        # Effectuer la recherche RAG
        response = await rag.question_complete(
            question=request.question,
            source_type=request.source_types[0] if request.source_types else None,
            k=5
        )

        # Logger l'interaction pour audit
        await _log_ai_interaction(
            db=db,
            user_id=user_id,
            question=request.question,
            response=response.reponse,
            sources=response.sources_citees,
            confidence=response.confiance
        )

        # Sauvegarder dans le dossier si ID fourni
        if request.dossier_id:
            await save_ai_interaction(
                db=db,
                dossier_id=request.dossier_id,
                question=request.question,
                response=response.reponse,
                user_id=user_id
            )

        return QuestionJuridiqueResponse(
            reponse=response.reponse,
            sources_citees=response.sources_citees,
            confiance=response.confiance,
            avertissements=response.avertissements
        )

    except Exception as e:
        logger.error(f"Erreur lors de la consultation juridique: {str(e)}")
        raise


async def _log_ai_interaction(
    db: AsyncSession,
    user_id: str,
    question: str,
    response: str,
    sources: List[str],
    confidence: float
) -> None:
    """
    Log une interaction IA pour audit
    """
    try:
        # Insérer dans la table ai_interactions (à créer si nécessaire)
        stmt = insert("ai_interactions").values(
            user_id=user_id,
            type="juridique_question",
            input_data={"question": question},
            output_data={
                "response": response,
                "sources": sources,
                "confidence": confidence
            }
        )
        await db.execute(stmt)
        await db.commit()

    except Exception as e:
        logger.warning(f"Impossible de logger l'interaction IA: {str(e)}")
        # Ne pas faire échouer la requête si le logging échoue


async def save_ai_interaction(
    db: AsyncSession,
    dossier_id: UUID,
    question: str,
    response: str,
    user_id: str
) -> None:
    """
    Sauvegarde une interaction IA dans un dossier

    Args:
        db: Session base de données
        dossier_id: ID du dossier
        question: Question posée
        response: Réponse générée
        user_id: ID de l'utilisateur
    """
    try:
        # Insérer dans la table dossier_interactions (à créer si nécessaire)
        stmt = insert("dossier_interactions").values(
            dossier_id=dossier_id,
            user_id=user_id,
            type="consultation_juridique",
            content={
                "question": question,
                "response": response
            }
        )
        await db.execute(stmt)
        await db.commit()

        logger.info(f"Interaction sauvegardée dans le dossier {dossier_id}")

    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde dans le dossier: {str(e)}")
        # Ne pas faire échouer la requête principale


async def get_statistiques_juridiques() -> dict:
    """
    Récupère les statistiques de la base de connaissances

    Returns:
        Statistiques formatées
    """
    try:
        rag = get_notaire_rag()
        stats = await rag.get_stats()

        return {
            "total_chunks": stats["total_chunks"],
            "by_source_type": stats["by_source_type"]
        }

    except Exception as e:
        logger.error(f"Erreur lors de la récupération des stats: {str(e)}")
        return {
            "total_chunks": 0,
            "by_source_type": {}
        }