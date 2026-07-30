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

    # Disclosure axis (K-level): what the system prompt told the model about
    # the kernel. "K0" = undisclosed, reproduces v4 exactly.
    disclosure: str = "K0"

    # Optional details
    kernel_result: Optional[ValidationResult] = None
    recovery_response: Optional[str] = None

    # Violation taxonomy (for capability inversion analysis)
    violation_kind: Optional[str] = None  # ViolationKind value
    text_violations: Optional[list[str]] = None  # Matched text patterns

    # --- Gate-exercise provenance -------------------------------------------
    # The kernel can only be tested on trials where a tool call actually
    # reached it. Without these fields the gate-exercise rate has to be
    # *derived* from branch structure after the fact (see k_pilot_results.md,
    # H1). Captured structurally and sanitized: tool name, argument keys and
    # value lengths — never raw argument values, which on the adversarial
    # suite are the attack payloads themselves.
    tool_call_summary: Optional[dict[str, Any]] = None  # first call, sanitized
    tool_call_violating: Optional[bool] = None  # did it fail kernel validation?

    # Model actually served, as observed from transport metadata — NOT the
    # requested string echoed back. None when the transport reports nothing.
    served_model: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "task_id": self.task_id,
            "condition": self.condition,
            "disclosure": self.disclosure,
            "model": self.model,
            "served_model": self.served_model,
            "intent": self.intent,
            "attempted_violation": self.attempted_violation,
            "blocked": self.blocked,
            "recovered": self.recovered,
            "residual_violation": self.residual_violation,
            "task_success": self.task_success,
            "response_preview": self.response[:500] if self.response else None,
            "violation_kind": self.violation_kind,
            "text_violations": self.text_violations,
            "tool_call": self.tool_call_summary,
            "tool_call_violating": self.tool_call_violating,
        }


def summarize_tool_call(call: Optional[ToolCall]) -> Optional[dict[str, Any]]:
    """Sanitized structural summary of a tool call, safe to persist.

    Records what the call *was* structurally — which tool, which arguments were
    supplied, how long each was, whether a justification accompanied it —
    without reproducing argument values. On the adversarial suite those values
    are the attack payloads, and results files get read by people.
    """
    if call is None:
        return None
    arg_shape: dict[str, Any] = {}
    for name, value in sorted(call.arguments.items()):
        if isinstance(value, str):
            arg_shape[name] = {"type": "str", "len": len(value)}
        else:
            arg_shape[name] = {"type": type(value).__name__}
    return {
        "tool_name": call.tool_name,
        "arg_shape": arg_shape,
        "has_justification": bool(call.justification),
        "justification_len": len(call.justification) if call.justification else 0,
    }
