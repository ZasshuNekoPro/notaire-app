---
name: notaire-domain
description: Connaissance spécialisée du domaine notarial français. Charge automatiquement cette skill quand le code concerne des actes notariaux, successions, donations, ventes immobilières, droit de la famille, fiscalité successorale, ou quand l'utilisateur mentionne des termes comme notaire, acte, succession, héritier, défunt, patrimoine, donation, SCI, régime matrimonial. Active aussi pour toute question sur le Code civil, les barèmes de droits de succession, ou la rédaction d'actes authentiques.
---

# Domaine Notarial Français — Référentiel Métier

## Types d'actes principaux

| Acte | Code | Délai moyen | Complexité |
|------|------|-------------|------------|
| Vente immobilière | VENTE | 3 mois | Moyenne |
| Succession | SUCC | 6-12 mois | Haute |
| Donation | DON | 1 mois | Moyenne |
| Testament | TEST | Variable | Haute |
| Bail emphytéotique | BAIL | 2 mois | Haute |
| SCI constitution | SCI | 1 mois | Moyenne |
| PACS | PACS | 2 semaines | Faible |
| Contrat de mariage | MARIAGE | 1 mois | Moyenne |

## Structure d'une succession française

```
Succession ouverte à la date du décès
│
├── Actif brut
│   ├── Immobilier (valeur vénale)
│   ├── Comptes bancaires (solde au jour du décès)
│   ├── Assurances-vie (selon bénéficiaires)
│   ├── Valeurs mobilières
│   └── Mobilier (forfait 5% ou inventaire)
│
├── Passif
│   ├── Dettes du défunt
│   ├── Frais funéraires (forfait 1 500€)
│   └── Frais de dernière maladie
│
└── Actif net taxable = Actif brut - Passif
```

## Barèmes droits de succession 2025 (art. 777 CGI)

### En ligne directe (enfants, petits-enfants)
| Tranche | Taux |
|---------|------|
| < 8 072 € | 5% |
| 8 072 € – 12 109 € | 10% |
| 12 109 € – 15 932 € | 15% |
| 15 932 € – 552 324 € | 20% |
| 552 324 € – 902 838 € | 30% |
| 902 838 € – 1 805 677 € | 40% |
| > 1 805 677 € | 45% |

### Entre frères et sœurs
- ≤ 24 430 € : 35%
- > 24 430 € : 45%

### Autres (oncle, neveu, non-parents)
- Parents jusqu'au 4e degré : 55%
- Au-delà ou non-parents : 60%

## Abattements légaux 2025

| Bénéficiaire | Abattement |
|---|---|
| Enfant (par enfant) | 100 000 € |
| Conjoint / partenaire PACS | Exonération totale |
| Frère / sœur | 15 932 € |
| Neveu / nièce | 7 967 € |
| Personne handicapée | 159 325 € (cumulable) |
| Petit-enfant (par représentation) | Part de l'enfant prédécédé |

## Règles métier critiques

1. **Réserve héréditaire** : les enfants ont une part incompressible
   - 1 enfant : 1/2 de la succession
   - 2 enfants : 2/3
   - 3 enfants et + : 3/4

2. **Rapport des donations** : les donations antérieures réduisent la part

3. **Assurance-vie** : hors succession si bénéficiaire désigné (sauf primes manifestement exagérées)

4. **Délai de déclaration** : 6 mois en France, 12 mois à l'étranger

5. **Option des héritiers** : acceptation pure, sous bénéfice d'inventaire, ou renonciation

## Sources légales à citer

- Code civil : art. 720 à 892 (successions), art. 893 à 1 100 (libéralités)
- Code général des impôts : art. 750 ter à 806
- Légifrance : https://www.legifrance.gouv.fr
- BOFIP : https://bofip.impots.gouv.fr (ENR - Mutations à titre gratuit)

## Voir aussi

- `references/actes-types.md` : structure des actes courants
- `references/jurisprudence-cles.md` : décisions importantes
