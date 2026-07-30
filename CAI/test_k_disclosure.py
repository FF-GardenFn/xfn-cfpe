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

from kernel import ConstitutionalKernel
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

    print("\nRESULT: PASS - all 4 tests green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
