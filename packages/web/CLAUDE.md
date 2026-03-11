# Frontend Web — Conventions Next.js

## Stack
Next.js 14 (App Router) + Tailwind CSS + TypeScript strict

## Structure
```
src/
  pages/       → routes Next.js
  components/
    ui/        → composants réutilisables (Button, Card, Input)
    forms/     → formulaires métier
    charts/    → graphiques (recharts)
    map/       → carte Leaflet
  hooks/       → custom hooks (useEstimation, useDossier)
  lib/         → api client, utils
```

## Règles
- Composants fonctionnels uniquement
- Strict TypeScript (pas de any)
- Hooks personnalisés pour la logique métier
- API calls via lib/api-client.ts (jamais fetch direct dans les composants)

## Connexion à l'API
```typescript
// lib/api-client.ts
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
```
