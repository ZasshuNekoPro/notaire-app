---
name: pgvector-rag
description: Patterns d'implémentation pgvector pour la recherche vectorielle. Active pour les questions sur les index IVFFlat ou HNSW, la similarité cosinus, les embeddings en base de données, ou quand l'utilisateur implémente une recherche sémantique dans PostgreSQL. Active aussi pour le tuning des performances vectorielles ou la migration vers plus de vecteurs.
user-invocable: false
---

# pgvector — Patterns d'implémentation

## Index recommandé selon le volume

```sql
-- < 100k vecteurs : IVFFlat (rapide à créer)
CREATE INDEX ON knowledge_chunks
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- > 100k vecteurs : HNSW (meilleure précision)
CREATE INDEX ON knowledge_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
```

## Requête de recherche optimisée

```sql
-- Similarité cosinus (valeur entre -1 et 1, 1 = identique)
SELECT id, source, content,
       1 - (embedding <=> $1::vector) AS similarity
FROM knowledge_chunks
WHERE source_type = $2
  AND 1 - (embedding <=> $1::vector) > 0.75  -- seuil de pertinence
ORDER BY embedding <=> $1::vector
LIMIT 5;
```

## Insertion avec déduplication

```python
await conn.execute("""
    INSERT INTO knowledge_chunks (source, source_type, content, content_hash, embedding)
    VALUES ($1, $2, $3, $4, $5::vector)
    ON CONFLICT (content_hash) DO NOTHING
""", source, source_type, content,
    hashlib.sha256(content.encode()).hexdigest(),
    json.dumps(embedding))
```

## Réglage des performances

```sql
-- Avant une grande insertion
SET maintenance_work_mem = '1GB';

-- Après insertion, reconstruire l'index
REINDEX INDEX idx_chunks_embedding;

-- Statistiques d'utilisation
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
WHERE tablename = 'knowledge_chunks';
```
