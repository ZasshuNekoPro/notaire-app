#!/usr/bin/env python3
"""
Router pour l'analyse et la rédaction d'actes notariaux
"""
import logging
import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..middleware.auth_middleware import require_role, get_current_user
from ..database import get_db
from ..schemas.actes import (
    AnalyserActeRequest,
    AnalyseActeResponse,
    RedigerActeRequest,
    RelireActeRequest,
    RelectureActeResponse
)
from ..services import actes_service
from ..models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/actes", tags=["actes"])


@router.post(
    "/analyser",
    response_model=AnalyseActeResponse,
    dependencies=[Depends(require_role("notaire", "clerc", "admin"))],
    summary="Analyse d'acte notarial",
    description="Analyse un acte et identifie les clauses manquantes et points d'attention"
)
async def analyser_acte(
    request: AnalyserActeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> AnalyseActeResponse:
    """
    Analyse un acte notarial et suggère les améliorations

    - **type_acte**: Type d'acte (VENTE, SUCCESSION, DONATION, etc.)
    - **elements**: Éléments de l'acte fournis

    Retourne une analyse avec clauses manquantes et articles de loi applicables.
    """
    try:
        logger.info(f"Analyse d'acte {request.type_acte} par {current_user.id}")

        # Vérifier que le type d'acte est supporté
        supported_types = ["VENTE", "SUCC", "DON", "TEST", "SCI", "PACS", "MARIAGE", "BAIL"]
        if request.type_acte not in supported_types:
            raise HTTPException(
                status_code=400,
                detail=f"Type d'acte non supporté: {request.type_acte}"
            )

        # Effectuer l'analyse via le service
        response = await actes_service.analyser_acte(request, db)

        logger.info(f"Analyse terminée - {len(response.clauses_manquantes)} clauses manquantes trouvées")
        return response

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Erreur lors de l'analyse d'acte: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Erreur interne lors de l'analyse d'acte"
        )


@router.post(
    "/rediger",
    dependencies=[Depends(require_role("notaire", "admin"))],  # Rédaction réservée aux notaires
    summary="Rédaction d'acte en streaming",
    description="Génère un acte notarial en streaming SSE"
)
async def rediger_acte(
    request: RedigerActeRequest,
    current_user: User = Depends(get_current_user)
) -> StreamingResponse:
    """
    Rédige un acte notarial en streaming

    - **type_acte**: Type d'acte à rédiger
    - **elements**: Éléments de l'acte (parties, biens, etc.)
    - **style**: Style de rédaction (formel ou simplifié)

    Retourne un stream SSE avec les chunks de l'acte généré.
    """
    try:
        logger.info(f"Rédaction d'acte {request.type_acte} en style {request.style} par {current_user.id}")

        # Générer l'acte via le service
        stream_response = await actes_service.rediger_acte_stream(request, str(current_user.id))

        return StreamingResponse(
            stream_response,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*"
            }
        )

    except Exception as e:
        logger.error(f"Erreur lors de la rédaction: {str(e)}")

        # En cas d'erreur, retourner un SSE d'erreur
        async def error_stream():
            error_data = {
                "type": "error",
                "error": f"Erreur lors de la rédaction: {str(e)}",
                "finished": True
            }
            yield f"data: {json.dumps(error_data)}\n\n"

        return StreamingResponse(
            error_stream(),
            media_type="text/event-stream"
        )


@router.post(
    "/relire",
    response_model=RelectureActeResponse,
    dependencies=[Depends(require_role("notaire", "clerc", "admin"))],
    summary="Relecture d'acte",
    description="Effectue une relecture critique d'un acte avec suggestions"
)
async def relire_acte(
    request: RelireActeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> RelectureActeResponse:
    """
    Effectue une relecture critique d'un acte

    - **contenu_acte**: Contenu de l'acte à relire
    - **type_acte**: Type d'acte pour adapter l'analyse

    Retourne un score de complétude avec corrections suggérées.
    """
    try:
        logger.info(f"Relecture d'acte {request.type_acte} par {current_user.id}")

        # Effectuer la relecture via le service
        response = await actes_service.relire_acte(request, db)

        logger.info(f"Relecture terminée - Score: {response.score_completude}%, {len(response.corrections)} corrections")
        return response

    except Exception as e:
        logger.error(f"Erreur lors de la relecture: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Erreur interne lors de la relecture"
        )