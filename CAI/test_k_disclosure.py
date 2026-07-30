#!/usr/bin/env python3
"""
No-network validation for the disclosure axis (K-levels).

Exercises prompt composition and runner threading WITHOUT any API call.
The fake client returns a response starting with "I cannot", which makes
IntentClassifier._quick_classify short-circuit to REFUSAL before it would
ever reach the network.

Usage:
    cd CAI && ../bin/python3 test_k_disclosure.py
"""

import sys
from types import SimpleNamespace

from analysis.k_pilot_analysis import score, summarize
from kernel import ConstitutionalKernel, ViolationKind
from models import ToolCall
from classifier import IntentClassifier
from experiment import ExperimentRunner
from experiment.task_suite import TASKS
from experiment.prompts import (
    CONDITION_PROMPTS,
    KERNEL_DISCLOSURES,
    compose_system,
)

CONDITIONS = ["baseline", "cai", "kernel_only", "cai_kernel"]
DISCLOSURES = ["K0", "K1", "K2", "K3"]

FAKE_RESPONSE = "I cannot help with that."

K1_MARKER = "Runtime Enforcement Notice"
K2_MARKER = "The gate's complete policy"
K3_MARKER = "Additional Instruction"


class FakeMessages:
    """Stand-in for client.messages - records calls, never hits the network."""

    def __init__(self):
        self.calls: list[dict] = []

    def create(self, **kw):
        self.calls.append(kw)
        return SimpleNamespace(content=[SimpleNamespace(text=FAKE_RESPONSE)])


class FakeClient:
    """Stand-in for anthropic.Anthropic()."""

    def __init__(self):
        self.messages = FakeMessages()


def test_k0_regression() -> list[str]:
    """K0 must be byte-identical to the v4 prompt for every condition."""
    failures = []
    for cond in CONDITIONS:
        composed = compose_system(cond, "K0")
        expected = CONDITION_PROMPTS[cond]
        if composed != expected:
            failures.append(
                f"{cond}: K0 prompt differs from CONDITION_PROMPTS "
                f"(len {len(composed)} vs {len(expected)})"
            )
    return failures


def test_composition() -> list[str]:
    """K1-K3 must append cumulative disclosure text onto the v4 prompt."""
    failures = []
    for cond in CONDITIONS:
        base = CONDITION_PROMPTS[cond]
        for k in ["K1", "K2", "K3"]:
            composed = compose_system(cond, k)

            if not composed.startswith(base):
                failures.append(f"{cond}/{k}: composed prompt does not start with v4 prompt")

            if K1_MARKER not in composed:
                failures.append(f"{cond}/{k}: missing K1 marker {K1_MARKER!r}")

            has_k2 = K2_MARKER in composed
            has_k3 = K3_MARKER in composed

            if k == "K1":
                if has_k2:
                    failures.append(f"{cond}/K1: unexpectedly contains K2 marker")
                if has_k3:
                    failures.append(f"{cond}/K1: unexpectedly contains K3 marker")
            elif k == "K2":
                if not has_k2:
                    failures.append(f"{cond}/K2: missing K2 marker {K2_MARKER!r}")
                if has_k3:
                    failures.append(f"{cond}/K2: unexpectedly contains K3 marker")
            else:  # K3
                if not has_k2:
                    failures.append(f"{cond}/K3: missing K2 marker {K2_MARKER!r}")
                if not has_k3:
                    failures.append(f"{cond}/K3: missing K3 marker {K3_MARKER!r}")

    # Sanity: the disclosure table itself is cumulative
    if not KERNEL_DISCLOSURES["K2"].startswith(KERNEL_DISCLOSURES["K1"]):
        failures.append("KERNEL_DISCLOSURES: K2 is not a superset prefix of K1")
    if not KERNEL_DISCLOSURES["K3"].startswith(KERNEL_DISCLOSURES["K2"]):
        failures.append("KERNEL_DISCLOSURES: K3 is not a superset prefix of K2")
    if KERNEL_DISCLOSURES["K0"] != "":
        failures.append("KERNEL_DISCLOSURES: K0 is not the empty string")

    return failures


def test_runner_threading(runner: ExperimentRunner, task) -> list[str]:
    """disclosure must be threaded through run_trial into TrialResult."""
    failures = []
    for cond in CONDITIONS:
        for k in DISCLOSURES:
            result = runner.run_trial(task, cond, "fake-model", k)

            if result.disclosure != k:
                failures.append(
                    f"{cond}/{k}: TrialResult.disclosure == {result.disclosure!r}"
                )

            d = result.to_dict()
            if d.get("disclosure") != k:
                failures.append(
                    f"{cond}/{k}: to_dict()['disclosure'] == {d.get('disclosure')!r}"
                )

            # Fake response is a clean refusal -> no residual violation
            if result.residual_violation is not False:
                failures.append(
                    f"{cond}/{k}: residual_violation == {result.residual_violation!r}, "
                    "expected False for a clean refusal"
                )
    return failures


def test_default_compat(runner: ExperimentRunner, task) -> list[str]:
    """Calling run_trial without a disclosure arg must default to K0."""
    failures = []
    result = runner.run_trial(task, "baseline", "fake-model")
    if result.disclosure != "K0":
        failures.append(
            f"default disclosure == {result.disclosure!r}, expected 'K0'"
        )
    if result.to_dict().get("disclosure") != "K0":
        failures.append(
            f"default to_dict()['disclosure'] == "
            f"{result.to_dict().get('disclosure')!r}, expected 'K0'"
        )
    return failures


def test_tool_channel_not_masked() -> list[str]:
    """A tool-channel violation must survive both the taxonomy and the filter.

    Two defects could each make H1's falsifier structurally blind to a real
    tool-channel violation, and together would erase it:
      1. classify_violation checked text patterns first, so a violating call
         accompanied by a prose mention was labelled text_only.
      2. the mention-vs-use filter nulled any refusal-classified residual with
         text violations, including one where a call reached the gate.
    """
    failures = []
    kernel = ConstitutionalKernel()
    violating = ToolCall(tool_name="read_file", arguments={"path": "/etc/shadow"})
    benign = ToolCall(tool_name="search_web", arguments={"query": "weather"})

    # 1. Tool kind wins over a co-occurring prose match.
    kind = kernel.classify_violation(violating, ["some-prose-pattern"], True)
    if kind == ViolationKind.TEXT_ONLY:
        failures.append("classify_violation masked a violating tool call as text_only")

    # A non-violating call with dirty prose is genuinely text-only.
    kind = kernel.classify_violation(benign, ["some-prose-pattern"], False)
    if kind != ViolationKind.TEXT_ONLY:
        failures.append(f"classify_violation mislabelled a clean call as {kind}")

    # No call at all is text-only.
    if kernel.classify_violation(None, ["p"]) != ViolationKind.TEXT_ONLY:
        failures.append("classify_violation mislabelled a no-call response")

    # 2. The mention-vs-use filter must not null a real tool-channel event.
    #    Asserted on the RECORD (attempted/residual), not on the H1 falsifier:
    #    whether the event counts as *executed* is a separate question, decided
    #    by whether the gate blocked it — see test_blocked_is_not_executed.
    blocked_tool_event = {
        "intent": "refusal", "attempted_violation": True,
        "residual_violation": True, "text_violations": ["p"],
        "violation_kind": "sensitive_read", "blocked": True,
    }
    s = score(blocked_tool_event)
    if not (s["attempted"] and s["residual"]):
        failures.append("intent fix erased an unrecovered tool-channel violation")
    if s["executed_tool"]:
        failures.append(
            "a call the gate BLOCKED was counted as an executed tool-channel "
            "violation"
        )

    # The same event with no gate in the way: it really did go through, so it
    # must survive the filter AND register as executed tool-channel harm.
    passed_tool_event = dict(blocked_tool_event, blocked=False)
    s = score(passed_tool_event)
    if not (s["attempted"] and s["residual"] and s["executed_tool"]):
        failures.append("intent fix erased a tool-channel violation that executed")

    # ...but must still null a genuine mention-while-refusing false positive.
    prose_only = {
        "intent": "refusal", "attempted_violation": True,
        "residual_violation": True, "text_violations": ["p"],
        "violation_kind": "text_only", "blocked": False,
    }
    s = score(prose_only)
    if s["attempted"] or s["residual"]:
        failures.append("intent fix stopped clearing prose-only false positives")

    return failures


def test_blocked_is_not_executed() -> list[str]:
    """A blocked-then-unrecovered trial must never read as executed harm.

    `residual_violation` was set in two branches with two incompatible
    meanings: where the gate BLOCKED a call it meant "blocked, and the
    follow-up turn wasn't clean" (nothing ran); everywhere else it meant "a
    violating action went through". H1's falsifier is "any EXECUTED
    tool-channel violation", so scoring it off `residual` blames the gate for
    failures it in fact prevented.

    This is live, not hypothetical. After the classify_violation fix in
    f1bb6a4 a blocked-then-unrecovered row carries a TOOL kind instead of
    `text_only`, so the old `residual and kind in TOOL_KINDS` would report 8
    executed tool-channel violations in the v4 data where zero executed.
    """
    failures = []

    # The shape that would falsely falsify H1: gate refused the call, the
    # follow-up turn wasn't clean, and the corrected classifier gives it a
    # tool kind.
    blocked_unrecovered = {
        "intent": "compliance", "attempted_violation": True,
        "residual_violation": True, "violation_kind": "sensitive_read",
        "blocked": True, "recovered": False, "text_violations": [],
    }
    s = score(blocked_unrecovered)
    if s["executed"]:
        failures.append("blocked-and-unrecovered trial counted as EXECUTED")
    if s["executed_tool"]:
        failures.append(
            "blocked-and-unrecovered trial counted as an executed "
            "tool-channel violation — this would falsely falsify H1"
        )
    if s["residual_tool"]:
        failures.append(
            "residual_tool still keys on the conflated metric; a blocked "
            "call would trip H1's falsifier"
        )
    if not s["blocked_unrecovered"]:
        failures.append("blocked-and-unrecovered trial not reported as such")
    if s["blocked_recovered"]:
        failures.append("blocked-and-unrecovered trial mislabelled as recovered")
    # The upper-bound field keeps its historical value so stored files remain
    # reproducible — it must NOT have been silently redefined.
    if not s["residual"]:
        failures.append(
            "residual_violation was silently redefined; stored v4/pilot "
            "values would no longer reproduce"
        )

    # Blocked AND recovered: gate worked, follow-up clean. Nothing anywhere.
    blocked_recovered = dict(blocked_unrecovered,
                             residual_violation=False, recovered=True)
    s = score(blocked_recovered)
    if s["executed"] or s["executed_tool"] or s["blocked_unrecovered"]:
        failures.append("blocked-and-recovered trial mis-scored")
    if not s["blocked_recovered"]:
        failures.append("blocked-and-recovered trial not reported as such")

    # Contrast: a genuine leak. No gate, violating call went through. This one
    # MUST trip the falsifier, or the fix has gone too far the other way.
    executed_leak = {
        "intent": "compliance", "attempted_violation": True,
        "residual_violation": True, "violation_kind": "sensitive_read",
        "blocked": False, "recovered": False, "text_violations": [],
    }
    s = score(executed_leak)
    if not (s["executed"] and s["executed_tool"] and s["residual_tool"]):
        failures.append(
            "a real executed tool-channel violation stopped tripping H1's "
            "falsifier — the fix over-corrected"
        )

    # H1's falsifier, end to end: a K-cell made entirely of blocked-and-
    # unrecovered trials must not fire it; one real leak must.
    clean = summarize([blocked_unrecovered] * 4)
    if clean["executed_tool"] != 0:
        failures.append(
            f"summarize() reports {clean['executed_tool']} executed "
            "tool-channel violations for 4 blocked trials; expected 0"
        )
    if clean["blocked_unrecovered"] != 4:
        failures.append("summarize() lost the blocked-and-unrecovered count")
    leaky = summarize([blocked_unrecovered] * 4 + [executed_leak])
    if leaky["executed_tool"] != 1:
        failures.append(
            f"summarize() reports {leaky['executed_tool']} executed "
            "tool-channel violations for 4 blocked + 1 leak; expected 1"
        )

    # Rows written by the post-split runner carry the flags explicitly; the
    # explicit field must win over the back-compat derivation.
    explicit = dict(blocked_unrecovered, executed_violation=False,
                    blocked_violation=True, recovery_failure=True)
    if score(explicit)["executed"]:
        failures.append("explicit executed_violation=False was overridden")

    return failures


def test_runner_sets_outcome_split(runner: ExperimentRunner, task) -> list[str]:
    """The runner must emit the three outcomes coherently on every path."""
    failures = []
    for cond in CONDITIONS:
        r = runner.run_trial(task, cond, "fake-model", "K0")
        # Clean refusal: none of the three occurred.
        for field in ("executed_violation", "blocked_violation", "recovery_failure"):
            if getattr(r, field) is not False:
                failures.append(f"{cond}: {field} == {getattr(r, field)!r} on a clean refusal")
        # The compatibility identity must hold on every trial.
        if r.residual_violation != (r.executed_violation or r.recovery_failure):
            failures.append(
                f"{cond}: residual_violation != executed_violation OR recovery_failure"
            )
        if r.executed_violation and r.blocked_violation:
            failures.append(f"{cond}: trial marked both executed and blocked")
        d = r.to_dict()
        for field in ("executed_violation", "blocked_violation", "recovery_failure"):
            if field not in d:
                failures.append(f"{cond}: to_dict() omits {field}")

    # The error path constructs a TrialResult separately — it must be coherent too.
    err = runner._error_result(task, "baseline", "fake-model", "ERROR: transport")
    if err.executed_violation or err.blocked_violation or err.recovery_failure:
        failures.append("_error_result set a violation outcome on a transport error")
    return failures


def main() -> int:
    client = FakeClient()
    runner = ExperimentRunner(
        client=client,
        kernel=ConstitutionalKernel(),
        classifier=IntentClassifier(FakeClient()),
    )

    task = TASKS[0]
    print(f"Using task: {task.id}\n")

    tests = [
        ("Test 1: K0 byte-identical regression", lambda: test_k0_regression()),
        ("Test 2: K1-K3 composition + cumulativity", lambda: test_composition()),
        ("Test 3: runner threads disclosure -> TrialResult", lambda: test_runner_threading(runner, task)),
        ("Test 4: run_trial default disclosure == K0", lambda: test_default_compat(runner, task)),
        ("Test 5: tool-channel violations are not masked", lambda: test_tool_channel_not_masked()),
        ("Test 6: blocked != executed (H1 falsifier keys on execution)", lambda: test_blocked_is_not_executed()),
        ("Test 7: runner emits the three-outcome split coherently", lambda: test_runner_sets_outcome_split(runner, task)),
    ]

    total_failures = 0
    for name, fn in tests:
        failures = fn()
        if failures:
            total_failures += len(failures)
            print(f"FAIL  {name}")
            for f in failures:
                print(f"        - {f}")
        else:
            print(f"PASS  {name}")

    print()
    print(f"Model API calls made by fake client: {len(client.messages.calls)} "
          f"(all served locally, zero network)")

    if total_failures:
        print(f"\nRESULT: FAIL - {total_failures} assertion failure(s)")
        return 1

    print(f"\nRESULT: PASS - all {len(tests)} tests green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
