# Evaluation Framework v1.0

Unified rubric for LLM reasoning evaluation. Core innovation: **Process-Confidence Coupling**.

---

## 1. Core Principles

| ID | Principle | Implication |
|----|-----------|-------------|
| P1 | Process > Output | Correct answer via flawed reasoning = fail |
| P2 | Quantifiable | Every dimension yields numeric score |
| P3 | Replayable | Same response + rubric = same score (±5%) |
| P4 | Multi-Evaluator | Human and LLM evaluators agree within tolerance |
| P5 | Process-Confidence Coupling | Confidence must match demonstrated rigor |

---

## 2. Dimensions & Weights

```
Dimension          Weight   What It Measures
─────────────────────────────────────────────────────────────
H-count            20%      Hypothesis generation breadth
Oscillation        20%      Perspective shifts / genuine deliberation
Crux               15%      Identification of decision-critical factors
Epistemic Honesty  15%      Uncertainty acknowledgment accuracy
Process Integrity  10%      Logical coherence, no contradictions
Actionability      10%      Concrete, executable recommendations
Brevity             5%      Information density (signal/noise)
Format              5%      Structure aids comprehension
─────────────────────────────────────────────────────────────
TOTAL             100%
```

**Mode** (not scored): Classify as `explore` | `converge` | `hybrid`

---

## 3. Scoring Quick Reference

```
┌─────────────────┬───────────────────┬───────────────────┬───────────────────┐
│ Dimension       │ 0 (Fail)          │ 5 (Adequate)      │ 10 (Excellent)    │
├─────────────────┼───────────────────┼───────────────────┼───────────────────┤
│ H-count         │ 0-1 hypotheses    │ 3-4 hypotheses    │ 6+ with rationale │
│ Oscillation     │ No perspective    │ 2-3 shifts,       │ 4+ genuine shifts │
│                 │ shifts            │ surface level     │ with synthesis    │
│ Crux            │ Crux not          │ Crux stated,      │ Crux explicit,    │
│                 │ identified        │ weakly justified  │ drives conclusion │
│ Epistemic       │ False certainty   │ Some hedging,     │ Calibrated        │
│ Honesty         │ or false doubt    │ not calibrated    │ uncertainty       │
│ Process         │ Contradictions,   │ Minor gaps,       │ Fully coherent,   │
│ Integrity       │ circular logic    │ recoverable       │ traceable         │
│ Actionability   │ Vague or no       │ General           │ Specific, scoped, │
│                 │ recommendations   │ recommendations   │ prioritized       │
│ Brevity         │ >50% filler       │ 10-30% filler     │ <10% filler,      │
│                 │                   │                   │ high density      │
│ Format          │ Wall of text      │ Basic structure   │ Hierarchy aids    │
│                 │                   │                   │ comprehension     │
└─────────────────┴───────────────────┴───────────────────┴───────────────────┘
```

---

## 4. Hard Fail Conditions

Any of these = **automatic score 0**, regardless of other dimensions:

| Code | Condition | Example |
|------|-----------|---------|
| HF1 | Factual fabrication | Invented citations, false statistics |
| HF2 | Contradictory conclusion | "X is true" after proving "X is false" |
| HF3 | Complete crux miss | Ignores the actual decision point |
| HF4 | Dangerous recommendation | Advice that could cause harm if followed |
| HF5 | Confidence-process mismatch >3 tiers | 95% confidence with zero analysis |

---

## 5. Process-Confidence Coupling (CRITICAL)

**The core innovation.** Confidence level must be *earned* by demonstrated process rigor.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PROCESS-CONFIDENCE COUPLING TABLE                        │
├──────────────┬──────────────┬──────────────┬──────────────┬────────────────┤
│ Confidence   │ Min H-count  │ Min Osc      │ Crux         │ Epistemic Req  │
│ Expressed    │ Required     │ Required     │ Required     │                │
├──────────────┼──────────────┼──────────────┼──────────────┼────────────────┤
│ >90%         │ 5+           │ 4+           │ Explicit +   │ Addressed      │
│ "certain"    │              │              │ justified    │ counterargs    │
├──────────────┼──────────────┼──────────────┼──────────────┼────────────────┤
│ 70-90%       │ 4+           │ 3+           │ Explicit     │ Key caveats    │
│ "likely"     │              │              │              │ noted          │
├──────────────┼──────────────┼──────────────┼──────────────┼────────────────┤
│ 50-70%       │ 3+           │ 2+           │ Stated       │ Uncertainty    │
│ "possible"   │              │              │              │ quantified     │
├──────────────┼──────────────┼──────────────┼──────────────┼────────────────┤
│ <50%         │ 2+           │ 1+           │ Attempted    │ Limits         │
│ "uncertain"  │              │              │              │ acknowledged   │
└──────────────┴──────────────┴──────────────┴──────────────┴────────────────┘

VIOLATION PENALTY:
- 1 tier gap:  -10 points
- 2 tier gap:  -25 points
- 3+ tier gap: HARD FAIL (HF5)

Example: Claims 95% confidence but only 2 hypotheses explored = 3 tier gap = HF5
```

---

## 6. Tier System

```
Tier    Label          Score Range    Action Required
────────────────────────────────────────────────────────
 0      Hard Fail      0              Reject, escalate
 1      Soft Fail      1-49           Reject, revise
 2      Warning        50-69          Flag, may accept with caveats
 3      Pass           70-100         Accept
────────────────────────────────────────────────────────
```

**Acceptance Gates:**

| Gate | Threshold | Bypass Condition |
|------|-----------|------------------|
| Hard Fail | Any HF1-HF5 | None |
| Soft Fail | Score < 50 | Manual override with justification |
| Warning | Score < 70 | Acknowledged by consumer |
| Pass | Score >= 70 | None required |

---

## 7. Baseline Targets

Targets (vs. naive single-shot):

| Metric | Baseline | Target | Improvement |
|--------|----------|--------|-------------|
| H-count | 1.2 avg | 3.5 avg | +192% |
| Oscillation | 0.3 avg | 2.8 avg | +833% |
| Coupling violations | 45% | <10% | -78% |

---

## 8. Calibration Example

**Prompt:** "Should our startup pivot from B2B to B2C?"

**Response excerpt:**
> Let me think through this systematically...
>
> **Hypotheses considered:**
> 1. B2C could expand TAM 10x but CAC increases 5x
> 2. Current B2B has 18-month runway, B2C pivot needs 24mo
> 3. Team has B2B DNA, B2C requires different skills
> 4. Hybrid model could preserve B2B while testing B2C
> 5. Market timing favors consumer spend in 2024
>
> **Oscillation:** Initially leaned B2C (larger market), then reconsidered
> (execution risk), then evaluated hybrid (balanced), finally synthesized
> position based on runway constraint.
>
> **Crux identified:** The 18-month runway is the crux—insufficient for
> full B2C pivot given CAC ramp time. Hybrid only viable with bridge funding.
>
> **Recommendation:** Pursue hybrid with 70% confidence. Contingent on
> securing 12-month bridge by Q2. If bridge fails, optimize B2B unit economics.
>
> **Caveats:** Assumes current burn rate; macro conditions could shift;
> team capacity for parallel execution untested.

**Scoring:**

```
Dimension        Score   Rationale
─────────────────────────────────────────────────────────────
H-count          8       5 hypotheses, rationale provided
Oscillation      8       4 shifts with synthesis
Crux             9       Explicit, justified, drives conclusion
Epistemic        8       70% confidence, caveats noted
Process          9       Coherent, no contradictions
Actionability    9       Specific, scoped, contingent
Brevity          7       Tight, minimal filler
Format           8       Clear structure
─────────────────────────────────────────────────────────────

Coupling check: 70% confidence requires 4+ H, 3+ Osc
                Actual: 5 H, 4 Osc → No penalty

Calculation:
  (8×.20) + (8×.20) + (9×.15) + (8×.15) + (9×.10) +
  (9×.10) + (7×.05) + (8×.05) = 8.3

Final: 83/100 → Tier 3 (Pass)
```

---

## Appendix: Mode Classification

Not scored, but tracked for analysis:

| Mode | Characteristics | Typical Use |
|------|-----------------|-------------|
| Explore | High H-count, high oscillation, lower confidence | Open-ended questions |
| Converge | Focused H-count, synthesized oscillation, higher confidence | Decision support |
| Hybrid | Explore → Converge pattern within response | Complex analysis |

---

*Framework version 1.0 | Process-Confidence Coupling is the differentiating metric.*
