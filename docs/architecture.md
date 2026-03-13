# Architecture — Décisions techniques

## ADR-001 — Abstraction multi-provider IA
Toute interaction LLM passe par `ai-core/src/providers/`.
Interface : `BaseAIProvider` avec `complete()`, `stream()`, `embed()`.
Provider actif : défini par `AI_PROVIDER` dans `.env`.

## ADR-002 — pgvector pour les embeddings RAG
PostgreSQL + pgvector. Évite un service vectoriel séparé.
Dimension : 768 (nomic-embed-text) ou 1536 (OpenAI).

## ADR-003 — Format Parquet pour DVF
10x plus compact que CSV, requêtes analytiques 50x plus rapides avec DuckDB.

## ADR-004 — Embeddings via Ollama en mode local
`nomic-embed-text` via Ollama quand `AI_PROVIDER=ollama`.
Fallback : OpenAI `text-embedding-3-small` si `AI_PROVIDER=openai`.

## ADR-005 — Signature électronique avec provider abstraction
Pattern similaire à `ai-core` : `BaseSignatureProvider` avec interface unifiée.
Providers : `SignatureSimuleeProvider` (tests/démo), `YousignProvider` (production).
Factory `get_signature_provider()` basée sur `SIGNATURE_PROVIDER` dans `.env`.

## ADR-006 — Frontend Next.js 14 avec architecture modulaire
App Router + TypeScript strict. AuthProvider centralisé avec auto-refresh JWT.
Client API axios avec intercepteurs (401 → refresh token automatique).
Composants UI réutilisables : Button, Card, Input, Badge, Toast, Spinner.

## ADR-007 — Notifications WebSocket temps réel
WebSocket `/ws/notifications` avec auth JWT via query param.
Redis Pub/Sub pour multi-instance. ConnectionManager pour gestion connexions.
Frontend : hook `useAlertes()` avec auto-reconnexion et toast notifications.

## ADR-008 — Layout responsive avec sidebar adaptative
AppLayout : sidebar navigation + header breadcrumb + zone contenu.
Navigation filtrée par rôles. Badge alertes temps réel. Mobile responsive.

## Décisions en attente
- [ ] File storage : local ou S3/Minio ?
- [ ] Recherche fulltext : pg_trgm ou Elasticsearch ?
- [ ] Cache stratégie : Redis keys TTL ou invalidation active ?
- [ ] CI/CD pipeline : GitHub Actions ou GitLab CI ?
