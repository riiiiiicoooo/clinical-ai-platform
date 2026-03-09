"""
LLM Provider Base — Abstract interface for healthcare AI model providers.

All providers must support BAA-compliant operation with PHI handling.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMResponse:
    """Standardized LLM response across providers."""
    content: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0
    latency_ms: float = 0.0
    cached: bool = False


class BaseLLMProvider(ABC):
    """Base class for LLM providers with BAA compliance."""

    @abstractmethod
    async def generate(
        self,
        system: str,
        prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.1,
        tools: list = None,
    ) -> LLMResponse:
        pass

    @abstractmethod
    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        pass
