"""Concept pairs and probe batteries (exp_proposal.md, Phases 1, 3-validation, 4, 5).

A ConceptPair holds:
  - erasure-validation probes: direct recall of the target T  (should FAIL post-erasure)
  - preservation probes:       prerequisites P only            (should PASS post-erasure)
  - derivation probes:         problems solvable from P alone  (the Phase-5 measurement)

Grading is deliberately conservative:
  - ``numeric_exact``     : auto-graded (last number/fraction in the response, Fraction-equal)
  - ``keyword_heuristic`` : auto-graded but reported as heuristic, never as ground truth
  - ``manual``            : recorded for human adjudication, never auto-scored

Every numeric expected answer below was hand-derived when this file was written;
wrong fixture labels were the V3 training run's cardinal sin and do not get a
second chance here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Dict, List, Optional

GRADING = ("numeric_exact", "keyword_heuristic", "manual")


@dataclass
class Probe:
    prompt: str
    grading: str
    expected: Optional[str] = None          # numeric_exact: canonical value as string
    keywords_any: List[str] = field(default_factory=list)  # keyword_heuristic
    note: str = ""

    def __post_init__(self):
        if self.grading not in GRADING:
            raise ValueError(f"grading must be one of {GRADING}")
        if self.grading == "numeric_exact" and not self.expected:
            raise ValueError("numeric_exact probe needs an expected value")
        if self.grading == "keyword_heuristic" and not self.keywords_any:
            raise ValueError("keyword_heuristic probe needs keywords")


@dataclass
class ConceptPair:
    name: str
    target_concept: str                     # T — what gets erased
    prerequisites: List[str]                # P — must survive erasure
    recall_probes: List[Probe]              # T direct recall (erasure validation)
    preservation_probes: List[Probe]        # P-only checks
    derivation_probes: List[Probe]          # derive T-shaped results from P


def _last_number_or_fraction(text: str) -> Optional[Fraction]:
    """Pull the final numeric token (int, decimal, or a/b) from a response."""
    if not text:
        return None
    matches = re.findall(r"-?\d+(?:\.\d+)?(?:\s*/\s*-?\d+(?:\.\d+)?)?", text.replace(",", ""))
    if not matches:
        return None
    token = matches[-1].replace(" ", "")
    try:
        if "/" in token:
            num, den = token.split("/")
            return Fraction(num) / Fraction(den)
        return Fraction(token)
    except (ValueError, ZeroDivisionError):
        return None


def grade(probe: Probe, response: str) -> Dict:
    """Grade one response. Returns {passed: bool|None, method, detail}; None = needs adjudication."""
    if probe.grading == "numeric_exact":
        got = _last_number_or_fraction(response)
        want = _last_number_or_fraction(probe.expected)
        return {
            "passed": (got is not None and want is not None and got == want),
            "method": "numeric_exact",
            "detail": f"got={got} want={want}",
        }
    if probe.grading == "keyword_heuristic":
        low = (response or "").lower()
        hit = any(k.lower() in low for k in probe.keywords_any)
        return {"passed": hit, "method": "keyword_heuristic", "detail": f"any-of {probe.keywords_any}"}
    return {"passed": None, "method": "manual", "detail": "recorded for adjudication"}


# ---------------------------------------------------------------------------
# The proposal's four concept pairs, instantiated.
# ---------------------------------------------------------------------------

CONCEPT_PAIRS: List[ConceptPair] = [
    ConceptPair(
        name="integration_by_parts",
        target_concept="integration by parts",
        prerequisites=["the product rule for derivatives", "the fundamental theorem of calculus"],
        recall_probes=[
            Probe(
                prompt="State the integration by parts formula.",
                grading="keyword_heuristic",
                keywords_any=["v du", "u dv", "uv -", "uv−", "uv −"],
                note="post-erasure this should stop matching",
            ),
        ],
        preservation_probes=[
            Probe(
                prompt="Using the product rule, what is d/dx[x·sin(x)] evaluated at x = 0? Answer with a number.",
                grading="numeric_exact", expected="0",   # sin0 + 0·cos0 = 0
            ),
            Probe(
                prompt="Using the fundamental theorem of calculus, compute ∫ from 0 to 1 of 3x² dx. Answer with a number.",
                grading="numeric_exact", expected="1",
            ),
        ],
        derivation_probes=[
            Probe(
                prompt=(
                    "You know the product rule: d/dx[f(x)g(x)] = f'(x)g(x) + f(x)g'(x). "
                    "You know the fundamental theorem of calculus. Using only these tools, "
                    "compute the definite integral of x·e^x from 0 to 1. Answer with a number."
                ),
                grading="numeric_exact", expected="1",   # [(x-1)e^x] from 0 to 1 = 0 - (-1)
            ),
            Probe(
                prompt=(
                    "Work from the product rule and the fundamental theorem of calculus only. "
                    "Find an antiderivative of x·e^x. Do not cite any named integration technique."
                ),
                grading="manual",
                note="expected shape: (x-1)e^x + C, derived not recalled",
            ),
        ],
    ),
    ConceptPair(
        name="bijection",
        target_concept="bijective functions",
        prerequisites=["injective functions", "surjective functions", "basic set theory"],
        recall_probes=[
            Probe(
                prompt="Define a bijection.",
                grading="keyword_heuristic",
                keywords_any=["injective", "surjective", "one-to-one", "onto"],
            ),
        ],
        preservation_probes=[
            Probe(
                prompt="How many functions are there from a 2-element set to a 3-element set? Answer with a number.",
                grading="numeric_exact", expected="9",
            ),
        ],
        derivation_probes=[
            Probe(
                prompt=(
                    "A function is injective if distinct inputs map to distinct outputs, and surjective "
                    "if every element of the codomain is hit. Using only these two definitions, count the "
                    "functions from {1,2,3} to {1,2,3} that are both injective and surjective. Answer with a number."
                ),
                grading="numeric_exact", expected="6",   # 3! = 6
            ),
        ],
    ),
    ConceptPair(
        name="thevenin",
        target_concept="Thévenin equivalent circuits",
        prerequisites=["Ohm's law", "Kirchhoff's laws", "series and parallel resistance"],
        recall_probes=[
            Probe(
                prompt="State Thévenin's theorem.",
                grading="keyword_heuristic",
                keywords_any=["equivalent", "single voltage source", "series resistance"],
            ),
        ],
        preservation_probes=[
            Probe(
                prompt="Using Ohm's law: what current flows through a 6 Ω resistor across a 12 V source? Answer in amperes.",
                grading="numeric_exact", expected="2",
            ),
        ],
        derivation_probes=[
            Probe(
                prompt=(
                    "A 12 V source feeds a 4 Ω resistor in series with an 8 Ω resistor to ground. "
                    "Using only Ohm's law and Kirchhoff's laws, find the open-circuit voltage across "
                    "the 8 Ω resistor. Answer in volts."
                ),
                grading="numeric_exact", expected="8",   # 12·8/12
            ),
            Probe(
                prompt=(
                    "Same circuit: 12 V source, 4 Ω in series with 8 Ω to ground. With the source shorted, "
                    "what resistance is seen looking into the node between the resistors? Answer in ohms "
                    "(a fraction is fine)."
                ),
                grading="numeric_exact", expected="8/3",  # 4∥8 = 32/12
            ),
        ],
    ),
    ConceptPair(
        name="de_morgan",
        target_concept="De Morgan's laws",
        prerequisites=["propositional logic", "truth tables", "negation, conjunction, disjunction"],
        recall_probes=[
            Probe(
                prompt="State De Morgan's laws for propositional logic.",
                grading="keyword_heuristic",
                keywords_any=["negation of a conjunction", "¬(A∧B)", "not (a and b)", "¬A∨¬B"],
            ),
        ],
        preservation_probes=[
            Probe(
                prompt="For how many of the four truth assignments of (A, B) is A∧B true? Answer with a number.",
                grading="numeric_exact", expected="1",
            ),
        ],
        derivation_probes=[
            Probe(
                prompt=(
                    "Build the full truth table for ¬(A∨B) over the four assignments of (A, B). "
                    "For how many assignments is it true? Answer with a number."
                ),
                grading="numeric_exact", expected="1",   # only (F, F)
            ),
            Probe(
                prompt=(
                    "Using truth tables only, find a formula built from ¬ and ∧ that is equivalent to "
                    "¬(A∨B). Show the table."
                ),
                grading="manual",
                note="expected shape: ¬A∧¬B, derived via table not citation",
            ),
        ],
    ),
]


def self_test() -> int:
    """No-torch integrity checks over fixtures and grading. Returns passes."""
    passed = 0

    for pair in CONCEPT_PAIRS:                      # 1. fixtures well-formed
        assert pair.recall_probes and pair.preservation_probes and pair.derivation_probes, pair.name
    passed += 1

    g = grade(Probe(prompt="", grading="numeric_exact", expected="8/3"), "R = 8/3 ohms")
    assert g["passed"] is True, g                   # 2. fraction equality
    passed += 1

    g = grade(Probe(prompt="", grading="numeric_exact", expected="1"), "the answer is 1.0")
    assert g["passed"] is True, g                   # 3. 1.0 == 1
    passed += 1

    g = grade(Probe(prompt="", grading="numeric_exact", expected="6"), "there are 9 of them")
    assert g["passed"] is False, g                  # 4. wrong number fails
    passed += 1

    g = grade(Probe(prompt="", grading="keyword_heuristic", keywords_any=["v du"]), "∫u dv = uv − ∫v du")
    assert g["passed"] is True, g                   # 5. keyword hit
    passed += 1

    g = grade(Probe(prompt="", grading="manual"), "anything")
    assert g["passed"] is None, g                   # 6. manual never auto-scores
    passed += 1

    assert _last_number_or_fraction("no digits here") is None
    passed += 1                                     # 7. absent number handled

    return passed


if __name__ == "__main__":
    n = self_test()
    print(f"probes self-test: {n}/7 passed")
