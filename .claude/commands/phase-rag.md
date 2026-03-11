---
name: phase-rag
description: Lance le workflow de la Phase 3 — RAG juridique et rédaction d'actes. Orchestre l'ingestion de Légifrance et BOFIP, le service RAG, et l'assistant de rédaction. Invoquer avec /phase-rag.
disable-model-invocation: true
---

# /phase-rag — Workflow Phase 3

Charge les skills `rag-juridique`, `pgvector-rag`, et `notaire-domain`.
Utilise l'agent `rag-specialist`.

## Séquence d'implémentation

### Étape 1 — Pipeline d'ingestion
Créer `packages/data-pipeline/src/ingest_legal.py` :
- `LegiFranceIngester` : Code civil successions (art. 720-892)
- `BOFIPIngester` : pages barèmes mutations à titre gratuit
- `EmbeddingPipeline` : chunking (512 tokens, overlap 50) + embeddings Ollama

```bash
# Test d'ingestion
python packages/data-pipeline/src/ingest_legal.py --source legifrance
docker exec notaire-postgres psql -U notaire -d notaire_app \
  -c "SELECT source_type, COUNT(*) FROM knowledge_chunks GROUP BY 1;"
```

### Étape 2 — Service RAG
Créer `packages/ai-core/src/rag/notaire_rag.py` :
- `NotaireRAG.search(query, source_type, k=5)` → similarité cosinus
- `NotaireRAG.answer(question, chunks)` → réponse citée

### Étape 3 — Routes juridiques
`packages/api/src/routers/juridique.py` :
- `POST /juridique/question`
- `POST /actes/analyser`
- `POST /actes/rediger` (streaming SSE)
- `POST /actes/relire`

## Critère de succès
```bash
curl -X POST http://localhost:8000/juridique/question \
  -d '{"question": "Quel est l abattement pour un enfant en succession ?"}' \
  | jq .response
# → Doit citer l'art. 779 CGI et le montant 100 000€
```
