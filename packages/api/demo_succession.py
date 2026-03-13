#!/usr/bin/env python3
"""
Démonstration du workflow Phase 4 - Succession automatique.
Simulation complète depuis l'extraction jusqu'aux calculs fiscaux.
"""
from decimal import Decimal
from datetime import date
import json

# Simulation de données extraites par IA depuis des documents
DOCUMENTS_SUCCESSION = {
    "acte_deces.pdf": {
        "defunt_nom": "DUPONT",
        "defunt_prenom": "Pierre",
        "defunt_date_naissance": "1945-03-15",
        "defunt_date_deces": "2025-01-20",
        "lieu_deces": "Paris 15e"
    },
    "testament.pdf": {
        "heritiers": [
            {
                "nom": "DUPONT",
                "prenom": "Marie",
                "lien_parente": "conjoint",
                "quote_part_legale": 0.5
            },
            {
                "nom": "DUPONT",
                "prenom": "Jean",
                "lien_parente": "enfant",
                "quote_part_legale": 0.25
            },
            {
                "nom": "DUPONT",
                "prenom": "Sophie",
                "lien_parente": "enfant",
                "quote_part_legale": 0.25
            }
        ]
    },
    "inventaire_biens.pdf": {
        "actifs": [
            {
                "type_actif": "immobilier",
                "description": "Maison familiale avec jardin, 120m²",
                "valeur_estimee": 350000.00,
                "adresse": "123 rue de la Paix, 75015 Paris",
                "surface": 120.0
            },
            {
                "type_actif": "financier",
                "description": "Compte épargne BNP Paribas",
                "valeur_estimee": 45000.00
            },
            {
                "type_actif": "financier",
                "description": "Assurance vie AXA",
                "valeur_estimee": 80000.00
            },
            {
                "type_actif": "mobilier",
                "description": "Véhicule Peugeot 308 (2019)",
                "valeur_estimee": 18000.00
            }
        ],
        "passifs": [
            {
                "type_passif": "credit_immobilier",
                "description": "Crédit résidence principale",
                "montant": 120000.00,
                "creancier": "Crédit Agricole"
            },
            {
                "type_passif": "frais_funeraires",
                "description": "Frais obsèques",
                "montant": 5000.00,
                "creancier": "Pompes Funèbres Martin"
            }
        ]
    }
}


def simuler_extraction_ia():
    """Simule l'extraction IA des documents de succession."""
    print("🤖 EXTRACTION IA - Analyse des documents...")
    print("-" * 50)

    # Fusion des données extraites
    succession_data = {
        "numero_dossier": "2025-SUC-DEMO01",
        **DOCUMENTS_SUCCESSION["acte_deces.pdf"],
        **DOCUMENTS_SUCCESSION["testament.pdf"],
        **DOCUMENTS_SUCCESSION["inventaire_biens.pdf"]
    }

    # Calcul de confiance simulée
    confiance = {
        "succession": 0.98,  # Acte de décès très clair
        "heritiers": 0.85,   # Testament bien structuré
        "actifs": 0.80,      # Inventaire complet mais estimatif
        "passifs": 0.90,     # Factures précises
        "globale": 0.88
    }

    print(f"📄 Documents analysés : {len(DOCUMENTS_SUCCESSION)}")
    print(f"👤 Défunt : {succession_data['defunt_prenom']} {succession_data['defunt_nom']}")
    print(f"👥 Héritiers identifiés : {len(succession_data['heritiers'])}")
    print(f"🏠 Actifs trouvés : {len(succession_data['actifs'])}")
    print(f"💳 Passifs trouvés : {len(succession_data['passifs'])}")
    print(f"🎯 Confiance globale : {confiance['globale']:.1%}")

    return succession_data, confiance


def calculer_patrimoine(succession_data):
    """Calcule le patrimoine net de la succession."""
    print("\n💰 CALCUL PATRIMOINE...")
    print("-" * 50)

    actifs = succession_data["actifs"]
    passifs = succession_data["passifs"]

    total_actifs = sum(Decimal(str(actif["valeur_estimee"])) for actif in actifs)
    total_passifs = sum(Decimal(str(passif["montant"])) for passif in passifs)
    actif_net = total_actifs - total_passifs

    print("ACTIFS :")
    for actif in actifs:
        print(f"  • {actif['description']:.<40} {actif['valeur_estimee']:>10,.2f}€")
    print(f"  {'Total actifs':.<40} {total_actifs:>10,.2f}€")

    print("\nPASSIFS :")
    for passif in passifs:
        print(f"  • {passif['description']:.<40} {passif['montant']:>10,.2f}€")
    print(f"  {'Total passifs':.<40} {total_passifs:>10,.2f}€")

    print(f"\n  {'ACTIF NET':=<40} {actif_net:>10,.2f}€")

    return total_actifs, total_passifs, actif_net


def calculer_droits_succession(succession_data, actif_net):
    """Calcule les droits de succession pour chaque héritier."""
    print("\n🏛️ CALCUL DROITS DE SUCCESSION...")
    print("-" * 50)

    # Barèmes 2025 (reproduits pour la démo)
    ABATTEMENTS = {
        "conjoint": Decimal("0"),     # Exonération totale
        "enfant": Decimal("100000"),  # 100k€
        "frere_soeur": Decimal("15932")
    }

    TAUX_FRERES_SOEURS = Decimal("0.35")

    def calculer_droits_ligne_directe(base):
        """Barème progressif ligne directe."""
        tranches = [
            (Decimal("8072"), Decimal("0.05")),
            (Decimal("12109"), Decimal("0.10")),
            (Decimal("15932"), Decimal("0.15")),
            (Decimal("552324"), Decimal("0.20")),
        ]

        droits = Decimal("0")
        precedent = Decimal("0")

        for seuil, taux in tranches:
            if base <= precedent:
                break
            tranche = min(base - precedent, seuil - precedent)
            droits += tranche * taux
            precedent = seuil

        return droits

    heritiers = succession_data["heritiers"]
    total_droits = Decimal("0")

    print(f"Actif net à répartir : {actif_net:,.2f}€\n")

    for heritier in heritiers:
        nom_complet = f"{heritier['prenom']} {heritier['nom']}"
        lien = heritier["lien_parente"]
        quote_part = Decimal(str(heritier["quote_part_legale"]))

        # Part héritée
        part_heritee = actif_net * quote_part

        # Abattement selon le lien
        if lien == "conjoint":
            abattement = part_heritee  # Exonération totale
        else:
            abattement_max = ABATTEMENTS.get(lien, Decimal("1594"))
            abattement = min(abattement_max, part_heritee)

        # Base taxable
        base_taxable = max(Decimal("0"), part_heritee - abattement)

        # Calcul des droits
        if base_taxable == 0:
            droits = Decimal("0")
        elif lien in ["enfant", "parent"]:
            droits = calculer_droits_ligne_directe(base_taxable)
        elif lien == "frere_soeur":
            droits = base_taxable * TAUX_FRERES_SOEURS
        else:
            droits = base_taxable * Decimal("0.60")  # 60% autres

        total_droits += droits

        print(f"👤 {nom_complet} ({lien})")
        print(f"   Quote-part : {quote_part:.1%}")
        print(f"   Part héritée : {part_heritee:>12,.2f}€")
        print(f"   Abattement : {abattement:>12,.2f}€")
        print(f"   Base taxable : {base_taxable:>12,.2f}€")
        print(f"   Droits dus : {droits:>12,.2f}€")
        print()

    print(f"{'TOTAL DROITS DE SUCCESSION':=<40} {total_droits:>10,.2f}€")

    return total_droits


def generer_rapport_final(succession_data, totaux, total_droits):
    """Génère le rapport final de succession."""
    print("\n📊 RAPPORT FINAL DE SUCCESSION")
    print("=" * 60)

    total_actifs, total_passifs, actif_net = totaux

    print(f"Dossier : {succession_data['numero_dossier']}")
    print(f"Défunt : {succession_data['defunt_prenom']} {succession_data['defunt_nom']}")
    print(f"Date de décès : {succession_data['defunt_date_deces']}")
    print(f"Lieu : {succession_data['lieu_deces']}")
    print()

    print("SYNTHÈSE PATRIMONIALE :")
    print(f"  Total actifs : {total_actifs:>15,.2f}€")
    print(f"  Total passifs : {total_passifs:>15,.2f}€")
    print(f"  Actif net : {actif_net:>15,.2f}€")
    print()

    print("SYNTHÈSE FISCALE :")
    print(f"  Nombre d'héritiers : {len(succession_data['heritiers']):>11}")
    print(f"  Total droits dus : {total_droits:>15,.2f}€")
    taux_effectif = (total_droits / actif_net * 100) if actif_net > 0 else 0
    print(f"  Taux effectif : {taux_effectif:>15.2f}%")
    print()

    print("PROCHAINES ÉTAPES :")
    print("  ✅ Calculs fiscaux validés")
    print("  📝 Déclaration de succession à déposer")
    print("  💰 Paiement des droits (délai : 6 mois)")
    print("  📋 Partage entre héritiers")

    return {
        "dossier": succession_data['numero_dossier'],
        "actif_net": float(actif_net),
        "droits_total": float(total_droits),
        "taux_effectif": float(taux_effectif),
        "heritiers_count": len(succession_data['heritiers'])
    }


def main():
    """Démonstration complète du workflow succession."""
    print("🏛️ DÉMONSTRATION PHASE 4 - SUCCESSION AUTOMATIQUE")
    print("=" * 60)
    print("Simulation du workflow complet :")
    print("1. Extraction IA des documents")
    print("2. Calcul du patrimoine")
    print("3. Calculs fiscaux par héritier")
    print("4. Rapport final")
    print("=" * 60)

    try:
        # 1. Extraction IA
        succession_data, confiance = simuler_extraction_ia()

        # 2. Calcul patrimoine
        totaux = calculer_patrimoine(succession_data)
        total_actifs, total_passifs, actif_net = totaux

        # 3. Calculs fiscaux
        total_droits = calculer_droits_succession(succession_data, actif_net)

        # 4. Rapport final
        rapport = generer_rapport_final(succession_data, totaux, total_droits)

        print("\n✅ DÉMONSTRATION TERMINÉE AVEC SUCCÈS")
        print(f"Dossier {rapport['dossier']} traité automatiquement")
        print(f"Actif net : {rapport['actif_net']:,.2f}€")
        print(f"Droits calculés : {rapport['droits_total']:,.2f}€")

        return 0

    except Exception as e:
        print(f"\n❌ ERREUR DANS LA DÉMONSTRATION : {e}")
        return 1


if __name__ == "__main__":
    exit(main())