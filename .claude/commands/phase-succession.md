---
name: phase-succession
description: Lance le workflow complet de la Phase 4 — Analyse patrimoniale et succession automatique. Invoquer avec /phase-succession.
disable-model-invocation: true
---

# /phase-succession — Workflow Phase 4

Charge les skills `succession-fiscale` et `notaire-domain` avant de commencer.
Utilise l'agent `succession-analyst` pour les calculs fiscaux complexes.

## Séquence d'implémentation

### Étape 1 — Modèles de données
Créer `packages/api/src/models/succession.py` :
Tables : `successions`, `heritiers`, `actifs_successoraux`, `passifs_successoraux`
Migration Alembic immédiatement après.

### Étape 2 — Moteur de calcul fiscal
Créer `packages/api/src/services/calcul_succession.py` :
- Barèmes ligne directe, frères/sœurs, autres (taux 2025)
- Abattements légaux 2025
- `calculer_succession(succession_id)` → rapport complet par héritier

Tests OBLIGATOIRES avec cas réels :
```python
# Cas 1 : 2 enfants, actif 350k€ → droits ≈ 8 194€ / enfant
# Cas 2 : conjoint seul → exonération totale
# Cas 3 : frère unique, actif 100k€ → droits ≈ 28 934€
```

### Étape 3 — Extraction automatique par IA
Créer `packages/api/src/services/succession_auto.py` :
- Upload multi-documents (PDF/images)
- Extraction structurée via LLM (défunt, héritiers, biens)
- Seuil de confiance 0.7 → auto si OK, confirmation si < 0.7
- Estimation DVF automatique des biens immobiliers

### Étape 4 — Routes API
`packages/api/src/routers/successions.py` :
- `POST /successions/analyser-documents`
- `POST /successions/creer-auto`
- `GET /successions/{id}/rapport`
- `GET /successions/{id}/calcul-fiscal`

## Critère de succès
Upload d'un acte de décès fictif → dossier créé automatiquement avec calcul fiscal.
