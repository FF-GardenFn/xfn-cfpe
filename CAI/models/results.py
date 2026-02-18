"""
Trial result data structures.
"""

from dataclasses import dataclass
from typing import Any, Optional

from models.schemas import ToolCall, ValidationResult


@dataclass
class TrialResult:
    """Result of a single trial with consistent metrics."""
    task_id: str
    condition: str
    model: str
    response: str

    # Parsed output
    tool_call: Optional[ToolCall]

    # Intent classification (key addition)
    intent: str  # "compliance", "refusal", "unclear"

    # Validation metrics
    attempted_violation: bool
    blocked: bool
    recovered: bool
    residual_violation: bool

    # Final outcome
    task_success: bool

    # Optional details
    kernel_result: Optional[ValidationResult] = None
    recovery_response: Optional[str] = None

    # Violation taxonomy (for capability inversion analysis)
    violation_kind: Optional[str] = None  # ViolationKind value
    text_violations: Optional[list[str]] = None  # Matched text patterns

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "task_id": self.task_id,
            "condition": self.condition,
            "model": self.model,
            "intent": self.intent,
            "attempted_violation": self.attempted_violation,
            "blocked": self.blocked,
            "recovered": self.recovered,
            "residual_violation": self.residual_violation,
            "task_success": self.task_success,
            "response_preview": self.response[:500] if self.response else None,
            "violation_kind": self.violation_kind,
            "text_violations": self.text_violations,
        }
