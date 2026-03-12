# AI Core — Providers et RAG

## Règle absolue
Tout appel LLM passe par `src/providers/factory.py::get_ai_provider()`.

## Providers disponibles
| AI_PROVIDER | Classe | Embeddings |
|---|---|---|
| anthropic | AnthropicProvider | via Ollama |
| openai | OpenAICompatibleProvider | text-embedding-3-small |
| ollama | OllamaProvider | nomic-embed-text ✅ |
| custom | OpenAICompatibleProvider | selon modèle |

## Ajouter un provider
1. Hériter de BaseAIProvider (base.py)
2. Implémenter complete(), stream(), embed()
3. Ajouter dans factory.py
4. ADR dans docs/architecture.md

## Embeddings
Anthropic n'a pas d'API d'embedding.
Toujours utiliser OllamaProvider(model="nomic-embed-text") pour embed().

## RAG
- Service : src/rag/notaire_rag.py
- Recherche cosine via pgvector (<=> opérateur)
- Seuil similarité : 0.75 (ajustable)
- Dimension vecteurs : 768 (nomic) ou 1536 (openai)
