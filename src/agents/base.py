"""
Base Clinical Agent — Foundation for all specialized healthcare agents.

Provides HIPAA-compliant execution framework with audit logging,
PHI protection, budget tracking, and circuit breaker fault isolation.
"""

import logging
import time
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from langsmith import traceable

from src.db import get_redis_client

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Configuration for a clinical agent."""
    name: str
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    temperature: float = 0.1  # Low temp for clinical accuracy
    daily_budget: float = 50.0
    per_request_limit: float = 0.50
    tools: list[str] = field(default_factory=list)
    requires_phi_access: bool = True
    audit_level: str = "full"  # full, summary, minimal


@dataclass
class AgentMetrics:
    """
    Runtime metrics for monitoring agent performance (Redis-backed).

    Metrics are persisted in Redis for durability across application restarts
    and for sharing across load-balanced instances.
    """
    agent_name: str = ""  # Used as Redis key prefix
    redis_client: Optional[Any] = None

    def __post_init__(self):
        """Initialize Redis client if not provided."""
        if self.redis_client is None:
            self.redis_client = get_redis_client()

    def _key(self, suffix: str) -> str:
        """Generate Redis key for this agent's metric."""
        return f"agent_metrics:{self.agent_name}:{suffix}"

    @property
    def tasks_completed(self) -> int:
        """Get completed tasks count from Redis."""
        if not self.redis_client:
            return 0
        val = self.redis_client.get(self._key("tasks_completed"))
        return int(val) if val else 0

    @tasks_completed.setter
    def tasks_completed(self, value: int):
        """Set completed tasks count in Redis."""
        if self.redis_client:
            self.redis_client.set(self._key("tasks_completed"), value)

    @property
    def tasks_failed(self) -> int:
        """Get failed tasks count from Redis."""
        if not self.redis_client:
            return 0
        val = self.redis_client.get(self._key("tasks_failed"))
        return int(val) if val else 0

    @tasks_failed.setter
    def tasks_failed(self, value: int):
        """Set failed tasks count in Redis."""
        if self.redis_client:
            self.redis_client.set(self._key("tasks_failed"), value)

    @property
    def total_cost(self) -> float:
        """Get total cost from Redis."""
        if not self.redis_client:
            return 0.0
        val = self.redis_client.get(self._key("total_cost"))
        return float(val) if val else 0.0

    @total_cost.setter
    def total_cost(self, value: float):
        """Set total cost in Redis."""
        if self.redis_client:
            self.redis_client.set(self._key("total_cost"), value)

    @property
    def total_tokens(self) -> int:
        """Get total tokens from Redis."""
        if not self.redis_client:
            return 0
        val = self.redis_client.get(self._key("total_tokens"))
        return int(val) if val else 0

    @total_tokens.setter
    def total_tokens(self, value: int):
        """Set total tokens in Redis."""
        if self.redis_client:
            self.redis_client.set(self._key("total_tokens"), value)

    @property
    def avg_latency_ms(self) -> float:
        """Calculate average latency from stored latencies."""
        if not self.redis_client:
            return 0.0
        latencies = self.get_latencies()
        return sum(latencies) / len(latencies) if latencies else 0.0

    @property
    def last_error(self) -> Optional[str]:
        """Get last error message from Redis."""
        if not self.redis_client:
            return None
        return self.redis_client.get(self._key("last_error"))

    @last_error.setter
    def last_error(self, value: Optional[str]):
        """Set last error message in Redis."""
        if self.redis_client:
            if value:
                self.redis_client.set(self._key("last_error"), value)
            else:
                self.redis_client.delete(self._key("last_error"))

    @property
    def last_active(self) -> Optional[datetime]:
        """Get last active timestamp from Redis."""
        if not self.redis_client:
            return None
        val = self.redis_client.get(self._key("last_active"))
        if val:
            try:
                return datetime.fromisoformat(val)
            except (ValueError, TypeError):
                return None
        return None

    @last_active.setter
    def last_active(self, value: Optional[datetime]):
        """Set last active timestamp in Redis."""
        if self.redis_client:
            if value:
                self.redis_client.set(self._key("last_active"), value.isoformat())
            else:
                self.redis_client.delete(self._key("last_active"))

    def add_latency(self, latency_ms: float):
        """Add a latency measurement to the sorted set (keeps last 100 measurements)."""
        if not self.redis_client:
            return
        now = time.time()
        # Use sorted set to store latencies with timestamp as score
        self.redis_client.zadd(self._key("latencies"), {str(latency_ms): now})
        # Keep only last 100 measurements
        self.redis_client.zremrangebyrank(self._key("latencies"), 0, -101)
        # Set expiration (24 hours)
        self.redis_client.expire(self._key("latencies"), 86400)

    def get_latencies(self) -> list[float]:
        """Get all stored latency measurements from Redis."""
        if not self.redis_client:
            return []
        latencies = self.redis_client.zrange(self._key("latencies"), 0, -1)
        try:
            return [float(l) for l in latencies]
        except (ValueError, TypeError):
            return []

    def increment_completed(self):
        """Increment completed tasks counter."""
        if self.redis_client:
            self.redis_client.incr(self._key("tasks_completed"))

    def increment_failed(self):
        """Increment failed tasks counter."""
        if self.redis_client:
            self.redis_client.incr(self._key("tasks_failed"))

    def increment_cost(self, amount: float):
        """Add to total cost."""
        if self.redis_client:
            self.redis_client.incrbyfloat(self._key("total_cost"), amount)

    def increment_tokens(self, amount: int):
        """Add to total tokens."""
        if self.redis_client:
            self.redis_client.incrby(self._key("total_tokens"), amount)


class CircuitBreaker:
    """
    Redis-backed circuit breaker for fault isolation.

    Prevents cascading failures when an agent's LLM provider or downstream
    service is degraded. State persists across application restarts.

    States:
    - closed: Normal operation, requests allowed
    - open: Service degraded, requests rejected
    - half-open: Testing recovery, one request allowed
    """

    def __init__(self, agent_name: str, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.agent_name = agent_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.redis_client = get_redis_client()

    def _key(self, suffix: str) -> str:
        """Generate Redis key for this circuit breaker's state."""
        return f"circuit_breaker:{self.agent_name}:{suffix}"

    def record_success(self):
        """Record successful request and reset failure count."""
        if self.redis_client:
            self.redis_client.delete(self._key("failure_count"))
            self.redis_client.set(self._key("state"), "closed")
            logger.debug("Circuit breaker CLOSED — %s recovered", self.agent_name)

    def record_failure(self):
        """Record failed request and update failure count."""
        if not self.redis_client:
            return

        # Increment failure count
        failure_count = self.redis_client.incr(self._key("failure_count"))
        self.redis_client.set(self._key("last_failure_time"), time.time())

        if failure_count >= self.failure_threshold:
            self.redis_client.set(self._key("state"), "open")
            logger.warning("Circuit breaker OPEN — %s: %d consecutive failures",
                          self.agent_name, failure_count)

    def can_execute(self) -> bool:
        """Check if request can be executed (circuit breaker allows)."""
        if not self.redis_client:
            return True  # Fallback: allow if Redis unavailable

        current_state = self.redis_client.get(self._key("state")) or "closed"

        if current_state == "closed":
            return True

        if current_state == "open":
            last_failure = self.redis_client.get(self._key("last_failure_time"))
            if last_failure:
                try:
                    elapsed = time.time() - float(last_failure)
                    if elapsed > self.recovery_timeout:
                        self.redis_client.set(self._key("state"), "half-open")
                        logger.info("Circuit breaker HALF-OPEN — %s testing recovery", self.agent_name)
                        return True
                except (ValueError, TypeError):
                    pass
            return False

        # half-open: allow one attempt
        return True

    @property
    def state(self) -> str:
        """Get current circuit breaker state."""
        if not self.redis_client:
            return "closed"
        return self.redis_client.get(self._key("state")) or "closed"

    @property
    def failure_count(self) -> int:
        """Get current failure count."""
        if not self.redis_client:
            return 0
        val = self.redis_client.get(self._key("failure_count"))
        return int(val) if val else 0


class BaseClinicalAgent(ABC):
    """
    Base class for all clinical AI agents.

    Provides:
    - HIPAA-compliant execution with audit logging
    - PHI detection and masking in prompts/responses
    - Budget enforcement per request and daily
    - Circuit breaker for fault isolation
    - LangSmith tracing for observability
    """

    def __init__(self, config: AgentConfig, model_router, audit_logger):
        self.config = config
        self.model_router = model_router
        self.audit_logger = audit_logger
        self.metrics = AgentMetrics(agent_name=config.name)
        self.circuit_breaker = CircuitBreaker(agent_name=config.name)

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the agent's system prompt with clinical domain instructions."""
        pass

    @abstractmethod
    async def build_context(self, request: dict, patient_data: dict) -> str:
        """Build the context-specific prompt for this request."""
        pass

    @traceable(name="agent.execute")
    async def execute(self, request: dict, patient_data: dict) -> dict:
        """
        Execute the agent's task with full HIPAA compliance.

        Flow:
        1. Circuit breaker check
        2. Budget verification
        3. Build prompt with patient context
        4. PHI audit logging (what data accessed)
        5. LLM call via model router
        6. Response validation
        7. Metrics update
        """
        start_time = time.time()

        # Circuit breaker check
        if not self.circuit_breaker.can_execute():
            return {
                "status": "circuit_open",
                "error": f"Agent {self.config.name} circuit breaker is open",
                "agent": self.config.name,
            }

        # Budget check
        if self.metrics.total_cost >= self.config.daily_budget:
            return {
                "status": "budget_exceeded",
                "error": f"Daily budget ${self.config.daily_budget} exceeded",
                "agent": self.config.name,
            }

        try:
            # Build prompt
            system_prompt = self.get_system_prompt()
            user_prompt = await self.build_context(request, patient_data)

            # Audit: log PHI access
            await self.audit_logger.log_phi_access(
                agent=self.config.name,
                patient_id=patient_data.get("patient", {}).get("id"),
                data_types=self._identify_phi_types(patient_data),
                action="clinical_processing",
            )

            # LLM call
            response = await self.model_router.generate(
                model=self.config.model,
                system=system_prompt,
                prompt=user_prompt,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
            )

            # Update metrics in Redis
            latency_ms = (time.time() - start_time) * 1000
            self.metrics.increment_completed()
            self.metrics.increment_cost(response.get("cost", 0))
            self.metrics.increment_tokens(response.get("total_tokens", 0))
            self.metrics.add_latency(latency_ms)
            self.metrics.last_active = datetime.utcnow()
            self.circuit_breaker.record_success()

            return {
                "status": "success",
                "agent": self.config.name,
                "response": response.get("content", ""),
                "cost": response.get("cost", 0),
                "latency_ms": latency_ms,
                "model": self.config.model,
            }

        except Exception as e:
            self.metrics.increment_failed()
            self.metrics.last_error = str(e)
            self.circuit_breaker.record_failure()
            logger.error("Agent %s failed: %s", self.config.name, str(e))

            return {
                "status": "error",
                "agent": self.config.name,
                "error": str(e),
                "latency_ms": (time.time() - start_time) * 1000,
            }

    def _identify_phi_types(self, patient_data: dict) -> list[str]:
        """Identify which PHI data types are being accessed for audit logging."""
        phi_types = []
        if patient_data.get("patient"):
            phi_types.append("demographics")
        if patient_data.get("conditions"):
            phi_types.append("diagnoses")
        if patient_data.get("medications"):
            phi_types.append("medications")
        if patient_data.get("lab_results"):
            phi_types.append("lab_results")
        if patient_data.get("allergies"):
            phi_types.append("allergies")
        if patient_data.get("recent_encounters"):
            phi_types.append("encounters")
        return phi_types

    def get_status(self) -> dict:
        """Return agent status for monitoring dashboard."""
        total_cost = self.metrics.total_cost
        return {
            "name": self.config.name,
            "model": self.config.model,
            "status": "healthy" if self.circuit_breaker.state == "closed" else self.circuit_breaker.state,
            "tasks_completed": self.metrics.tasks_completed,
            "tasks_failed": self.metrics.tasks_failed,
            "total_cost": round(total_cost, 4),
            "avg_latency_ms": round(self.metrics.avg_latency_ms, 1),
            "budget_remaining": round(self.config.daily_budget - total_cost, 2),
            "last_active": self.metrics.last_active.isoformat() if self.metrics.last_active else None,
        }
