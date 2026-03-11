---
name: ai-provider
description: Architecture multi-provider IA du projet notaire-app. Active quand l'utilisateur travaille dans packages/ai-core/, modifie un provider IA, ajoute un nouveau provider, ou questionne sur la factory, les embeddings, ou le streaming. Active aussi pour les questions sur la configuration AI_PROVIDER dans .env, les différences entre Claude/Ollama/OpenAI, ou les coûts par provider.
user-invocable: false
---

# AI Provider — Architecture Multi-Provider

## Règle critique

> Toute interaction LLM passe par `ai-core/src/providers/`.
> Appel direct à l'API Anthropic depuis `api/` = INTERDIT.

## Interface BaseAIProvider

```python
class BaseAIProvider(ABC):
    async def complete(messages, system_prompt) -> AIResponse
    async def stream(messages, system_prompt) -> AsyncIterator[str]
    async def embed(text) -> list[float]  # 768 dims (nomic) ou 1536 (openai)
```

## Factory — get_ai_provider()

```python
# Usage dans n'importe quel service
from packages.ai_core.src.providers import get_ai_provider

provider = get_ai_provider()  # Lit AI_PROVIDER dans .env
response = await provider.complete([
    AIMessage(role="user", content="Analyse cette succession...")
], system_prompt="Tu es un expert en droit notarial...")
```

## Providers disponibles

| AI_PROVIDER | Classe | Clé requise | Embeddings |
|-------------|--------|-------------|------------|
| anthropic | AnthropicProvider | ANTHROPIC_API_KEY | Via Ollama |
| openai | OpenAICompatibleProvider | OPENAI_API_KEY | text-embedding-3-small |
| ollama | OllamaProvider | Aucune | nomic-embed-text ✅ |
| custom | OpenAICompatibleProvider | Optionnelle | Selon modèle |

## Règle embeddings

```python
# Anthropic n'a PAS d'API d'embedding native
# Toujours utiliser Ollama pour les embeddings, quel que soit le LLM principal

from packages.ai_core.src.providers import OllamaProvider

EMBED_PROVIDER = OllamaProvider(
    model="nomic-embed-text",
    base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
)
```

## Ajouter un nouveau provider

1. Créer `packages/ai-core/src/providers/mon_provider.py`
2. Hériter de `BaseAIProvider` et implémenter les 3 méthodes
3. Ajouter le cas dans `factory.py` sous `get_ai_provider()`
4. Documenter dans `docs/architecture.md` (ADR)
