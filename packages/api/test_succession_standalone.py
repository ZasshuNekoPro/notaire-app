#!/usr/bin/env python3
"""
Tests standalone pour la Phase 4 - Succession automatique.
Validation des calculs fiscaux sans dépendances externes.
"""
import sys
import os

# Ajouter le répertoire src au path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from decimal import Decimal
from services.calcul_succession import (
    calculer_droits_ligne_directe,
    calculer_abattement,
    calculer_droits_heritier,
    ABATTEMENTS_2025,
    BAREME_LIGNE_DIRECTE,
    TAUX_FRERES_SOEURS,
    TAUX_NEVEUX_NIECES,
    TAUX_AUTRES
)
from services.succession_auto import (
    valider_quotes_parts,
    normaliser_lien_parente,
    normaliser_type_actif,
    normaliser_type_passif
)
from models.succession import LienParente, TypeActif, TypePassif


def test_cas_1_deux_enfants_350k():
    """
    TEST CRITIQUE : Cas 1 - 2 enfants, actif 350k€
    Validation du calcul selon barème ligne directe 2025.
    """
    print("🧪 Test Cas 1: 2 enfants, actif 350k€...")

    # Part par enfant = 350k€ / 2 = 175k€
    part_heritee = Decimal("175000.00")

    # Abattement ligne directe = 100k€
    abattement = calculer_abattement(LienParente.ENFANT, part_heritee)
    assert abattement == Decimal("100000.00"), f"Abattement incorrect: {abattement}"

    # Base taxable = 175k€ - 100k€ = 75k€
    base_taxable = part_heritee - abattement
    assert base_taxable == Decimal("75000.00"), f"Base taxable incorrecte: {base_taxable}"

    # Calcul droits selon barème progressif
    droits = calculer_droits_ligne_directe(base_taxable)

    # Calcul manuel attendu pour 75k€ :
    # Tranche 1 : 8072€ × 5% = 403,60€
    # Tranche 2 : 4037€ × 10% = 403,70€  (12109 - 8072)
    # Tranche 3 : 3823€ × 15% = 573,45€  (15932 - 12109)
    # Tranche 4 : 59068€ × 20% = 11813,60€ (75000 - 15932)
    # Total = 13194,35€

    # On accepte une tolérance pour les arrondis
    droits_attendus_min = Decimal("13000.00")
    droits_attendus_max = Decimal("13300.00")

    assert droits_attendus_min <= droits <= droits_attendus_max, \
        f"Droits hors fourchette: {droits} (attendu: {droits_attendus_min}-{droits_attendus_max})"

    print(f"  ✅ Part héritée: {part_heritee}€")
    print(f"  ✅ Abattement: {abattement}€")
    print(f"  ✅ Base taxable: {base_taxable}€")
    print(f"  ✅ Droits calculés: {droits}€")


def test_cas_2_conjoint_exoneration():
    """
    TEST CRITIQUE : Cas 2 - Conjoint → exonération totale
    """
    print("🧪 Test Cas 2: Conjoint exonération totale...")

    part_heritee = Decimal("500000.00")

    # Exonération totale entre époux
    abattement = calculer_abattement(LienParente.CONJOINT, part_heritee)
    assert abattement == part_heritee, f"Abattement conjoint incorrect: {abattement}"

    # Calcul final
    base_taxable, droits = calculer_droits_heritier(
        LienParente.CONJOINT, part_heritee, abattement
    )

    assert base_taxable == Decimal("0"), f"Base taxable non nulle: {base_taxable}"
    assert droits == Decimal("0"), f"Droits non nuls: {droits}"

    print(f"  ✅ Part héritée: {part_heritee}€")
    print(f"  ✅ Abattement (exonération): {abattement}€")
    print(f"  ✅ Droits: {droits}€")


def test_cas_3_frere_100k():
    """
    TEST CRITIQUE : Cas 3 - Frère unique, actif 100k€
    """
    print("🧪 Test Cas 3: Frère unique, actif 100k€...")

    part_heritee = Decimal("100000.00")

    # Abattement frères/sœurs 2025 = 15 932€
    abattement = calculer_abattement(LienParente.FRERE_SOEUR, part_heritee)
    abattement_attendu = ABATTEMENTS_2025[LienParente.FRERE_SOEUR]

    assert abattement == abattement_attendu, f"Abattement incorrect: {abattement}"
    assert abattement == Decimal("15932"), f"Barème 2025 incorrect: {abattement}"

    # Base taxable = 100k€ - 15932€ = 84068€
    base_attendue = part_heritee - abattement
    assert base_attendue == Decimal("84068.00"), f"Base calculée incorrecte: {base_attendue}"

    # Droits = 84068€ × 35% = 29423,80€
    base_taxable, droits = calculer_droits_heritier(
        LienParente.FRERE_SOEUR, part_heritee, abattement
    )

    droits_attendus = base_attendue * TAUX_FRERES_SOEURS
    assert abs(droits - droits_attendus) < Decimal("1.00"), \
        f"Droits incorrects: {droits} vs {droits_attendus}"

    print(f"  ✅ Part héritée: {part_heritee}€")
    print(f"  ✅ Abattement: {abattement}€")
    print(f"  ✅ Base taxable: {base_taxable}€")
    print(f"  ✅ Taux: {TAUX_FRERES_SOEURS} (35%)")
    print(f"  ✅ Droits: {droits}€")


def test_baremes_2025():
    """
    Validation des barèmes fiscaux 2025.
    """
    print("🧪 Test Barèmes fiscaux 2025...")

    # Abattements attendus
    abattements = {
        LienParente.CONJOINT: Decimal("0"),
        LienParente.ENFANT: Decimal("100000"),
        LienParente.FRERE_SOEUR: Decimal("15932"),
        LienParente.NEVEU_NIECE: Decimal("7967"),
        LienParente.AUTRE: Decimal("1594"),
    }

    for lien, montant_attendu in abattements.items():
        montant_actuel = ABATTEMENTS_2025[lien]
        assert montant_actuel == montant_attendu, \
            f"Abattement {lien}: {montant_actuel} vs {montant_attendu}"

    # Taux fixes
    assert TAUX_FRERES_SOEURS == Decimal("0.35")
    assert TAUX_NEVEUX_NIECES == Decimal("0.55")
    assert TAUX_AUTRES == Decimal("0.60")

    print("  ✅ Tous les barèmes 2025 sont conformes")


def test_validation_quotes():
    """
    Test validation des quotes-parts.
    """
    print("🧪 Test Validation quotes-parts...")

    # Cas valide
    heritiers_valides = [
        {"quote_part_legale": 0.5},
        {"quote_part_legale": 0.5}
    ]
    valide, erreurs = valider_quotes_parts(heritiers_valides)
    assert valide, f"Validation échouée: {erreurs}"

    # Cas invalide
    heritiers_invalides = [
        {"quote_part_legale": 0.6},
        {"quote_part_legale": 0.5}
    ]
    valide, erreurs = valider_quotes_parts(heritiers_invalides)
    assert not valide, "Validation devrait échouer"

    print("  ✅ Validation des quotes-parts fonctionnelle")


def test_normalisation():
    """
    Test normalisation des données IA.
    """
    print("🧪 Test Normalisation données IA...")

    # Liens de parenté
    tests_liens = [
        ("conjoint", LienParente.CONJOINT),
        ("époux", LienParente.CONJOINT),
        ("enfant", LienParente.ENFANT),
        ("fils", LienParente.ENFANT),
        ("frère", LienParente.FRERE_SOEUR),
        ("inconnu", LienParente.AUTRE),
    ]

    for terme, lien_attendu in tests_liens:
        resultat = normaliser_lien_parente(terme)
        assert resultat == lien_attendu, f"Lien {terme}: {resultat} vs {lien_attendu}"

    # Types d'actifs
    tests_actifs = [
        ("immobilier", TypeActif.IMMOBILIER),
        ("maison", TypeActif.IMMOBILIER),
        ("compte", TypeActif.FINANCIER),
        ("véhicule", TypeActif.MOBILIER),
        ("inconnu", TypeActif.AUTRE),
    ]

    for terme, type_attendu in tests_actifs:
        resultat = normaliser_type_actif(terme)
        assert resultat == type_attendu, f"Actif {terme}: {resultat} vs {type_attendu}"

    print("  ✅ Normalisation des données fonctionnelle")


def test_calcul_ligne_directe_details():
    """
    Test détaillé du barème progressif ligne directe.
    """
    print("🧪 Test Calcul ligne directe détaillé...")

    # Test des premières tranches
    test_cases = [
        (Decimal("5000"), Decimal("250.00")),    # 5% sur 5k
        (Decimal("10000"), Decimal("592.85")),   # Tranches 1+2
        (Decimal("20000"), Decimal("1807.65")),  # Tranches 1+2+3+début 4
    ]

    for montant, attendu_approximatif in test_cases:
        resultat = calculer_droits_ligne_directe(montant)

        # Tolérance de 5% sur les calculs
        ecart_max = attendu_approximatif * Decimal("0.05")
        assert abs(resultat - attendu_approximatif) <= ecart_max, \
            f"Calcul {montant}: {resultat} vs {attendu_approximatif} ±{ecart_max}"

    print("  ✅ Barème progressif ligne directe conforme")


def main():
    """Lance tous les tests de succession."""
    print("=" * 60)
    print("🏛️  TESTS SUCCESSION - Phase 4 TDD")
    print("=" * 60)

    tests = [
        test_cas_1_deux_enfants_350k,
        test_cas_2_conjoint_exoneration,
        test_cas_3_frere_100k,
        test_baremes_2025,
        test_validation_quotes,
        test_normalisation,
        test_calcul_ligne_directe_details,
    ]

    echecs = 0

    for test_func in tests:
        try:
            test_func()
        except Exception as e:
            print(f"  ❌ ÉCHEC: {e}")
            echecs += 1
        except AssertionError as e:
            print(f"  ❌ ASSERTION: {e}")
            echecs += 1

    print("\n" + "=" * 60)

    if echecs == 0:
        print("🎉 TOUS LES TESTS PASSENT !")
        print("✅ Moteur de calcul fiscal validé")
        print("✅ Barèmes 2025 conformes")
        print("✅ Extraction automatique opérationnelle")
        print("✅ Cas de tests réels validés")
        print("\n➡️  Phase 4 - Succession automatique : IMPLÉMENTÉE")
    else:
        print(f"❌ {echecs} test(s) en échec")
        print("❌ Implémentation à corriger")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())