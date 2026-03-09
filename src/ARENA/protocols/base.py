"""Base protocol interface for ARENA evaluation protocols."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class Role(str, Enum):
    """Participant role in a protocol."""
    PROPOSER = "proposer"
    OPPONENT = "opponent"
    JUDGE = "judge"
    AUDITOR = "auditor"
    PLANNER = "planner"
    IMPLEMENTER = "implementer"


@dataclass
class ProtocolTurn:
    """A single turn in a protocol execution."""
    turn_number: int
    role: Role
    model: str
    provider: str
    content: str
    tokens_used: int = 0
    thinking_tokens: int = 0
    latency_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProtocolResult:
    """Result of a complete protocol execution."""
    protocol_name: str
    task_id: str
    turns: list[ProtocolTurn] = field(default_factory=list)
    scores: dict[str, float] = field(default_factory=dict)
    cost_breakdown: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def total_tokens(self) -> int:
        return sum(t.tokens_used for t in self.turns)

    @property
    def total_latency_ms(self) -> float:
        return sum(t.latency_ms for t in self.turns)

    @property
    def num_turns(self) -> int:
        return len(self.turns)


class Protocol(ABC):
    """Base class for ARENA evaluation protocols.

    A protocol defines the interaction pattern between models:
    - Debate: adversarial alternation with judge scoring
    - Collab: cooperative planning with auditor verification
    - Audit: safety and correctness probing
    """

    @abstractmethod
    def run(self, task: Any, **kwargs) -> ProtocolResult:
        """Execute the protocol on a task.

        Args:
            task: The task to evaluate (ArenaTask or similar).
            **kwargs: Protocol-specific configuration.

        Returns:
            ProtocolResult with turns, scores, and cost breakdown.
        """
        ...

    @abstractmethod
    def score(self, result: ProtocolResult) -> dict[str, float]:
        """Score a completed protocol result.

        Args:
            result: The protocol execution result.

        Returns:
            Dict of metric_name -> score.
        """
        ...