"""
Service de signature électronique avec abstraction providers.
Support Yousign v3 + provider simulé pour tests et démos.
"""
import os
import json
import hashlib
import hmac
import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from uuid import uuid4, UUID
from enum import Enum

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.dossiers import Dossier
from src.database import get_db


logger = logging.getLogger(__name__)


# === Enums et modèles === #

class StatutSignature(str, Enum):
    """Statuts de signature électronique."""
    EN_ATTENTE = "en_attente"      # Initié, en attente des signataires
    EN_COURS = "en_cours"          # Au moins un signataire a signé
    SIGNE = "signe"                # Tous signataires ont signé
    EXPIRE = "expire"              # Délai expiré
    ANNULE = "annule"              # Annulé par l'émetteur
    ERREUR = "erreur"              # Erreur technique


class SignataireInfo:
    """Informations d'un signataire."""
    def __init__(self, nom: str, email: str, role: str = "signataire"):
        self.nom = nom
        self.email = email
        self.role = role  # "signataire", "approbateur", "temoin"

    def to_dict(self) -> Dict[str, str]:
        return {
            "nom": self.nom,
            "email": self.email,
            "role": self.role
        }


class SignatureRequest:
    """Demande de signature complète."""
    def __init__(
        self,
        request_id: str,
        dossier_id: str,
        document_id: str,
        signataires: List[SignataireInfo],
        statut: StatutSignature = StatutSignature.EN_ATTENTE
    ):
        self.request_id = request_id
        self.dossier_id = dossier_id
        self.document_id = document_id
        self.signataires = signataires
        self.statut = statut
        self.created_at = datetime.now()
        self.expires_at = self.created_at + timedelta(days=30)  # 30 jours par défaut


# === Provider abstrait === #

class BaseSignatureProvider(ABC):
    """
    Provider abstrait pour signature électronique.
    Même pattern que BaseAIProvider du ai-core.
    """

    @abstractmethod
    async def initier(
        self,
        document: bytes,
        signataires: List[SignataireInfo],
        **kwargs
    ) -> str:
        """
        Initie une demande de signature.

        Args:
            document: Document PDF à faire signer (bytes)
            signataires: Liste des signataires requis
            **kwargs: Options spécifiques au provider

        Returns:
            request_id: Identifiant unique de la demande
        """
        pass

    @abstractmethod
    async def get_statut(self, request_id: str) -> StatutSignature:
        """
        Récupère le statut d'une demande de signature.

        Args:
            request_id: Identifiant de la demande

        Returns:
            Statut actuel de la signature
        """
        pass

    @abstractmethod
    async def telecharger_signe(self, request_id: str) -> bytes:
        """
        Télécharge le document signé.

        Args:
            request_id: Identifiant de la demande

        Returns:
            Document PDF signé (bytes)
        """
        pass

    @abstractmethod
    async def annuler(self, request_id: str) -> None:
        """
        Annule une demande de signature.

        Args:
            request_id: Identifiant de la demande à annuler
        """
        pass

    @abstractmethod
    async def verifier_webhook(self, payload: bytes, signature: str) -> bool:
        """
        Vérifie la signature d'un webhook.

        Args:
            payload: Corps du webhook (raw bytes)
            signature: Signature fournie dans les headers

        Returns:
            True si la signature est valide
        """
        pass


# === Provider simulé (tests/démo) === #

class SignatureSimuleeProvider(BaseSignatureProvider):
    """
    Provider simulé pour tests et démonstrations.
    Simule toutes les étapes sans appel externe réel.
    """

    def __init__(self):
        # Stockage en mémoire des demandes simulées
        self.requests: Dict[str, SignatureRequest] = {}
        self.documents: Dict[str, bytes] = {}
        self.webhook_secret = "simulation_webhook_secret"

    async def initier(
        self,
        document: bytes,
        signataires: List[SignataireInfo],
        **kwargs
    ) -> str:
        """
        Simule l'initiation d'une signature.
        """
        request_id = f"sim_{uuid4().hex[:12]}"

        # Stocker la demande
        self.requests[request_id] = SignatureRequest(
            request_id=request_id,
            dossier_id=kwargs.get("dossier_id", "unknown"),
            document_id=kwargs.get("document_id", "unknown"),
            signataires=signataires,
            statut=StatutSignature.EN_ATTENTE
        )

        # Stocker le document
        self.documents[request_id] = document

        # Simuler la signature automatique après 5 secondes
        asyncio.create_task(self._simuler_signature_auto(request_id))

        logger.info(f"Signature simulée initiée: {request_id} avec {len(signataires)} signataires")

        return request_id

    async def get_statut(self, request_id: str) -> StatutSignature:
        """
        Retourne le statut simulé.
        """
        if request_id not in self.requests:
            return StatutSignature.ERREUR

        return self.requests[request_id].statut

    async def telecharger_signe(self, request_id: str) -> bytes:
        """
        Retourne le document "signé" (ajout footer simulation).
        """
        if request_id not in self.documents:
            raise ValueError(f"Document non trouvé: {request_id}")

        request = self.requests[request_id]
        if request.statut != StatutSignature.SIGNE:
            raise ValueError(f"Document non encore signé: {request.statut}")

        # Simulation: ajouter footer de signature au PDF
        document_original = self.documents[request_id]
        footer_signature = b"\n\n--- DOCUMENT SIGNE ELECTRONIQUEMENT (SIMULATION) ---\n"
        footer_signature += f"Request ID: {request_id}\n".encode()
        footer_signature += f"Signataires: {len(request.signataires)}\n".encode()
        footer_signature += f"Date: {datetime.now().isoformat()}\n".encode()

        return document_original + footer_signature

    async def annuler(self, request_id: str) -> None:
        """
        Annule la demande simulée.
        """
        if request_id in self.requests:
            self.requests[request_id].statut = StatutSignature.ANNULE
            logger.info(f"Signature simulée annulée: {request_id}")

    async def verifier_webhook(self, payload: bytes, signature: str) -> bool:
        """
        Vérifie la signature webhook simulée.
        """
        expected_signature = hmac.new(
            self.webhook_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(f"sha256={expected_signature}", signature)

    async def _simuler_signature_auto(self, request_id: str):
        """
        Simule la signature automatique après délai.
        """
        try:
            # Attendre 5 secondes pour simuler le processus
            await asyncio.sleep(5)

            if request_id in self.requests:
                request = self.requests[request_id]
                if request.statut == StatutSignature.EN_ATTENTE:
                    request.statut = StatutSignature.SIGNE
                    logger.info(f"Signature simulée complétée: {request_id}")

        except Exception as e:
            logger.error(f"Erreur simulation signature {request_id}: {e}")


# === Provider Yousign === #

class YousignProvider(BaseSignatureProvider):
    """
    Provider pour Yousign API v3.
    Documentation: https://developers.yousign.com/docs
    """

    def __init__(
        self,
        api_key: str,
        webhook_secret: str,
        base_url: str = "https://api.yousign.com"
    ):
        self.api_key = api_key
        self.webhook_secret = webhook_secret
        self.base_url = base_url
        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
        )

    async def initier(
        self,
        document: bytes,
        signataires: List[SignataireInfo],
        **kwargs
    ) -> str:
        """
        Initie une signature via API Yousign v3.
        """
        try:
            # 1. Upload du document
            document_id = await self._upload_document(
                document,
                kwargs.get("document_name", "document.pdf")
            )

            # 2. Créer la demande de signature
            signature_request = {
                "name": f"Signature {kwargs.get('dossier_id', 'unknown')}",
                "delivery_mode": "email",
                "reminder_settings": {
                    "interval_in_days": 3,
                    "max_occurrences": 3
                },
                "expiration_date": (datetime.now() + timedelta(days=30)).isoformat(),
                "documents": [{"id": document_id}],
                "signers": []
            }

            # 3. Ajouter les signataires
            for signataire in signataires:
                signature_request["signers"].append({
                    "info": {
                        "first_name": signataire.nom.split()[0] if signataire.nom else "",
                        "last_name": " ".join(signataire.nom.split()[1:]) if len(signataire.nom.split()) > 1 else signataire.nom,
                        "email": signataire.email,
                        "locale": "fr"
                    },
                    "signature_level": "electronic_signature",
                    "fields": [
                        {
                            "type": "signature",
                            "document_id": document_id,
                            "page": 1,
                            "x": 100,
                            "y": 100,
                            "width": 150,
                            "height": 50
                        }
                    ]
                })

            # 4. Créer la demande
            response = await self.client.post(
                f"{self.base_url}/signature_requests",
                json=signature_request
            )
            response.raise_for_status()

            signature_data = response.json()
            request_id = signature_data["id"]

            # 5. Activer la demande pour envoi emails
            await self.client.post(f"{self.base_url}/signature_requests/{request_id}/activate")

            logger.info(f"Signature Yousign initiée: {request_id}")

            return request_id

        except Exception as e:
            logger.error(f"Erreur initiation Yousign: {e}")
            raise

    async def get_statut(self, request_id: str) -> StatutSignature:
        """
        Récupère le statut via API Yousign.
        """
        try:
            response = await self.client.get(
                f"{self.base_url}/signature_requests/{request_id}"
            )
            response.raise_for_status()

            data = response.json()
            yousign_status = data.get("status", "unknown")

            # Mapping des statuts Yousign → nos statuts
            status_mapping = {
                "draft": StatutSignature.EN_ATTENTE,
                "ongoing": StatutSignature.EN_COURS,
                "done": StatutSignature.SIGNE,
                "expired": StatutSignature.EXPIRE,
                "canceled": StatutSignature.ANNULE,
                "error": StatutSignature.ERREUR
            }

            return status_mapping.get(yousign_status, StatutSignature.ERREUR)

        except Exception as e:
            logger.error(f"Erreur statut Yousign {request_id}: {e}")
            return StatutSignature.ERREUR

    async def telecharger_signe(self, request_id: str) -> bytes:
        """
        Télécharge le document signé via API Yousign.
        """
        try:
            # Récupérer les documents de la demande
            response = await self.client.get(
                f"{self.base_url}/signature_requests/{request_id}/documents"
            )
            response.raise_for_status()

            documents = response.json()

            if not documents or len(documents) == 0:
                raise ValueError("Aucun document trouvé")

            # Télécharger le premier document signé
            document_id = documents[0]["id"]
            download_response = await self.client.get(
                f"{self.base_url}/documents/{document_id}/download",
                headers={"Accept": "application/pdf"}
            )
            download_response.raise_for_status()

            return download_response.content

        except Exception as e:
            logger.error(f"Erreur téléchargement Yousign {request_id}: {e}")
            raise

    async def annuler(self, request_id: str) -> None:
        """
        Annule la demande via API Yousign.
        """
        try:
            response = await self.client.post(
                f"{self.base_url}/signature_requests/{request_id}/cancel"
            )
            response.raise_for_status()

            logger.info(f"Signature Yousign annulée: {request_id}")

        except Exception as e:
            logger.error(f"Erreur annulation Yousign {request_id}: {e}")
            raise

    async def verifier_webhook(self, payload: bytes, signature: str) -> bool:
        """
        Vérifie la signature webhook Yousign (X-Yousign-Signature-256).
        """
        try:
            expected_signature = hmac.new(
                self.webhook_secret.encode(),
                payload,
                hashlib.sha256
            ).hexdigest()

            return hmac.compare_digest(f"sha256={expected_signature}", signature)

        except Exception as e:
            logger.error(f"Erreur vérification webhook Yousign: {e}")
            return False

    async def _upload_document(self, document: bytes, filename: str) -> str:
        """
        Upload un document via API Yousign.
        """
        try:
            # Créer l'objet document
            document_data = {
                "name": filename,
                "nature": "signable_document"
            }

            response = await self.client.post(
                f"{self.base_url}/documents",
                json=document_data
            )
            response.raise_for_status()

            document_info = response.json()
            document_id = document_info["id"]

            # Upload le contenu
            upload_response = await self.client.post(
                f"{self.base_url}/documents/{document_id}/upload",
                files={"file": (filename, document, "application/pdf")}
            )
            upload_response.raise_for_status()

            return document_id

        except Exception as e:
            logger.error(f"Erreur upload document Yousign: {e}")
            raise


# === Factory Pattern === #

def get_signature_provider() -> BaseSignatureProvider:
    """
    Factory pour récupérer le provider de signature selon config.
    Même pattern que get_ai_provider().
    """
    provider_type = os.getenv("SIGNATURE_PROVIDER", "simulee").lower()

    if provider_type == "yousign":
        api_key = os.getenv("YOUSIGN_API_KEY")
        webhook_secret = os.getenv("YOUSIGN_WEBHOOK_SECRET")

        if not api_key:
            logger.warning("YOUSIGN_API_KEY manquant, fallback vers provider simulé")
            return SignatureSimuleeProvider()

        if not webhook_secret:
            logger.warning("YOUSIGN_WEBHOOK_SECRET manquant")

        return YousignProvider(
            api_key=api_key,
            webhook_secret=webhook_secret or "default_secret",
            base_url=os.getenv("YOUSIGN_BASE_URL", "https://api.yousign.com")
        )

    elif provider_type == "simulee":
        return SignatureSimuleeProvider()

    else:
        logger.warning(f"Provider signature inconnu: {provider_type}, fallback vers simulé")
        return SignatureSimuleeProvider()


# === Service principal === #

class SignatureService:
    """
    Service principal pour gestion des signatures électroniques.
    """

    def __init__(self, provider: Optional[BaseSignatureProvider] = None):
        self.provider = provider or get_signature_provider()

    async def initier_signature(
        self,
        dossier_id: str,
        document: bytes,
        signataires: List[Dict[str, str]],
        db: AsyncSession
    ) -> str:
        """
        Initie une demande de signature pour un dossier.

        Args:
            dossier_id: ID du dossier notarial
            document: Document PDF à faire signer
            signataires: Liste des signataires [{nom, email, role}]
            db: Session de base de données

        Returns:
            request_id: Identifiant de la demande de signature
        """
        try:
            # Valider le dossier
            # TODO: Vérifier que le dossier existe en base

            # Convertir les signataires
            signataires_info = [
                SignataireInfo(**s) for s in signataires
            ]

            # Initier via le provider
            request_id = await self.provider.initier(
                document=document,
                signataires=signataires_info,
                dossier_id=dossier_id,
                document_id=f"doc_{uuid4().hex[:8]}"
            )

            # TODO: Enregistrer la demande en base de données
            # signature_request = SignatureRequestModel(...)
            # db.add(signature_request)
            # await db.commit()

            logger.info(f"Signature initiée pour dossier {dossier_id}: {request_id}")

            return request_id

        except Exception as e:
            logger.error(f"Erreur initiation signature dossier {dossier_id}: {e}")
            raise

    async def get_statut(self, request_id: str) -> StatutSignature:
        """
        Récupère le statut d'une demande de signature.
        """
        return await self.provider.get_statut(request_id)

    async def telecharger_document_signe(self, request_id: str) -> bytes:
        """
        Télécharge le document signé.
        """
        statut = await self.get_statut(request_id)

        if statut != StatutSignature.SIGNE:
            raise ValueError(f"Document non signé: statut {statut}")

        return await self.provider.telecharger_signe(request_id)

    async def traiter_webhook(
        self,
        payload: bytes,
        signature: str
    ) -> Dict[str, Any]:
        """
        Traite un webhook de provider de signature.
        """
        try:
            # Vérifier la signature
            if not await self.provider.verifier_webhook(payload, signature):
                raise ValueError("Signature webhook invalide")

            # Parser le payload
            webhook_data = json.loads(payload.decode())

            # Extraire les informations
            request_id = webhook_data.get("signature_request", {}).get("id")
            event_type = webhook_data.get("event_name")

            if not request_id:
                raise ValueError("ID de demande manquant dans webhook")

            # Mettre à jour le statut
            nouveau_statut = await self.get_statut(request_id)

            # TODO: Mettre à jour en base de données
            # TODO: Notifier via WebSocket si nécessaire

            logger.info(f"Webhook traité: {request_id} → {event_type} → {nouveau_statut}")

            return {
                "request_id": request_id,
                "event_type": event_type,
                "nouveau_statut": nouveau_statut.value,
                "success": True
            }

        except Exception as e:
            logger.error(f"Erreur traitement webhook: {e}")
            raise

    async def annuler_signature(self, request_id: str) -> None:
        """
        Annule une demande de signature.
        """
        await self.provider.annuler(request_id)

        # TODO: Mettre à jour en base de données

        logger.info(f"Signature annulée: {request_id}")