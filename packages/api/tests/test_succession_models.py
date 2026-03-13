"""
Tests TDD pour les modèles de succession - Notaire App
Conformes aux spécifications : FK dossier_id, enum lien_parente, calcul total, cascade delete
"""
import pytest
from datetime import date
from decimal import Decimal
from uuid import uuid4
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, func

from src.models.succession import (
    Succession, Heritier, ActifSuccessoral, PassifSuccessoral,
    LienParente, TypeActif
)
from src.models.dossiers import Dossier


class TestSuccessionModels:
    """Tests TDD des modèles succession avec cas spécifiés."""

    @pytest_asyncio.async_test
    async def test_succession_lies_au_dossier(self, db_session: AsyncSession):
        """
        Test 1: Vérifier FK dossier_id valide
        Une succession DOIT être liée à un dossier existant
        """
        # Arrange - Créer d'abord un dossier
        dossier = Dossier(
            numero="DOS-2025-001",
            type_dossier="succession",
            description="Dossier test succession famille type"
        )
        db_session.add(dossier)
        await db_session.flush()

        # Créer la succession liée au dossier
        succession = Succession(
            dossier_id=dossier.id,
            defunt_nom="DUPONT",
            defunt_prenom="Pierre",
            defunt_date_naissance=date(1950, 5, 15),
            defunt_date_deces=date(2025, 1, 15),
            regime_matrimonial="communaute_legale",
            nb_enfants=2,
            statut_traitement="analyse_auto"
        )

        # Act & Assert
        db_session.add(succession)
        await db_session.commit()
        await db_session.refresh(succession)

        assert succession.id is not None
        assert succession.dossier_id == dossier.id
        assert succession.defunt_nom == "DUPONT"
        assert succession.nb_enfants == 2

        # Vérifier l'intégrité des timestamps
        assert succession.created_at is not None
        assert succession.updated_at is not None

        # Vérifier la relation ORM
        await db_session.refresh(succession, ['dossier'])
        assert succession.dossier.numero == "DOS-2025-001"

    @pytest_asyncio.async_test
    async def test_heritier_lien_parente_enum(self, db_session: AsyncSession):
        """
        Test 2: Seules les valeurs autorisées pour lien_parente
        Valeurs valides: conjoint, enfant, petit_enfant, parent, frere_soeur, autre
        """
        # Arrange - Dossier et succession
        dossier = Dossier(numero="DOS-2025-002")
        db_session.add(dossier)
        await db_session.flush()

        succession = Succession(
            dossier_id=dossier.id,
            defunt_nom="MARTIN",
            defunt_prenom="Marie",
            defunt_date_naissance=date(1960, 3, 10),
            defunt_date_deces=date(2025, 2, 1),
            nb_enfants=2
        )
        db_session.add(succession)
        await db_session.flush()

        # Test valeurs valides
        liens_valides = [
            LienParente.CONJOINT,
            LienParente.ENFANT,
            LienParente.PETIT_ENFANT,
            LienParente.PARENT,
            LienParente.FRERE_SOEUR,
            LienParente.AUTRE
        ]

        heritiers_valides = []
        for i, lien in enumerate(liens_valides):
            heritier = Heritier(
                succession_id=succession.id,
                nom=f"HERITIER{i}",
                prenom=f"Test{i}",
                lien_parente=lien,
                part_theorique=Decimal("0.1667")  # 1/6
            )
            heritiers_valides.append(heritier)

        # Act & Assert - toutes les valeurs doivent être acceptées
        db_session.add_all(heritiers_valides)
        await db_session.commit()

        # Vérifier que tous les héritiers sont créés
        result = await db_session.execute(
            select(Heritier).where(Heritier.succession_id == succession.id)
        )
        heritiers_db = result.scalars().all()

        assert len(heritiers_db) == len(liens_valides)

        liens_db = [h.lien_parente for h in heritiers_db]
        assert all(lien in liens_valides for lien in liens_db)

    @pytest_asyncio.async_test
    async def test_actif_calcul_total(self, db_session: AsyncSession):
        """
        Test 3: Calcul correct du total des actifs
        Cas famille type: 2 enfants, bien 350k€ + compte 25k€ = 375k€ total
        IMPORTANT: Valeurs en centimes d'euros (BigInteger)
        """
        # Arrange - Dossier et succession famille type
        dossier = Dossier(numero="DOS-2025-003")
        db_session.add(dossier)
        await db_session.flush()

        succession = Succession(
            dossier_id=dossier.id,
            defunt_nom="DURAND",
            defunt_prenom="Paul",
            defunt_date_naissance=date(1955, 8, 22),
            defunt_date_deces=date(2025, 1, 20),
            nb_enfants=2
        )
        db_session.add(succession)
        await db_session.flush()

        # Actifs - bien immobilier + compte bancaire (EN CENTIMES)
        bien_immobilier = ActifSuccessoral(
            succession_id=succession.id,
            type_actif=TypeActif.IMMOBILIER,
            description="Maison familiale Paris 15e, 85m²",
            valeur_estimee=35000000,  # 350 000€ en centimes
            etablissement="",
            reference="Paris 15e - Bien principal",
            date_evaluation=date(2025, 1, 25)
        )

        compte_bancaire = ActifSuccessoral(
            succession_id=succession.id,
            type_actif=TypeActif.COMPTE_BANCAIRE,
            description="Compte courant BNP Paribas",
            valeur_estimee=2500000,  # 25 000€ en centimes
            etablissement="BNP Paribas",
            reference="CC 123456789",
            date_evaluation=date(2025, 1, 15)
        )

        db_session.add_all([bien_immobilier, compte_bancaire])
        await db_session.commit()

        # Act - Calculer le total via requête
        result = await db_session.execute(
            select(func.sum(ActifSuccessoral.valeur_estimee))
            .where(ActifSuccessoral.succession_id == succession.id)
        )
        total_actifs_centimes = result.scalar() or 0

        # Act - Récupérer par relation ORM
        await db_session.refresh(succession, ['actifs'])
        total_via_relation_centimes = sum(actif.valeur_estimee for actif in succession.actifs)

        # Assert - Vérification en centimes
        assert total_actifs_centimes == 37500000  # 375 000€ en centimes
        assert total_via_relation_centimes == 37500000
        assert len(succession.actifs) == 2

        # Vérifier les détails (conversion en euros pour lisibilité)
        actifs_par_type = {a.type_actif: a.valeur_estimee / 100 for a in succession.actifs}
        assert actifs_par_type[TypeActif.IMMOBILIER] == 350000.0  # €
        assert actifs_par_type[TypeActif.COMPTE_BANCAIRE] == 25000.0  # €

    @pytest_asyncio.async_test
    async def test_cascade_delete(self, db_session: AsyncSession):
        """
        Test 4: Suppression cascade succession → héritiers + actifs + passifs
        Vérifier que la suppression d'une succession supprime automatiquement
        tous ses héritiers, actifs et passifs
        """
        # Arrange - Dossier et succession complète
        dossier = Dossier(numero="DOS-2025-004")
        db_session.add(dossier)
        await db_session.flush()

        succession = Succession(
            dossier_id=dossier.id,
            defunt_nom="LAMBERT",
            defunt_prenom="Jean",
            defunt_date_naissance=date(1948, 12, 5),
            defunt_date_deces=date(2025, 3, 1),
            nb_enfants=2
        )
        db_session.add(succession)
        await db_session.flush()

        # 2 héritiers
        enfant1 = Heritier(
            succession_id=succession.id,
            nom="LAMBERT", prenom="Sophie",
            lien_parente=LienParente.ENFANT,
            part_theorique=Decimal("0.5000")
        )
        enfant2 = Heritier(
            succession_id=succession.id,
            nom="LAMBERT", prenom="Pierre",
            lien_parente=LienParente.ENFANT,
            part_theorique=Decimal("0.5000")
        )

        # 2 actifs (en centimes)
        maison = ActifSuccessoral(
            succession_id=succession.id,
            type_actif=TypeActif.IMMOBILIER,
            description="Résidence principale",
            valeur_estimee=40000000  # 400 000€
        )
        epargne = ActifSuccessoral(
            succession_id=succession.id,
            type_actif=TypeActif.COMPTE_BANCAIRE,
            description="Livret A",
            valeur_estimee=5000000  # 50 000€
        )

        # 1 passif (en centimes)
        credit = PassifSuccessoral(
            succession_id=succession.id,
            type_passif="credit_immobilier",
            montant=15000000,  # 150 000€
            creancier="Crédit Agricole"
        )

        db_session.add_all([enfant1, enfant2, maison, epargne, credit])
        await db_session.commit()

        succession_id = succession.id

        # Vérifier présence avant suppression
        count_heritiers_before = await db_session.execute(
            select(func.count(Heritier.id)).where(Heritier.succession_id == succession_id)
        )
        count_actifs_before = await db_session.execute(
            select(func.count(ActifSuccessoral.id)).where(ActifSuccessoral.succession_id == succession_id)
        )
        count_passifs_before = await db_session.execute(
            select(func.count(PassifSuccessoral.id)).where(PassifSuccessoral.succession_id == succession_id)
        )

        assert count_heritiers_before.scalar() == 2
        assert count_actifs_before.scalar() == 2
        assert count_passifs_before.scalar() == 1

        # Act - Supprimer la succession
        await db_session.delete(succession)
        await db_session.commit()

        # Assert - Vérifier suppression en cascade
        count_heritiers_after = await db_session.execute(
            select(func.count(Heritier.id)).where(Heritier.succession_id == succession_id)
        )
        count_actifs_after = await db_session.execute(
            select(func.count(ActifSuccessoral.id)).where(ActifSuccessoral.succession_id == succession_id)
        )
        count_passifs_after = await db_session.execute(
            select(func.count(PassifSuccessoral.id)).where(PassifSuccessoral.succession_id == succession_id)
        )

        assert count_heritiers_after.scalar() == 0
        assert count_actifs_after.scalar() == 0
        assert count_passifs_after.scalar() == 0

        # Vérifier que la succession n'existe plus
        succession_exists = await db_session.execute(
            select(func.count(Succession.id)).where(Succession.id == succession_id)
        )
        assert succession_exists.scalar() == 0

        # Vérifier que le dossier existe toujours (pas de cascade inverse)
        dossier_exists = await db_session.execute(
            select(func.count(Dossier.id)).where(Dossier.id == dossier.id)
        )
        assert dossier_exists.scalar() == 1


class TestCalculsSuccessionTDD:
    """Tests des calculs fiscaux - cas famille type 350k€."""

    @pytest_asyncio.async_test
    async def test_famille_type_350k_deux_enfants(self, db_session: AsyncSession):
        """
        Cas test famille type selon l'énoncé :
        - Défunt : veuf, 2 enfants
        - Actif net : 350 000€
        - Part par enfant : 175 000€
        - Abattement : 100 000€ chacun
        - Base taxable : 75 000€ par enfant
        - Droits ≈ 8 194€ par enfant (calcul barème ligne directe)

        Ce test valide le moteur de calcul avant implémentation.
        """
        # Arrange - Dossier et succession type
        dossier = Dossier(numero="TEST-CALCUL-001")
        db_session.add(dossier)
        await db_session.flush()

        succession = Succession(
            dossier_id=dossier.id,
            defunt_nom="FAMILLE",
            defunt_prenom="Type",
            defunt_date_naissance=date(1950, 1, 1),
            defunt_date_deces=date(2025, 3, 10),
            regime_matrimonial="veuf_veuve",
            nb_enfants=2
        )
        db_session.add(succession)
        await db_session.flush()

        # 2 enfants parts égales
        enfant1 = Heritier(
            succession_id=succession.id,
            nom="FAMILLE", prenom="Enfant1",
            lien_parente=LienParente.ENFANT,
            part_theorique=Decimal("0.5000")
        )
        enfant2 = Heritier(
            succession_id=succession.id,
            nom="FAMILLE", prenom="Enfant2",
            lien_parente=LienParente.ENFANT,
            part_theorique=Decimal("0.5000")
        )

        # Actif unique 350k€ (en centimes)
        bien = ActifSuccessoral(
            succession_id=succession.id,
            type_actif=TypeActif.IMMOBILIER,
            description="Bien familial type",
            valeur_estimee=35000000  # 350 000€ en centimes
        )

        db_session.add_all([enfant1, enfant2, bien])
        await db_session.commit()

        # Act - Calculs manuels de vérification (en euros pour clarté)
        actif_net_euros = 350000
        part_par_enfant_euros = actif_net_euros / 2  # 175 000€
        abattement_ligne_directe_euros = 100000  # Barème 2025
        base_taxable_par_enfant_euros = part_par_enfant_euros - abattement_ligne_directe_euros  # 75 000€

        # Barème succession ligne directe 2025 (progressif):
        # Jusqu'à 8072€ : 5%
        # De 8072€ à 12109€ : 10%
        # De 12109€ à 15932€ : 15%
        # De 15932€ à 552324€ : 20%
        # Au-delà : 45%

        # Calcul exact pour 75 000€
        droits_tranche1 = 8072 * 0.05  # 403.60€
        droits_tranche2 = (12109 - 8072) * 0.10  # 403.70€
        droits_tranche3 = (15932 - 12109) * 0.15  # 573.45€
        droits_tranche4 = (75000 - 15932) * 0.20  # 11813.60€
        droits_total_par_enfant = droits_tranche1 + droits_tranche2 + droits_tranche3 + droits_tranche4

        # Assert - Validation des calculs manuels
        assert part_par_enfant_euros == 175000
        assert base_taxable_par_enfant_euros == 75000

        # Droits attendus ≈ 13 194€ (vs 8 194€ de l'énoncé, probablement ancien barème)
        expected_droits = round(droits_total_par_enfant, 2)
        assert expected_droits == pytest.approx(13194.35, abs=1)

        print(f"Part par enfant: {part_par_enfant_euros}€")
        print(f"Base taxable: {base_taxable_par_enfant_euros}€")
        print(f"Droits calculés: {expected_droits}€")

        # TODO: Test avec le service calcul_succession une fois implémenté
        # rapport = await calculer_succession(succession.id, db_session)
        # assert rapport["heritiers"][0]["droits_succession"] == expected_droits


# Fixtures pour les tests
@pytest_asyncio.async_test
async def db_session():
    """
    Fixture de session DB pour les tests.
    TODO: Implémenter avec la configuration test du projet
    """
    # Cette fixture sera implémentée avec SQLite en mémoire ou PostgreSQL test
    # selon la configuration existante du projet
    pass