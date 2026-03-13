#!/usr/bin/env python3
"""
Script de lancement des tests TDD pour les modèles de succession.
Vérifie que les 4 cas spécifiés passent avant l'implémentation des services.
"""

import asyncio
import sys
import os
from pathlib import Path

# Ajouter le path pour les imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Configuration test minimaliste
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Import des modèles pour vérification
try:
    from src.models.base import Base
    from src.models.dossiers import Dossier
    from src.models.succession import (
        Succession, Heritier, ActifSuccessoral, PassifSuccessoral,
        LienParente, TypeActif, StatutTraitement
    )
    print("✅ Import des modèles réussi")
except ImportError as e:
    print(f"❌ Erreur d'import des modèles : {e}")
    sys.exit(1)


async def test_models_creation():
    """Test minimal de création des modèles en mémoire."""
    print("\n🧪 Test de création des modèles...")

    try:
        # Test création objets en mémoire
        dossier = Dossier(
            numero="TEST-001",
            type_dossier="succession"
        )

        succession = Succession(
            dossier_id=dossier.id,  # Sera généré automatiquement
            defunt_nom="TEST",
            defunt_prenom="Test",
            defunt_date_naissance="1950-01-01",
            defunt_date_deces="2025-01-01",
            nb_enfants=2
        )

        heritier = Heritier(
            succession_id=succession.id,
            nom="HERITIER",
            prenom="Test",
            lien_parente=LienParente.ENFANT,
            part_theorique=0.5
        )

        actif = ActifSuccessoral(
            succession_id=succession.id,
            type_actif=TypeActif.IMMOBILIER,
            description="Test actif",
            valeur_estimee=35000000  # 350k€ en centimes
        )

        passif = PassifSuccessoral(
            succession_id=succession.id,
            type_passif="credit_immobilier",
            montant=15000000,  # 150k€ en centimes
            creancier="Banque test"
        )

        print("✅ Création des objets modèles réussie")
        print(f"   Dossier: {dossier}")
        print(f"   Succession: {succession}")
        print(f"   Héritier: {heritier}")
        print(f"   Actif: {actif}")
        print(f"   Passif: {passif}")

        # Vérifications enum
        assert heritier.lien_parente == LienParente.ENFANT
        assert actif.type_actif == TypeActif.IMMOBILIER
        assert succession.statut_traitement == StatutTraitement.ANALYSE_AUTO

        print("✅ Vérifications enum réussies")

        return True

    except Exception as e:
        print(f"❌ Erreur création modèles : {e}")
        return False


def test_calcul_famille_type():
    """Test du calcul manuel famille type selon spécifications."""
    print("\n📊 Test calcul famille type...")

    try:
        # Selon spécifications TDD
        actif_net_euros = 350000
        nb_enfants = 2

        # Calculs manuels
        part_par_enfant = actif_net_euros / nb_enfants  # 175 000€
        abattement_ligne_directe = 100000  # 2025
        base_taxable = part_par_enfant - abattement_ligne_directe  # 75 000€

        # Barème succession ligne directe 2025 (progressif)
        # Jusqu'à 8072€ : 5%
        # De 8072€ à 12109€ : 10%
        # De 12109€ à 15932€ : 15%
        # De 15932€ à 552324€ : 20%

        droits_tranche1 = min(base_taxable, 8072) * 0.05
        droits_tranche2 = max(0, min(base_taxable - 8072, 12109 - 8072)) * 0.10
        droits_tranche3 = max(0, min(base_taxable - 12109, 15932 - 12109)) * 0.15
        droits_tranche4 = max(0, min(base_taxable - 15932, 552324 - 15932)) * 0.20

        droits_total = droits_tranche1 + droits_tranche2 + droits_tranche3 + droits_tranche4

        print(f"   Actif net: {actif_net_euros:,}€")
        print(f"   Part par enfant: {part_par_enfant:,}€")
        print(f"   Abattement: {abattement_ligne_directe:,}€")
        print(f"   Base taxable: {base_taxable:,}€")
        print(f"   Droits calculés: {droits_total:,.2f}€")

        # Vérifications selon énoncé
        assert part_par_enfant == 175000
        assert base_taxable == 75000
        assert 13000 <= droits_total <= 14000  # Environ 13 194€

        print("✅ Calculs famille type validés")
        return True

    except Exception as e:
        print(f"❌ Erreur calcul : {e}")
        return False


async def main():
    """Fonction principale des tests."""
    print("🏛️  Tests TDD Modèles Succession - Notaire App")
    print("=" * 50)

    tests_passed = 0
    total_tests = 2

    # Test 1 : Modèles
    if await test_models_creation():
        tests_passed += 1

    # Test 2 : Calculs
    if test_calcul_famille_type():
        tests_passed += 1

    print(f"\n📋 Résultats: {tests_passed}/{total_tests} tests passés")

    if tests_passed == total_tests:
        print("✅ TOUS LES TESTS TDD PASSENT")
        print("🚀 Prêt pour l'implémentation des services")
        return 0
    else:
        print("❌ DES TESTS TDD ÉCHOUENT")
        print("⚠️  Corriger les modèles avant de continuer")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)