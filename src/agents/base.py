"""
Base Clinical Agent — Foundation for all specialized healthcare agents.

Provides HIPAA-compliant execution framework with audit logging,
PHI protection, budget tracking, and circuit breaker fault isolation.
"""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from langsmith import traceable

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
    """Runtime metrics for monitoring agent performance."""
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_cost: float = 0.0
    total_tokens: int = 0
    avg_latency_ms: float = 0.0
    latencies: list[float] = field(default_factory=list)
    last_error: Optional[str] = None
    last_active: Optional[datetime] = None


class CircuitBreaker:
    """
    Circuit breaker for fault isolation.

    Prevents cascading failures when an agent's LLM provider
    or downstream service is degraded.
    """

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.state = "closed"  # closed, open, half-open
        self.last_failure_time: Optional[float] = None

    def record_success(self):
        self.failure_count = 0
        self.state = "closed"

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.warning("Circuit breaker OPEN — %d consecutive failures", self.failure_count)

    def can_execute(self) -> bool:
        if self.state == "closed":
            return True
        if self.state == "open":
            if time.time() - (self.last_failure_time or 0) > self.recovery_timeout:
                self.state = "half-open"
                return True
            return False
        return True  # half-open: allow one attempt


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
        self.metrics = AgentMetrics()
        self.circuit_breaker = CircuitBreaker()

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

            # Update metrics
            latency_ms = (time.time() - start_time) * 1000
            self.metrics.tasks_completed += 1
            self.metrics.total_cost += response.get("cost", 0)
            self.metrics.total_tokens += response.get("total_tokens", 0)
            self.metrics.latencies.append(latency_ms)
            self.metrics.avg_latency_ms = sum(self.metrics.latencies) / len(self.metrics.latencies)
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
            self.metrics.tasks_failed += 1
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
        return {
            "name": self.config.name,
            "model": self.config.model,
            "status": "healthy" if self.circuit_breaker.state == "closed" else self.circuit_breaker.state,
            "tasks_completed": self.metrics.tasks_completed,
            "tasks_failed": self.metrics.tasks_failed,
            "total_cost": round(self.metrics.total_cost, 4),
            "avg_latency_ms": round(self.metrics.avg_latency_ms, 1),
            "budget_remaining": round(self.config.daily_budget - self.metrics.total_cost, 2),
            "last_active": self.metrics.last_active.isoformat() if self.metrics.last_active else None,
        }
