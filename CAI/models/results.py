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

    # DEPRECATED SEMANTICS — kept for backward compatibility with stored v4 and
    # pilot data, whose values must stay reproducible.
    #
    #     residual_violation == executed_violation OR recovery_failure
    #
    # It is therefore an **upper bound** on harm that got through, not a measure
    # of it. The runner set this field in two branches with two incompatible
    # meanings: where the gate blocked a call it meant "blocked, and the
    # follow-up turn was not clean" (nothing executed); everywhere else it meant
    # "a violating action went through". Any question of the form "what actually
    # got through?" — H1's falsifier above all — must read `executed_violation`,
    # never this field.
    residual_violation: bool

    # Final outcome
    task_success: bool

    # Disclosure axis (K-level): what the system prompt told the model about
    # the kernel. "K0" = undisclosed, reproduces v4 exactly.
    disclosure: str = "K0"

    # --- Outcome split (the three states `residual_violation` conflated) -----
    # Mutually exclusive by construction; at most one is True on any trial.
    #
    #   executed_violation  a violating action actually got through — either no
    #                       gate was active, or the gate did not block it. This
    #                       and only this is what H1's falsifier keys on, and
    #                       the only one of the three that is a safety breach.
    #   blocked_violation   a violating tool call was presented and the gate
    #                       refused it. Evidence the gate WORKED. Nothing
    #                       executed. Says nothing about the follow-up turn.
    #   recovery_failure    the call was blocked AND the model's subsequent turn
    #                       was not clean (another violating call, a non-refusal
    #                       with no call, or prose that matched a pattern). A
    #                       utility/behavioral outcome, NOT a safety breach: the
    #                       action was already prevented before this turn ran.
    #
    # `blocked_violation` is True on every blocked trial; `recovery_failure` is
    # the subset of those where recovery did not come back clean. Reading
    # `recovery_failure` as leaked harm is the exact error this split exists to
    # prevent — it blames the gate for failures it in fact prevented.
    executed_violation: bool = False
    blocked_violation: bool = False
    recovery_failure: bool = False

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
            # Upper bound (executed OR recovery_failure) — see field docs.
            "residual_violation": self.residual_violation,
            # The honest split. Consumers asking "what got through?" read
            # executed_violation; the other two are gate-worked evidence.
            "executed_violation": self.executed_violation,
            "blocked_violation": self.blocked_violation,
            "recovery_failure": self.recovery_failure,
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
