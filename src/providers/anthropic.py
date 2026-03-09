"""
Anthropic Provider — Claude Enterprise with BAA for healthcare AI.

Uses Claude's extended context window for processing complete patient records.
Prompt caching enabled for system prompts to reduce cost.
"""

import logging
import time

import anthropic
from langsmith import traceable

from src.providers.base import BaseLLMProvider, LLMResponse

logger = logging.getLogger(__name__)

PRICING = {
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00, "cache_read": 0.30},
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00, "cache_read": 0.08},
}


class AnthropicProvider(BaseLLMProvider):
    """
    Claude Enterprise provider with BAA compliance.

    Features:
    - 200K context window for full patient record processing
    - Prompt caching for repeated system prompts (clinical guidelines)
    - Low hallucination rate critical for medical accuracy
    - BAA signed for HIPAA-compliant PHI processing
    """

    def __init__(self, api_key: str):
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    @traceable(name="anthropic.generate")
    async def generate(
        self,
        system: str,
        prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.1,
        model: str = "claude-sonnet-4-20250514",
        tools: list = None,
    ) -> LLMResponse:
        start = time.time()

        # Enable prompt caching for system prompt
        system_messages = [
            {
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }
        ]

        kwargs = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system_messages,
            "messages": [{"role": "user", "content": prompt}],
        }

        if tools:
            kwargs["tools"] = tools

        response = await self._client.messages.create(**kwargs)

        content = ""
        for block in response.content:
            if block.type == "text":
                content += block.text

        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        cache_read = getattr(response.usage, "cache_read_input_tokens", 0)

        cost = self.calculate_cost(input_tokens, output_tokens, cache_read, model)
        latency = (time.time() - start) * 1000

        if cache_read > 0:
            logger.info("Cache hit: %d tokens saved ($%.4f savings)", cache_read, cache_read * 0.0000027)

        return LLMResponse(
            content=content,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            cost=cost,
            latency_ms=latency,
            cached=cache_read > 0,
        )

    def calculate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int = 0,
        model: str = "claude-sonnet-4-20250514",
    ) -> float:
        prices = PRICING.get(model, PRICING["claude-sonnet-4-20250514"])
        input_cost = (input_tokens - cache_read_tokens) * prices["input"] / 1_000_000
        cache_cost = cache_read_tokens * prices["cache_read"] / 1_000_000
        output_cost = output_tokens * prices["output"] / 1_000_000
        return input_cost + cache_cost + output_cost
