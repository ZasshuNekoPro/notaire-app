---
name: rag-juridique
description: Architecture et implémentation du système RAG (Retrieval-Augmented Generation) juridique pour le domaine notarial. Active pour toute question sur les embeddings, pgvector, la recherche vectorielle, l'ingestion de Légifrance ou BOFIP, le module ai-core/rag/, la table knowledge_chunks, ou quand l'utilisateur veut implémenter une recherche sémantique sur des textes juridiques. Active aussi pour les questions sur nomic-embed-text, la similarité cosinus, ou l'indexation IVFFlat.
allowed-tools: Bash, Read, Write
---

# RAG Juridique — Architecture et Implémentation

## Principe du RAG

```
Question notaire
    ↓ embed(question) → vecteur[768]
    ↓ cosine similarity sur knowledge_chunks
Top-5 chunks pertinents (articles de loi, jurisprudence)
    ↓ + question originale
Prompt enrichi → LLM
    ↓
Réponse citant les sources exactes
```

## Table knowledge_chunks

```sql
CREATE TABLE knowledge_chunks (
    id          UUID PRIMARY KEY,
    source      VARCHAR(255),      -- ex: "Code civil art.734"
    source_type VARCHAR(50),       -- 'loi' | 'jurisprudence' | 'bofip' | 'acte_type'
    content     TEXT,              -- texte du chunk (512 tokens max)
    content_hash VARCHAR(64) UNIQUE, -- SHA256 pour déduplication
    embedding   vector(768),       -- nomic-embed-text
    metadata    JSONB              -- { article, date_version, url }
);

-- Index de recherche vectorielle
CREATE INDEX idx_chunks_embedding ON knowledge_chunks
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

## Requête de recherche (pgvector)

```python
async def search_similar(query_embedding: list[float], k: int = 5,
                         source_type: str = None) -> list[dict]:
    filter_clause = "AND source_type = $3" if source_type else ""
    params = [query_embedding, k]
    if source_type:
        params.append(source_type)

    return await conn.fetch(f"""
        SELECT id, source, source_type, content, metadata,
               1 - (embedding <=> $1::vector) AS similarity
        FROM knowledge_chunks
        WHERE 1 - (embedding <=> $1::vector) > 0.75
        {filter_clause}
        ORDER BY embedding <=> $1::vector
        LIMIT $2
    """, *params)
```

## Sources d'ingestion

### 1. Légifrance (API PISTE)
```
POST https://api.piste.gouv.fr/dila/legifrance/lf-engine-app/consult/getArticle
Authorization: Bearer <token>
Body: { "id": "LEGIARTI000006436298" }
```

### 2. BOFIP (scraping structuré)
```
https://bofip.impots.gouv.fr/bofip/1-PGP.html
→ Pages ENR (Enregistrement) > Mutations à titre gratuit
```

### 3. Chunking optimal
- Taille : 400-512 tokens par chunk
- Overlap : 50 tokens entre chunks consécutifs
- Frontières : couper aux articles/alinéas, jamais au milieu d'une phrase

## Provider d'embeddings

```python
# Règle : Anthropic n'a pas d'API d'embedding
# → Toujours utiliser OllamaProvider pour les embeddings
# même si AI_PROVIDER=anthropic pour le LLM principal

from packages.ai_core.src.providers import OllamaProvider

embed_provider = OllamaProvider(
    model="nomic-embed-text",   # 768 dimensions
    base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
)
embedding = await embed_provider.embed(text)
```

## Voir aussi
- `references/prompt-rag.md` : template de prompt RAG notarial
