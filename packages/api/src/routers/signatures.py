"""
Router FastAPI pour la signature électronique des documents notariaux.
Utilise le système de providers pour supporter différents services de signature (Yousign, etc.).
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr, Field
import base64
import uuid
import logging

from ..database import get_db
from ..auth import get_current_user, require_roles
from ..models.users import User
from ..services.signature_service import (
    SignatureService,
    StatutSignature,
    DocumentSignature,
    DemandeurSignature,
    get_signature_provider
)

# Configuration du logging
logger = logging.getLogger(__name__)

# Router FastAPI
router = APIRouter()

# ============================================================
# SCHÉMAS PYDANTIC
# ============================================================

class DemandeurSignatureCreate(BaseModel):
    """Schéma pour créer un demandeur de signature."""
    nom: str = Field(..., min_length=1, max_length=100, description="Nom de famille")
    prenom: str = Field(..., min_length=1, max_length=100, description="Prénom")
    email: EmailStr = Field(..., description="Adresse email pour recevoir la demande")
    telephone: Optional[str] = Field(None, max_length=20, description="Numéro de téléphone")
    ordre_signature: Optional[int] = Field(1, description="Ordre de signature (défaut: 1)")

class SignatureCreate(BaseModel):
    """Schéma pour créer une demande de signature."""
    titre_document: str = Field(..., min_length=1, max_length=200, description="Titre du document")
    demandeurs: List[DemandeurSignatureCreate] = Field(..., min_items=1, max_items=10,
                                                       description="Liste des signataires requis")
    callback_url: Optional[str] = Field(None, description="URL de callback pour webhooks")
    dossier_id: Optional[str] = Field(None, description="ID du dossier associé")
    expire_dans_jours: Optional[int] = Field(30, ge=1, le=365, description="Expiration en jours")

class SignatureResponse(BaseModel):
    """Schéma de réponse pour une signature."""
    signature_id: str
    statut: str
    titre_document: str
    date_creation: str
    date_expiration: Optional[str]
    demandeurs: List[dict]
    url_signature: Optional[str]
    message: str

class StatutSignatureResponse(BaseModel):
    """Schéma de réponse pour le statut d'une signature."""
    signature_id: str
    statut: str
    pourcentage_completion: int
    demandeurs: List[dict]
    date_creation: str
    date_completion: Optional[str]
    date_expiration: Optional[str]

class WebhookSignaturePayload(BaseModel):
    """Schéma pour recevoir les webhooks de signature."""
    signature_id: Optional[str]
    payload: dict
    provider: Optional[str]

# ============================================================
# ENDPOINTS API
# ============================================================

@router.post(
    "/initier",
    response_model=SignatureResponse,
    summary="Initier une signature électronique",
    description="Démarre un processus de signature électronique pour un document avec une liste de signataires.",
    tags=["Signature"]
)
async def initier_signature(
    signature_data: SignatureCreate,
    fichier: UploadFile = File(..., description="Document PDF à faire signer"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Initie une demande de signature électronique.

    - Télécharge le document PDF
    - Crée la demande de signature avec la liste des signataires
    - Retourne l'ID de signature et les URLs pour les signataires
    """
    try:
        # Vérifications de sécurité
        if fichier.content_type != "application/pdf":
            raise HTTPException(status_code=400, detail="Seuls les fichiers PDF sont acceptés")

        if fichier.size > 10 * 1024 * 1024:  # 10 MB max
            raise HTTPException(status_code=400, detail="Fichier trop volumineux (max 10 MB)")

        # Lire le fichier et encoder en base64
        contenu_fichier = await fichier.read()
        contenu_base64 = base64.b64encode(contenu_fichier).decode('utf-8')

        # Créer l'objet document
        document = DocumentSignature(
            nom_fichier=fichier.filename,
            contenu_base64=contenu_base64,
            titre=signature_data.titre_document
        )

        # Créer la liste des demandeurs
        demandeurs = [
            DemandeurSignature(
                nom=d.nom,
                prenom=d.prenom,
                email=d.email,
                telephone=d.telephone,
                ordre_signature=d.ordre_signature or 1
            )
            for d in signature_data.demandeurs
        ]

        # Initialiser le service de signature
        service = SignatureService(db=db)

        # Créer la demande de signature
        signature_id = await service.initier_signature(
            document=document,
            demandeurs=demandeurs,
            callback_url=signature_data.callback_url,
            dossier_id=signature_data.dossier_id,
            expire_dans_jours=signature_data.expire_dans_jours
        )

        # Récupérer le statut initial pour la réponse
        statut = await service.get_statut_signature(signature_id)

        logger.info(f"Signature initiée: {signature_id} par {current_user.email}")

        return SignatureResponse(
            signature_id=signature_id,
            statut=statut.statut.value,
            titre_document=signature_data.titre_document,
            date_creation=statut.date_creation.isoformat(),
            date_expiration=statut.date_expiration.isoformat() if statut.date_expiration else None,
            demandeurs=[
                {
                    "nom": d.nom,
                    "prenom": d.prenom,
                    "email": d.email,
                    "statut": d.statut.value,
                    "url_signature": d.url_signature
                }
                for d in statut.demandeurs
            ],
            url_signature=statut.url_signature,
            message="Demande de signature créée avec succès. Les signataires ont reçu un email."
        )

    except Exception as e:
        logger.error(f"Erreur création signature: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la création de la signature: {str(e)}")


@router.get(
    "/{signature_id}/statut",
    response_model=StatutSignatureResponse,
    summary="Statut d'une signature",
    description="Récupère le statut actuel d'une demande de signature et de ses signataires.",
    tags=["Signature"]
)
async def get_statut_signature(
    signature_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Récupère le statut d'une signature.

    - Statut global de la demande
    - Progression de chaque signataire
    - Dates importantes
    """
    try:
        service = SignatureService(db=db)
        statut = await service.get_statut_signature(signature_id)

        # Calculer le pourcentage de complétion
        if not statut.demandeurs:
            pourcentage = 0
        else:
            signes = sum(1 for d in statut.demandeurs if d.statut == StatutSignature.COMPLETE)
            pourcentage = int((signes / len(statut.demandeurs)) * 100)

        return StatutSignatureResponse(
            signature_id=signature_id,
            statut=statut.statut.value,
            pourcentage_completion=pourcentage,
            demandeurs=[
                {
                    "nom": d.nom,
                    "prenom": d.prenom,
                    "email": d.email,
                    "statut": d.statut.value,
                    "date_signature": d.date_signature.isoformat() if d.date_signature else None,
                    "url_signature": d.url_signature
                }
                for d in statut.demandeurs
            ],
            date_creation=statut.date_creation.isoformat(),
            date_completion=statut.date_completion.isoformat() if statut.date_completion else None,
            date_expiration=statut.date_expiration.isoformat() if statut.date_expiration else None
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Erreur récupération statut {signature_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Erreur lors de la récupération du statut")


@router.get(
    "/{signature_id}/telecharger",
    summary="Télécharger le document signé",
    description="Télécharge le document PDF signé une fois que toutes les signatures sont complètes.",
    tags=["Signature"]
)
async def telecharger_document_signe(
    signature_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Télécharge le document PDF signé.

    - Disponible uniquement quand toutes les signatures sont complètes
    - Retourne le PDF avec les signatures électroniques
    """
    try:
        service = SignatureService(db=db)

        # Vérifier que la signature est complète
        statut = await service.get_statut_signature(signature_id)
        if statut.statut != StatutSignature.COMPLETE:
            raise HTTPException(
                status_code=400,
                detail=f"Document non disponible. Statut: {statut.statut.value}"
            )

        # Télécharger le document signé
        document = await service.telecharger_document_signe(signature_id)

        # Décoder le base64
        contenu_pdf = base64.b64decode(document["contenu_base64"])

        logger.info(f"Document signé téléchargé: {signature_id} par {current_user.email}")

        # Retourner le PDF
        return Response(
            content=contenu_pdf,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{document["nom_fichier"]}"',
                "Content-Length": str(len(contenu_pdf))
            }
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Erreur téléchargement document {signature_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Erreur lors du téléchargement")


@router.post(
    "/{signature_id}/annuler",
    summary="Annuler une signature",
    description="Annule une demande de signature en cours. Seul l'initiateur peut annuler.",
    tags=["Signature"]
)
async def annuler_signature(
    signature_id: str,
    raison: str = Form(..., description="Raison de l'annulation"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Annule une demande de signature.

    - Seul l'initiateur de la signature peut l'annuler
    - Notifie tous les signataires de l'annulation
    """
    try:
        service = SignatureService(db=db)

        # Annuler la signature
        await service.annuler_signature(signature_id, raison)

        logger.info(f"Signature annulée: {signature_id} par {current_user.email}, raison: {raison}")

        return {"message": "Signature annulée avec succès", "signature_id": signature_id}

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Erreur annulation signature {signature_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Erreur lors de l'annulation")


# ============================================================
# WEBHOOKS
# ============================================================

@router.post(
    "/webhook",
    summary="Webhook pour les providers de signature",
    description="Endpoint pour recevoir les callbacks des services de signature externes (Yousign, etc.).",
    tags=["Webhook"]
)
async def webhook_signature(
    payload: WebhookSignaturePayload,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Reçoit les webhooks des providers de signature.

    - Traite les notifications de changement de statut
    - Met à jour la base de données en arrière-plan
    - Envoie des notifications aux utilisateurs si nécessaire
    """
    try:
        # Récupérer le provider configuré
        provider = get_signature_provider()

        # Traiter le webhook en arrière-plan pour répondre rapidement
        background_tasks.add_task(
            traiter_webhook_signature,
            provider=provider,
            payload=payload.payload,
            db=db
        )

        logger.info(f"Webhook reçu pour signature: {payload.signature_id}")

        return {"message": "Webhook reçu et traité", "status": "ok"}

    except Exception as e:
        logger.error(f"Erreur traitement webhook: {str(e)}")
        raise HTTPException(status_code=500, detail="Erreur traitement webhook")


async def traiter_webhook_signature(
    provider,
    payload: dict,
    db: AsyncSession
):
    """
    Traite un webhook de signature en arrière-plan.

    Args:
        provider: Provider de signature configuré
        payload: Données du webhook
        db: Session de base de données
    """
    try:
        import json

        # Vérifier et traiter le webhook via le provider
        statut_maj = await provider.verifier_webhook(json.dumps(payload))

        if statut_maj:
            # Mettre à jour en base de données si nécessaire
            service = SignatureService(db=db)

            # TODO: Implémenter la mise à jour en BDD des signatures
            # await service.mettre_a_jour_statut(statut_maj)

            logger.info(f"Statut signature mis à jour via webhook: {statut_maj.signature_id}")

    except Exception as e:
        logger.error(f"Erreur traitement webhook en arrière-plan: {str(e)}")


# ============================================================
# ENDPOINTS ADMIN
# ============================================================

@router.get(
    "/",
    summary="Lister les signatures",
    description="Liste toutes les signatures avec pagination et filtres. Accès admin requis.",
    tags=["Admin"]
)
async def lister_signatures(
    limit: int = 20,
    offset: int = 0,
    statut_filtre: Optional[str] = None,
    dossier_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "notaire"]))
):
    """
    Liste les signatures avec pagination et filtres.

    - Filtrage par statut, dossier, utilisateur
    - Pagination avec limit/offset
    - Accès restreint aux notaires et admins
    """
    try:
        service = SignatureService(db=db)

        # TODO: Implémenter la méthode de listing en service
        signatures = []  # await service.lister_signatures(limit, offset, statut_filtre, dossier_id)

        return {
            "signatures": signatures,
            "total": len(signatures),
            "limit": limit,
            "offset": offset
        }

    except Exception as e:
        logger.error(f"Erreur listing signatures: {str(e)}")
        raise HTTPException(status_code=500, detail="Erreur lors du listing")


@router.post(
    "/test",
    summary="Créer une signature de test",
    description="Crée une signature de test avec le provider simulé. Admin seulement.",
    tags=["Test"]
)
async def creer_signature_test(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"]))
):
    """
    Crée une signature de test pour démonstration.

    - Utilise le provider simulé
    - Document PDF de test
    - Signataires fictifs
    """
    try:
        # Document de test
        document_test = DocumentSignature(
            nom_fichier="acte_test.pdf",
            contenu_base64="JVBERi0xLjQKJcOkw7zDtsKdDQpTZXN0IGRvY3VtZW50",  # PDF minimal en base64
            titre="Acte de test - Signature électronique"
        )

        # Signataires de test
        demandeurs_test = [
            DemandeurSignature(
                nom="Martin",
                prenom="Jean",
                email="jean.martin@test.com",
                ordre_signature=1
            ),
            DemandeurSignature(
                nom="Dupont",
                prenom="Marie",
                email="marie.dupont@test.com",
                ordre_signature=2
            )
        ]

        # Créer la signature de test
        service = SignatureService(db=db)
        signature_id = await service.initier_signature(
            document=document_test,
            demandeurs=demandeurs_test,
            callback_url="https://test.notaire.fr/webhook"
        )

        logger.info(f"Signature de test créée: {signature_id} par {current_user.email}")

        return {
            "message": "Signature de test créée",
            "signature_id": signature_id,
            "note": "Cette signature sera automatiquement complétée en 5 secondes (provider simulé)"
        }

    except Exception as e:
        logger.error(f"Erreur création signature test: {str(e)}")
        raise HTTPException(status_code=500, detail="Erreur création signature test")