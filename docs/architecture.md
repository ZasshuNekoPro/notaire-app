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

## Décisions en attente
- [ ] File storage : local ou S3/Minio ?
- [ ] Recherche fulltext : pg_trgm ou Elasticsearch ?
