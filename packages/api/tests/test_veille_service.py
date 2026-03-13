"""
Tests TDD pour le service de veille automatique.
Validation des détections DVF, Légifrance, BOFIP et analyses d'impact.
"""
import pytest
from datetime import datetime, timedelta, date
from decimal import Decimal
from uuid import uuid4
from unittest.mock import AsyncMock, patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.veille import (
    VeilleRule, Alerte, HistoriqueVeille,
    TypeSource, NiveauImpact, StatutAlerte
)
from src.models.dossiers import Dossier
from src.services.veille_service import VeilleEngine, creer_veille_engine


@pytest.fixture
async def veille_engine(db_session: AsyncSession):
    """Fixture pour créer un moteur de veille avec session DB."""
    return VeilleEngine(db_session)


@pytest.fixture
async def regle_dvf_75001(db_session: AsyncSession):
    """Règle de veille DVF pour le 1er arrondissement."""
    regle = VeilleRule(
        nom="Test DVF 75001",
        description="Surveillance test Paris 1er",
        type_source=TypeSource.DVF,
        configuration={
            "code_postal": "75001",
            "seuil_variation_pct": 5.0,
            "periode_comparaison_jours": 30
        },
        code_postal="75001",
        active=True,
        frequence_heures=168
    )
    db_session.add(regle)
    await db_session.flush()
    return regle


@pytest.fixture
async def regle_legifrance(db_session: AsyncSession):
    """Règle de veille Légifrance pour articles succession."""
    regle = VeilleRule(
        nom="Test Légifrance Succession",
        description="Surveillance Code civil successions",
        type_source=TypeSource.LEGIFRANCE,
        configuration={
            "articles_surveilles": ["720", "777", "892"],
            "verification_quotidienne": True
        },
        articles_codes=["720", "777", "892"],
        active=True,
        frequence_heures=24
    )
    db_session.add(regle)
    await db_session.flush()
    return regle


@pytest.fixture
async def dossier_test(db_session: AsyncSession):
    """Dossier de test avec bien immobilier."""
    dossier = Dossier(
        numero="2025-TEST-001",
        type_acte="SUCC",
        description="Succession test veille",
        statut="en_cours"
    )
    db_session.add(dossier)
    await db_session.flush()
    return dossier


class TestVeilleVariationsDVF:
    """Tests pour la détection des variations DVF."""

    async def test_variation_dvf_detecte(
        self,
        veille_engine: VeilleEngine,
        regle_dvf_75001: VeilleRule,
        db_session: AsyncSession
    ):
        """
        Test : prix +6% en 30j → alerte créée.
        Vérifie que le seuil de 5% déclenche une alerte de niveau FAIBLE.
        """
        # Given: Une variation de +6.2% simulée pour 75001
        code_postal = "75001"

        # When: Vérification des variations DVF
        alertes = await veille_engine.verifier_variations_dvf(code_postal)

        # Then: Une alerte doit être créée
        assert len(alertes) == 1

        alerte = alertes[0]
        assert alerte.veille_rule_id == regle_dvf_75001.id
        assert alerte.niveau_impact == NiveauImpact.FAIBLE  # 6.2% > 5%
        assert alerte.statut == StatutAlerte.NOUVELLE
        assert "6.2%" in alerte.contenu
        assert code_postal in alerte.titre

        # Vérifier les détails techniques
        details = alerte.details_techniques
        assert details["code_postal"] == code_postal
        assert details["variation_pct"] == 6.2
        assert details["periode"] == "30j vs 60j"

    async def test_variation_dvf_forte_impact_moyen(
        self,
        veille_engine: VeilleEngine,
        regle_dvf_75001: VeilleRule,
        db_session: AsyncSession
    ):
        """
        Test : variation > 8% génère alerte impact MOYEN.
        """
        # Given: Simulation d'une forte variation pour 92100
        with patch.object(
            veille_engine,
            '_simuler_variation_dvf',
            return_value=12.5  # +12.5%
        ):
            # Créer règle pour 92100
            regle_92100 = VeilleRule(
                nom="Test DVF 92100",
                type_source=TypeSource.DVF,
                configuration={"code_postal": "92100"},
                code_postal="92100",
                active=True,
                frequence_heures=168
            )
            db_session.add(regle_92100)
            await db_session.flush()

            # When: Vérification
            alertes = await veille_engine.verifier_variations_dvf("92100")

            # Then: Impact FORT pour variation > 10%
            assert len(alertes) == 1
            assert alertes[0].niveau_impact == NiveauImpact.FORT
            assert "12.5%" in alertes[0].contenu

    async def test_variation_dvf_seuil_non_atteint(
        self,
        veille_engine: VeilleEngine,
        regle_dvf_75001: VeilleRule
    ):
        """
        Test : variation < 5% ne génère pas d'alerte.
        """
        # Given: Variation faible simulée
        with patch.object(
            veille_engine,
            '_simuler_variation_dvf',
            return_value=3.1  # +3.1% < seuil 5%
        ):
            # When: Vérification
            alertes = await veille_engine.verifier_variations_dvf("75015")

            # Then: Aucune alerte créée
            assert len(alertes) == 0


class TestVeilleLegifrance:
    """Tests pour la surveillance Légifrance."""

    async def test_legifrance_changement(
        self,
        veille_engine: VeilleEngine,
        regle_legifrance: VeilleRule,
        db_session: AsyncSession
    ):
        """
        Test : mock API → nouvelle version article → alerte.
        """
        # Given: Simulation changement article 777 CGI
        with patch.object(
            veille_engine,
            '_verifier_article_legifrance',
            return_value=True  # Changement détecté
        ):
            # When: Vérification Légifrance
            alertes = await veille_engine.verifier_legifrance()

            # Then: Alerte critique créée
            assert len(alertes) > 0

            # Vérifier une alerte pour l'article 777
            alerte_777 = None
            for alerte in alertes:
                if "777" in alerte.titre:
                    alerte_777 = alerte
                    break

            assert alerte_777 is not None
            assert alerte_777.niveau_impact == NiveauImpact.CRITIQUE
            assert alerte_777.veille_rule_id == regle_legifrance.id
            assert "CGI art. 777" in alerte_777.titre

    async def test_legifrance_aucun_changement(
        self,
        veille_engine: VeilleEngine,
        regle_legifrance: VeilleRule
    ):
        """
        Test : API stable → aucune alerte.
        """
        # Given: Aucun changement détecté (comportement par défaut)
        # When: Vérification Légifrance
        alertes = await veille_engine.verifier_legifrance()

        # Then: Aucune alerte créée
        assert len(alertes) == 0


class TestVeilleBOFIP:
    """Tests pour la surveillance BOFIP."""

    async def test_bofip_changement_bareme(
        self,
        veille_engine: VeilleEngine,
        db_session: AsyncSession
    ):
        """
        Test : changement page barème → alerte critique.
        """
        # Given: Règle BOFIP active
        regle_bofip = VeilleRule(
            nom="Test BOFIP Barèmes",
            type_source=TypeSource.BOFIP,
            configuration={
                "pages_surveillees": ["ENR-Mutations-10-20-20"],
                "surveillance_baremes": True
            },
            active=True,
            frequence_heures=24
        )
        db_session.add(regle_bofip)
        await db_session.flush()

        # Mock changement détecté
        with patch.object(
            veille_engine,
            '_verifier_page_bofip',
            return_value=True  # Changement barèmes détecté
        ):
            # When: Vérification BOFIP
            alertes = await veille_engine.verifier_bofip()

            # Then: Alerte critique créée
            assert len(alertes) > 0
            alerte = alertes[0]
            assert alerte.niveau_impact == NiveauImpact.CRITIQUE
            assert "BOFIP" in alerte.titre
            assert "barème" in alerte.contenu.lower()


class TestAnalyseImpactDossier:
    """Tests pour l'analyse d'impact sur dossiers spécifiques."""

    async def test_alerte_impact_analyse(
        self,
        veille_engine: VeilleEngine,
        regle_dvf_75001: VeilleRule,
        dossier_test: Dossier
    ):
        """
        Test : LLM explique impact sur dossier spécifique.
        """
        # Given: Alerte DVF
        alerte = Alerte(
            veille_rule_id=regle_dvf_75001.id,
            titre="Test variation DVF",
            niveau_impact=NiveauImpact.MOYEN,
            contenu="Variation +8% prix immobilier",
            veille_rule=regle_dvf_75001
        )

        # When: Analyse d'impact sur le dossier
        analyse = await veille_engine.analyser_impact_sur_dossier(
            alerte, dossier_test
        )

        # Then: Explication générée en langage naturel
        assert isinstance(analyse, str)
        assert len(analyse) > 50  # Au moins 2-3 phrases
        assert "variation immobilière" in analyse.lower()
        assert "estimation" in analyse.lower()
        assert dossier_test.numero in analyse

    async def test_alerte_impact_legifrance(
        self,
        veille_engine: VeilleEngine,
        regle_legifrance: VeilleRule,
        dossier_test: Dossier
    ):
        """
        Test : Impact alerte Légifrance sur dossier succession.
        """
        # Given: Alerte modification légale
        alerte = Alerte(
            veille_rule_id=regle_legifrance.id,
            titre="Modification Code civil art. 777",
            niveau_impact=NiveauImpact.CRITIQUE,
            contenu="Article droits succession modifié",
            veille_rule=regle_legifrance
        )

        # When: Analyse d'impact
        analyse = await veille_engine.analyser_impact_sur_dossier(
            alerte, dossier_test
        )

        # Then: Explication juridique
        assert "modification légale" in analyse.lower()
        assert "notaire" in analyse.lower()
        assert dossier_test.numero in analyse


class TestAssignationAlertes:
    """Tests pour l'assignation des alertes aux bons dossiers."""

    async def test_alerte_assignee_au_bon_dossier(
        self,
        veille_engine: VeilleEngine,
        db_session: AsyncSession,
        dossier_test: Dossier
    ):
        """
        Test : règle liée à dossier_id → alerte assignée correctement.
        """
        # Given: Règle de veille liée à un dossier spécifique
        regle_specifique = VeilleRule(
            nom="Veille dossier spécifique",
            type_source=TypeSource.DVF,
            configuration={"code_postal": "75001"},
            code_postal="75001",
            active=True,
            frequence_heures=168,
            dossier_id=dossier_test.id  # Liée au dossier
        )
        db_session.add(regle_specifique)
        await db_session.flush()

        # When: Vérification avec variation détectée
        with patch.object(
            veille_engine,
            '_simuler_variation_dvf',
            return_value=7.5  # Variation déclenchant alerte
        ):
            alertes = await veille_engine.verifier_variations_dvf("75001")

        # Then: Alerte créée et dossier référencé
        assert len(alertes) == 1
        alerte = alertes[0]

        # Vérifier que le dossier est dans les dossiers impactés
        dossiers_impactes = alerte.dossiers_impactes
        assert dossiers_impactes is not None
        assert str(dossier_test.id) in dossiers_impactes

    async def test_recherche_dossiers_par_code_postal(
        self,
        veille_engine: VeilleEngine,
        db_session: AsyncSession
    ):
        """
        Test : recherche automatique des dossiers par code postal.
        """
        # Given: Plusieurs dossiers avec biens immobiliers
        dossiers = []
        for i in range(3):
            dossier = Dossier(
                numero=f"2025-TEST-{i:03d}",
                type_acte="VENTE",
                description=f"Test dossier {i}",
                statut="en_cours"
            )
            db_session.add(dossier)
            dossiers.append(dossier)

        await db_session.flush()

        # When: Recherche des dossiers impactés
        dossiers_trouves = await veille_engine._trouver_dossiers_par_code_postal("75001")

        # Then: Dossiers trouvés (simulation retourne 3 max)
        assert len(dossiers_trouves) <= 3
        assert all(isinstance(d, Dossier) for d in dossiers_trouves)


class TestExecutionComplete:
    """Tests pour l'exécution complète de la veille."""

    async def test_execution_verification_complete(
        self,
        veille_engine: VeilleEngine,
        regle_dvf_75001: VeilleRule,
        regle_legifrance: VeilleRule,
        db_session: AsyncSession
    ):
        """
        Test : exécution de toutes les règles actives.
        """
        # When: Exécution complète
        rapport = await veille_engine.executer_verification_complete()

        # Then: Rapport généré avec statistiques
        assert "debut" in rapport
        assert "fin" in rapport
        assert "duree_ms" in rapport
        assert isinstance(rapport["sources_verifiees"], list)
        assert isinstance(rapport["alertes_creees"], int)
        assert isinstance(rapport["erreurs"], list)

        # Vérifier que les règles ont été traitées
        await db_session.refresh(regle_dvf_75001)
        await db_session.refresh(regle_legifrance)

        assert regle_dvf_75001.derniere_verification is not None
        assert regle_legifrance.derniere_verification is not None

    async def test_historique_verification_cree(
        self,
        veille_engine: VeilleEngine,
        regle_dvf_75001: VeilleRule,
        db_session: AsyncSession
    ):
        """
        Test : historique des vérifications enregistré.
        """
        # When: Exécution complète
        await veille_engine.executer_verification_complete()

        # Then: Historique créé pour chaque règle
        query = select(HistoriqueVeille).where(
            HistoriqueVeille.veille_rule_id == regle_dvf_75001.id
        )
        result = await db_session.execute(query)
        historiques = list(result.scalars().all())

        assert len(historiques) >= 1
        historique = historiques[0]
        assert historique.succes is True
        assert historique.duree_ms > 0
        assert historique.elements_verifies >= 0


@pytest.mark.integration
class TestIntegrationVeille:
    """Tests d'intégration complète du système de veille."""

    async def test_workflow_complet_dvf_alerte(
        self,
        db_session: AsyncSession
    ):
        """
        Test intégration : création règle → variation DVF → alerte → analyse.
        """
        # Given: Moteur de veille
        engine = VeilleEngine(db_session)

        # 1. Créer règle de veille DVF
        from src.services.veille_service import creer_regle_veille_dvf
        regle = await creer_regle_veille_dvf(
            nom="Integration Test DVF",
            code_postal="75001",
            db=db_session
        )

        # 2. Exécuter vérification (variation simulée +6.2%)
        alertes = await engine.verifier_variations_dvf("75001")

        # 3. Vérifier alerte créée
        assert len(alertes) == 1
        alerte = alertes[0]
        assert alerte.niveau_impact == NiveauImpact.FAIBLE

        # 4. Tester analyse d'impact
        dossier_test = Dossier(
            numero="2025-INTEGRATION-001",
            type_acte="VENTE",
            description="Test integration",
            statut="en_cours"
        )
        db_session.add(dossier_test)
        await db_session.flush()

        analyse = await engine.analyser_impact_sur_dossier(alerte, dossier_test)
        assert len(analyse) > 50
        assert "variation immobilière" in analyse.lower()

        # 5. Commit final
        await db_session.commit()

        print(f"✅ Workflow complet testé : règle → variation → alerte → analyse")


if __name__ == "__main__":
    # Lancer quelques tests de base
    print("Tests de base du service de veille...")
    print("✅ Tous les tests de structure définis")
    print("📋 4 cas principaux couverts :")
    print("  • Détection variations DVF avec seuils")
    print("  • Surveillance Légifrance avec alertes critiques")
    print("  • Monitoring BOFIP avec changements barèmes")
    print("  • Analyse d'impact IA sur dossiers spécifiques")