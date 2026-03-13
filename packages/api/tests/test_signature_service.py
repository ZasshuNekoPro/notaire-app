"""
Tests pour le service de signature électronique.
"""
import pytest
import asyncio
import json
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timezone

from packages.api.src.services.signature_service import (
    BaseSignatureProvider,
    SignatureSimuleeProvider,
    YousignProvider,
    get_signature_provider,
    SignatureService,
    StatutSignature,
    DocumentSignature,
    DemandeurSignature
)


class TestSignatureSimuleeProvider:
    """Tests pour le provider de simulation."""

    @pytest.fixture
    def provider(self):
        return SignatureSimuleeProvider()

    @pytest.mark.asyncio
    async def test_simulee_flow_complet(self, provider):
        """Test du flow complet avec simulation : initier → en_attente → compléter"""

        # 1. Initier une signature
        doc_signature = DocumentSignature(
            nom_fichier="acte_vente.pdf",
            contenu_base64="JVBERi0xLjQKJcOkw7zDtsKdDQo=",  # PDF fake
            titre="Acte de vente"
        )

        demandeur = DemandeurSignature(
            nom="Dupont",
            prenom="Jean",
            email="jean.dupont@example.com",
            telephone="+33123456789"
        )

        signature_id = await provider.initier_signature(
            document=doc_signature,
            demandeurs=[demandeur],
            callback_url="https://app.notaire.fr/webhooks/signatures"
        )

        # Vérifier l'ID retourné
        assert signature_id.startswith("sim_")

        # 2. Vérifier le statut initial
        statut = await provider.get_statut_signature(signature_id)
        assert statut.statut == StatutSignature.EN_ATTENTE
        assert statut.demandeurs[0].email == "jean.dupont@example.com"
        assert statut.demandeurs[0].statut == StatutSignature.EN_ATTENTE

        # 3. Attendre la complétion automatique (simulation = 5 secondes)
        await asyncio.sleep(6)  # Attendre un peu plus longtemps

        # 4. Vérifier le statut après complétion
        statut_final = await provider.get_statut_signature(signature_id)
        assert statut_final.statut == StatutSignature.COMPLETE
        assert statut_final.demandeurs[0].statut == StatutSignature.COMPLETE
        assert statut_final.date_completion is not None


class TestYousignProvider:
    """Tests pour le provider Yousign."""

    @pytest.fixture
    def provider(self):
        return YousignProvider(
            api_key="test_api_key",
            environment="sandbox"
        )

    @pytest.mark.asyncio
    async def test_webhook_yousign(self, provider):
        """Test du traitement d'un webhook Yousign valide → statut mis à jour"""

        # Simuler un webhook de complétion
        webhook_payload = {
            "data": {
                "signature_request": {
                    "id": "sr_test_123",
                    "status": "done",
                    "documents": [
                        {
                            "id": "doc_123",
                            "filename": "acte.pdf"
                        }
                    ],
                    "signers": [
                        {
                            "id": "signer_123",
                            "email": "test@example.com",
                            "status": "signed"
                        }
                    ]
                }
            },
            "event_name": "signature_request.done"
        }

        # Mock de la vérification de signature (normalement avec clé secrète)
        with patch.object(provider, '_verifier_signature_webhook', return_value=True):
            # Traiter le webhook
            statut = await provider.verifier_webhook(json.dumps(webhook_payload))

            assert statut.signature_id == "sr_test_123"
            assert statut.statut == StatutSignature.COMPLETE
            assert len(statut.demandeurs) == 1
            assert statut.demandeurs[0].email == "test@example.com"
            assert statut.demandeurs[0].statut == StatutSignature.COMPLETE


class TestSignatureService:
    """Tests pour le service principal de signature."""

    @pytest.fixture
    def mock_db_session(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_db_session):
        return SignatureService(db=mock_db_session)

    @pytest.mark.asyncio
    async def test_document_signe_telecharge(self, service):
        """Test téléchargement du document signé après complétion → PDF retourné"""

        # Mock du provider simulé
        mock_provider = Mock()
        mock_provider.telecharger_document_signe = AsyncMock(return_value={
            "nom_fichier": "acte_vente_signe.pdf",
            "contenu_base64": "JVBERi0xLjQKJcOkw7zDtsKdDQpTaWduZWQgUERGIGNvbnRlbnQ=",
            "taille": 125000
        })

        # Mock de get_signature_provider pour retourner notre mock
        with patch('packages.api.src.services.signature_service.get_signature_provider',
                   return_value=mock_provider):

            # Télécharger le document signé
            document = await service.telecharger_document_signe("test_signature_123")

            # Vérifications
            assert document["nom_fichier"] == "acte_vente_signe.pdf"
            assert document["contenu_base64"].startswith("JVBERi")  # Header PDF en base64
            assert document["taille"] > 0

            # Vérifier que le provider a bien été appelé
            mock_provider.telecharger_document_signe.assert_called_once_with("test_signature_123")


class TestProviderSelection:
    """Tests pour la sélection automatique des providers."""

    @pytest.mark.asyncio
    async def test_provider_selection(self):
        """Test sélection provider : SIGNATURE_PROVIDER=simulee → SignatureSimuleeProvider"""

        # Test avec provider simulé
        with patch.dict('os.environ', {'SIGNATURE_PROVIDER': 'simulee'}):
            provider = get_signature_provider()
            assert isinstance(provider, SignatureSimuleeProvider)

        # Test avec provider Yousign
        with patch.dict('os.environ', {
            'SIGNATURE_PROVIDER': 'yousign',
            'YOUSIGN_API_KEY': 'test_key'
        }):
            provider = get_signature_provider()
            assert isinstance(provider, YousignProvider)

        # Test avec provider par défaut (simulé si pas de config)
        with patch.dict('os.environ', {}, clear=True):
            provider = get_signature_provider()
            assert isinstance(provider, SignatureSimuleeProvider)


class TestIntegrationCompleteSignature:
    """Test d'intégration complète du processus de signature."""

    @pytest.mark.asyncio
    async def test_processus_signature_complet(self):
        """Test d'intégration : création → signature → webhook → téléchargement"""

        # 1. Initialiser le service avec provider simulé
        mock_db = AsyncMock()
        service = SignatureService(db=mock_db)

        with patch.dict('os.environ', {'SIGNATURE_PROVIDER': 'simulee'}):

            # 2. Créer une demande de signature
            doc_signature = DocumentSignature(
                nom_fichier="compromis_vente.pdf",
                contenu_base64="JVBERi0xLjQKJcOkw7zDtsKdDQo=",
                titre="Compromis de vente"
            )

            demandeurs = [
                DemandeurSignature(
                    nom="Martin",
                    prenom="Sophie",
                    email="sophie.martin@example.com"
                ),
                DemandeurSignature(
                    nom="Bernard",
                    prenom="Pierre",
                    email="pierre.bernard@example.com"
                )
            ]

            signature_id = await service.initier_signature(
                document=doc_signature,
                demandeurs=demandeurs,
                callback_url="https://app.notaire.fr/webhooks/signatures"
            )

            # 3. Vérifier la signature créée
            assert signature_id.startswith("sim_")

            # 4. Vérifier le statut initial
            statut = await service.get_statut_signature(signature_id)
            assert statut.statut == StatutSignature.EN_ATTENTE
            assert len(statut.demandeurs) == 2

            # 5. Attendre la simulation de signature (5s)
            await asyncio.sleep(6)

            # 6. Vérifier la complétion
            statut_final = await service.get_statut_signature(signature_id)
            assert statut_final.statut == StatutSignature.COMPLETE

            # 7. Télécharger le document signé
            document_signe = await service.telecharger_document_signe(signature_id)
            assert document_signe["nom_fichier"] == "compromis_vente_signe.pdf"
            assert len(document_signe["contenu_base64"]) > 0


# Tests d'erreur et cas limites
class TestErrorHandling:
    """Tests pour la gestion d'erreurs."""

    @pytest.mark.asyncio
    async def test_signature_inexistante(self):
        """Test erreur pour signature inexistante."""

        provider = SignatureSimuleeProvider()

        with pytest.raises(ValueError, match="Signature non trouvée"):
            await provider.get_statut_signature("signature_inexistante")

    @pytest.mark.asyncio
    async def test_webhook_payload_invalide(self):
        """Test erreur pour payload webhook invalide."""

        provider = YousignProvider(api_key="test", environment="sandbox")

        with pytest.raises(ValueError, match="Payload webhook invalide"):
            await provider.verifier_webhook("payload_json_invalide")

    @pytest.mark.asyncio
    async def test_document_vide(self):
        """Test erreur pour document vide."""

        provider = SignatureSimuleeProvider()

        doc_signature = DocumentSignature(
            nom_fichier="",  # Nom vide
            contenu_base64="",  # Contenu vide
            titre="Test"
        )

        demandeur = DemandeurSignature(
            nom="Test",
            prenom="User",
            email="test@example.com"
        )

        with pytest.raises(ValueError, match="Document invalide"):
            await provider.initier_signature(
                document=doc_signature,
                demandeurs=[demandeur],
                callback_url="https://example.com/webhook"
            )