#!/usr/bin/env python3
"""
Tests TDD pour le moteur de calcul des droits de succession
Barèmes 2025 - Ces tests DOIVENT tous passer exactement
"""
import pytest
from decimal import Decimal
from uuid import UUID, uuid4
from unittest.mock import Mock, AsyncMock, patch

# Import du service à créer
from packages.api.src.services.calcul_succession import (
    BaremesSuccession2025,
    calculer_droits_par_heritier,
    calculer_succession
)


class TestBaremesSuccession2025:
    """Tests des barèmes fiscaux 2025"""

    def test_cas1_famille_classique_2_enfants(self):
        """
        CAS 1 — Famille classique :
        Actif net 350 000€, 2 enfants, conjoint prédécédé
        Part enfant : 175 000€, abattement 100 000€, base taxable 75 000€
        Droits attendus par enfant : 8 194€ (barème ligne directe)
        """
        # Calcul détaillé barème ligne directe pour 75 000€ :
        # 0 à 8 072€ : 8 072 × 5% = 403,60€
        # 8 072 à 12 109€ : 4 037 × 10% = 403,70€
        # 12 109 à 15 932€ : 3 823 × 15% = 573,45€
        # 15 932 à 75 000€ : 59 068 × 20% = 11 813,60€
        # Total attendu : 403,60 + 403,70 + 573,45 + 11 813,60 = 13 194,35€

        # CORRECTION: Le calcul exact donne 13 194,35€ pas 8 194€

        actif_net_par_enfant = 175_000.0
        lien_parente = "enfant"
        est_handicape = False

        droits = calculer_droits_par_heritier(actif_net_par_enfant, lien_parente, est_handicape)

        # Droits attendus selon barème progressif exact
        assert abs(droits - 13_194.35) < 0.01, f"Attendu 13 194,35€, obtenu {droits}€"

    def test_cas2_conjoint_survivant_exoneration(self):
        """
        CAS 2 — Conjoint survivant :
        Actif net 500 000€, conjoint seul héritier
        Droits attendus : 0€ (exonération totale depuis 2007)
        """
        actif_net_conjoint = 500_000.0
        lien_parente = "conjoint"
        est_handicape = False

        droits = calculer_droits_par_heritier(actif_net_conjoint, lien_parente, est_handicape)

        assert droits == 0.0, f"Conjoint doit être exonéré, obtenu {droits}€"

    def test_cas3_frere_unique_bareme_specifique(self):
        """
        CAS 3 — Frère unique :
        Actif net 100 000€, frère unique
        Abattement 15 932€, base 84 068€
        Droits : 35% sur 24 430€ + 45% sur 59 638€ = 35 438,10€
        """
        # Calcul détaillé barème frères/sœurs :
        # Abattement : 15 932€
        # Base taxable : 100 000 - 15 932 = 84 068€
        # Tranche 1 : 24 430€ × 35% = 8 550,50€
        # Tranche 2 : (84 068 - 24 430) = 59 638€ × 45% = 26 837,10€
        # Total : 8 550,50 + 26 837,10 = 35 387,60€

        actif_net_frere = 100_000.0
        lien_parente = "frere_soeur"
        est_handicape = False

        droits = calculer_droits_par_heritier(actif_net_frere, lien_parente, est_handicape)

        # Vérifier le calcul exact barème frères/sœurs
        assert abs(droits - 35_387.60) < 0.01, f"Attendu 35 387,60€, obtenu {droits}€"

    def test_cas4_enfant_handicape_abattements_cumules(self):
        """
        CAS 4 — Personne handicapée :
        Enfant + handicap : abattements cumulables (100 000 + 159 325 = 259 325€)
        Actif 200 000€ → base taxable 200 000 - 259 325 = 0€ (négatif)
        Droits : 0€
        """
        actif_net_enfant_handicape = 200_000.0
        lien_parente = "enfant"
        est_handicape = True

        droits = calculer_droits_par_heritier(actif_net_enfant_handicape, lien_parente, est_handicape)

        assert droits == 0.0, f"Enfant handicapé avec abattement total, obtenu {droits}€"

    def test_cas4_bis_enfant_handicape_avec_droits(self):
        """
        CAS 4 bis — Enfant handicapé avec droits à payer :
        Actif 300 000€, abattement total 259 325€
        Base taxable : 40 675€
        Droits ligne directe sur 40 675€
        """
        actif_net_enfant_handicape = 300_000.0
        lien_parente = "enfant"
        est_handicape = True

        droits = calculer_droits_par_heritier(actif_net_enfant_handicape, lien_parente, est_handicape)

        # Base taxable : 300 000 - 259 325 = 40 675€
        # Barème ligne directe : 0 à 8 072€ × 5% + 8 072 à 12 109€ × 10% + ...
        # Calcul : 403,60 + 403,70 + 573,45 + 5 659,00 = 7 039,75€
        droits_attendus = 2033.75  # Calcul sur 40 675€
        assert abs(droits - droits_attendus) < 1.0, f"Attendu ~{droits_attendus}€, obtenu {droits}€"

    def test_autres_heritiers_taux_60_pourcent(self):
        """
        Test taux 60% pour les non-parents
        """
        actif_net = 50_000.0
        lien_parente = "autre"
        est_handicape = False

        droits = calculer_droits_par_heritier(actif_net, lien_parente, est_handicape)

        # Abattement autre : 1 594€
        # Base : 50 000 - 1 594 = 48 406€
        # Droits : 48 406 × 60% = 29 043,60€
        assert abs(droits - 29_043.60) < 0.01, f"Attendu 29 043,60€, obtenu {droits}€"


class TestCalculSuccessionComplete:
    """Tests du calcul complet d'une succession"""

    @pytest.mark.asyncio
    async def test_calcul_succession_famille_2_enfants(self):
        """
        Test intégration complète : succession avec 2 enfants
        """
        succession_id = uuid4()

        # Mock de la base de données
        mock_succession = Mock()
        mock_succession.id = succession_id
        mock_succession.defunt_nom = "Martin"
        mock_succession.heritiers = [
            Mock(nom="Martin", prenom="Pierre", lien_parente="enfant", part_theorique=Decimal('0.5000')),
            Mock(nom="Martin", prenom="Julie", lien_parente="enfant", part_theorique=Decimal('0.5000'))
        ]
        mock_succession.actifs = [
            Mock(type_actif="immobilier", valeur_estimee=25_000_000),  # 250k€ en centimes
            Mock(type_actif="compte_bancaire", valeur_estimee=10_000_000)  # 100k€ en centimes
        ]
        mock_succession.passifs = [
            Mock(type_passif="dette", montant=0)  # Pas de dettes
        ]

        # Mock de la session DB
        mock_db = AsyncMock()

        with patch('packages.api.src.services.calcul_succession.get_succession_by_id') as mock_get:
            mock_get.return_value = mock_succession

            result = await calculer_succession(succession_id, mock_db)

            # Vérifications
            assert result.actif_brut == 350_000.0  # 250k + 100k
            assert result.passif_total == 0.0
            assert result.actif_net == 350_000.0
            assert len(result.calculs_par_heritier) == 2

            # Chaque enfant reçoit 175k€ → droits 13 194,35€
            for calcul in result.calculs_par_heritier:
                assert calcul.part_nette == 175_000.0
                assert abs(calcul.droits_succession - 13_194.35) < 0.01

    @pytest.mark.asyncio
    async def test_calcul_succession_conjoint_seul(self):
        """
        Test succession conjoint seul (exonération totale)
        """
        succession_id = uuid4()

        mock_succession = Mock()
        mock_succession.heritiers = [
            Mock(nom="Martin", prenom="Marie", lien_parente="conjoint", part_theorique=Decimal('1.0000'))
        ]
        mock_succession.actifs = [
            Mock(valeur_estimee=50_000_000)  # 500k€
        ]
        mock_succession.passifs = []

        mock_db = AsyncMock()

        with patch('packages.api.src.services.calcul_succession.get_succession_by_id') as mock_get:
            mock_get.return_value = mock_succession

            result = await calculer_succession(succession_id, mock_db)

            assert result.actif_net == 500_000.0
            assert len(result.calculs_par_heritier) == 1
            assert result.calculs_par_heritier[0].droits_succession == 0.0

    def test_abattements_constants_2025(self):
        """
        Vérification des abattements 2025
        """
        baremes = BaremesSuccession2025()

        assert baremes.get_abattement("enfant") == 100_000
        assert baremes.get_abattement("conjoint") == float('inf')
        assert baremes.get_abattement("frere_soeur") == 15_932
        assert baremes.get_abattement("neveu_niece") == 7_967
        assert baremes.get_abattement("autre") == 1_594
        assert baremes.get_abattement("handicap") == 159_325


if __name__ == "__main__":
    # Tests en mode standalone
    pytest.main([__file__, "-v", "--tb=short"])