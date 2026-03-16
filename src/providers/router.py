"""
Model Router — Routes requests to appropriate LLM provider with Redis-backed metrics.

Selects Claude Enterprise for complex clinical reasoning and
routes based on task type, urgency, and budget.
Maintains usage metrics in Redis for durability across restarts.
"""

import logging
from typing import Optional

from src.providers.anthropic import AnthropicProvider
from src.providers.base import LLMResponse
from src.db import get_redis_client

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
    Usage metrics persisted in Redis for durability.
    """

    def __init__(self, settings):
        self._anthropic = AnthropicProvider(api_key=settings.anthropic_api_key)
        self._redis_client = get_redis_client()
        self._redis_prefix = "model_router"

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

        # Update metrics in Redis
        if self._redis_client:
            try:
                self._redis_client.incrbyfloat(f"{self._redis_prefix}:total_cost", response.cost)
                self._redis_client.incr(f"{self._redis_prefix}:request_count")
            except Exception as e:
                logger.warning("Failed to update Redis metrics: %s", str(e))

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
        """Get LLM cost summary from Redis."""
        total_cost = 0.0
        request_count = 0

        if self._redis_client:
            try:
                cost_val = self._redis_client.get(f"{self._redis_prefix}:total_cost")
                total_cost = float(cost_val) if cost_val else 0.0

                count_val = self._redis_client.get(f"{self._redis_prefix}:request_count")
                request_count = int(count_val) if count_val else 0
            except Exception as e:
                logger.warning("Failed to read Redis metrics: %s", str(e))

        return {
            "total_cost": round(total_cost, 4),
            "request_count": request_count,
            "avg_cost_per_request": round(total_cost / max(request_count, 1), 4),
        }
