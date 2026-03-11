---
name: succession-fiscale
description: Calcul des droits de succession, analyse patrimoniale automatisée, et création de dossiers de succession par IA. Active pour tout ce qui concerne le module packages/api/src/services/calcul_succession.py, les tables successions/heritiers/actifs_successoraux, le calcul des droits de mutation à titre gratuit, l'analyse de documents (acte de décès, livret de famille), ou quand l'utilisateur parle de défunt, héritier, actif successoral, déclaration de succession, droits à payer. Active aussi pour la génération automatique de dossiers par upload de documents.
allowed-tools: Bash, Read, Write
---

# Succession Fiscale — Moteur de Calcul

## Algorithme de calcul des droits

```python
def calculer_droits_succession(
    actif_net: float,
    lien_parente: str,
    abattement: float
) -> float:
    """
    Calcule les droits de succession pour un héritier.

    Args:
        actif_net: Part nette revenant à l'héritier
        lien_parente: 'enfant'|'conjoint'|'frere_soeur'|'autre'
        abattement: Abattement légal applicable

    Returns:
        Montant des droits à payer
    """
    # 1. Base taxable après abattement
    base = max(0, actif_net - abattement)
    if base == 0:
        return 0.0

    # 2. Application du barème progressif
    if lien_parente in ('enfant', 'petit_enfant', 'parent'):
        return _bareme_ligne_directe(base)
    elif lien_parente == 'conjoint':
        return 0.0  # Exonération totale depuis 2007
    elif lien_parente == 'frere_soeur':
        return _bareme_freres_soeurs(base)
    else:
        return base * 0.60  # Tiers et non-parents

def _bareme_ligne_directe(base: float) -> float:
    tranches = [
        (8072,    0.05),
        (12109,   0.10),
        (15932,   0.15),
        (552324,  0.20),
        (902838,  0.30),
        (1805677, 0.40),
        (float('inf'), 0.45),
    ]
    droits = 0.0
    precedent = 0
    for plafond, taux in tranches:
        if base <= precedent:
            break
        tranche = min(base, plafond) - precedent
        droits += tranche * taux
        precedent = plafond
    return droits
```

## Abattements 2025

```python
ABATTEMENTS = {
    'enfant':       100_000,
    'conjoint':     float('inf'),  # Exonération totale
    'frere_soeur':  15_932,
    'neveu_niece':  7_967,
    'autre':        1_594,
    'handicap':     159_325,       # Cumulable avec l'abattement principal
}
```

## Extraction automatique depuis documents

### Documents acceptés
- **Acte de décès** : nom/prénoms défunt, date, lieu
- **Livret de famille** : liste héritiers, liens de parenté
- **Relevés bancaires** : estimation comptes (solde affiché)
- **Titre de propriété** : adresse bien immobilier, surface

### Prompt d'extraction
```python
EXTRACTION_PROMPT = """
Extrais les informations suivantes du document (JSON strict, null si absent) :
{
  "defunt": {
    "nom": "", "prenom": "", "date_naissance": "YYYY-MM-DD",
    "date_deces": "YYYY-MM-DD", "lieu_deces": ""
  },
  "heritiers": [
    { "nom": "", "prenom": "", "lien_parente": "enfant|conjoint|frere_soeur|autre" }
  ],
  "biens_immobiliers": [
    { "adresse": "", "surface_m2": null, "type": "appartement|maison" }
  ],
  "comptes_bancaires": [
    { "etablissement": "", "solde_estime": null }
  ],
  "confidence": 0.0
}
"""
```

## Flux de création automatique

```
Upload documents (PDF/images)
    ↓ extraction IA par document
données structurées + confidence score
    ↓ si confidence > 0.7 → création auto
    ↓ si confidence ≤ 0.7 → demande confirmation notaire
Dossier créé + héritiers + actifs
    ↓ estimer_actif_immobilier() pour chaque bien
valorisation DVF automatique
    ↓ calculer_droits_succession()
rapport fiscal complet
    ↓ créer règle de veille
surveillance automatique activée
```
