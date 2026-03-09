"""
Model Router — Routes requests to appropriate LLM provider.

Selects Claude Enterprise for complex clinical reasoning and
routes based on task type, urgency, and budget.
"""

import logging
from typing import Optional

from src.providers.anthropic import AnthropicProvider
from src.providers.base import LLMResponse

logger = logging.getLogger(__name__)

# Task → Model mapping
TASK_MODEL_MAP = {
    "pa_generation": "claude-sonnet-4-20250514",
    "appeal_drafting": "claude-sonnet-4-20250514",
    "coding_analysis": "claude-sonnet-4-20250514",
    "denial_prediction": "claude-sonnet-4-20250514",
    "classification": "claude-haiku-4-5-20251001",
    "summarization": "claude-haiku-4-5-20251001",
}


class ModelRouter:
    """
    Routes AI requests to the appropriate model and provider.

    All requests go through Claude Enterprise (BAA-signed) to maintain
    HIPAA compliance. Model selection based on task complexity.
    """

    def __init__(self, settings):
        self._anthropic = AnthropicProvider(api_key=settings.anthropic_api_key)
        self._total_cost = 0.0
        self._request_count = 0

    async def generate(
        self,
        model: str = None,
        system: str = "",
        prompt: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.1,
        task_type: str = None,
        tools: list = None,
    ) -> dict:
        """Route to appropriate model and return standardized response."""
        # Select model based on task type if not specified
        if not model and task_type:
            model = TASK_MODEL_MAP.get(task_type, "claude-sonnet-4-20250514")
        elif not model:
            model = "claude-sonnet-4-20250514"

        response = await self._anthropic.generate(
            system=system,
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            model=model,
            tools=tools,
        )

        self._total_cost += response.cost
        self._request_count += 1

        return {
            "content": response.content,
            "model": response.model,
            "cost": response.cost,
            "total_tokens": response.total_tokens,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "latency_ms": response.latency_ms,
            "cached": response.cached,
        }

    def get_cost_summary(self) -> dict:
        return {
            "total_cost": round(self._total_cost, 4),
            "request_count": self._request_count,
            "avg_cost_per_request": round(self._total_cost / max(self._request_count, 1), 4),
        }
