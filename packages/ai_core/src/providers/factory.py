"""Factory : instancie le bon provider IA selon .env"""
import os
from functools import lru_cache
from .base import BaseAIProvider, AIProviderType
from .anthropic_provider import AnthropicProvider
from .ollama_provider import OllamaProvider
from .openai_provider import OpenAICompatibleProvider


@lru_cache(maxsize=1)
def get_ai_provider() -> BaseAIProvider:
    provider_type = os.getenv("AI_PROVIDER", "anthropic").lower()
    model        = os.getenv("AI_MODEL")
    temperature  = float(os.getenv("AI_TEMPERATURE", "0.3"))
    max_tokens   = int(os.getenv("AI_MAX_TOKENS", "4096"))
    kwargs = {"temperature": temperature, "max_tokens": max_tokens}

    if provider_type == AIProviderType.ANTHROPIC:
        api_key = os.getenv("ANTHROPIC_API_KEY") or raise_missing("ANTHROPIC_API_KEY")
        return AnthropicProvider(api_key=api_key, model=model or "claude-sonnet-4-20250514", **kwargs)

    elif provider_type == AIProviderType.OPENAI:
        api_key = os.getenv("OPENAI_API_KEY") or raise_missing("OPENAI_API_KEY")
        return OpenAICompatibleProvider(api_key=api_key,
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            model=model or "gpt-4o-mini", **kwargs)

    elif provider_type == AIProviderType.OLLAMA:
        return OllamaProvider(
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            model=model or os.getenv("OLLAMA_MODEL", "mistral:7b"), **kwargs)

    elif provider_type == AIProviderType.CUSTOM:
        return OpenAICompatibleProvider(
            api_key=os.getenv("CUSTOM_AI_API_KEY", "not-required"),
            base_url=os.getenv("CUSTOM_AI_BASE_URL", "http://localhost:1234/v1"),
            model=model or os.getenv("CUSTOM_AI_MODEL", "local-model"), **kwargs)

    raise ValueError(f"Provider inconnu : '{provider_type}'. Valeurs : anthropic, openai, ollama, custom")


def raise_missing(key: str):
    raise ValueError(f"{key} manquant dans .env")


def reset_provider_cache():
    get_ai_provider.cache_clear()
