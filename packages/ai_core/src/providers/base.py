"""Abstraction multi-provider IA."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator, Optional
from enum import Enum


class AIProviderType(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI    = "openai"
    OLLAMA    = "ollama"
    CUSTOM    = "custom"


@dataclass
class AIMessage:
    role: str    # "user" | "assistant" | "system"
    content: str


@dataclass
class AIResponse:
    content: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    raw: dict | None = None


class BaseAIProvider(ABC):
    def __init__(self, model: str, temperature: float = 0.3, max_tokens: int = 4096):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    @abstractmethod
    async def complete(self, messages: list[AIMessage], system_prompt: Optional[str] = None) -> AIResponse: ...

    @abstractmethod
    async def stream(self, messages: list[AIMessage], system_prompt: Optional[str] = None) -> AsyncIterator[str]: ...

    @abstractmethod
    async def embed(self, text: str) -> list[float]: ...

    @property
    @abstractmethod
    def provider_name(self) -> str: ...
