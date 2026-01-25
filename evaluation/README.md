# Evaluation Framework

Measurement infrastructure for the DIALECTICA research program.

---

## Structure

```
evaluation/
├── benchmarks/                    # Evaluation definitions
│   ├── evaluation_framework.md    # WHAT we measure (8 dimensions)
│   ├── methodologies.md           # HOW we measure (6 methods)
│   ├── test_cases.jsonl           # Test corpus (15 cases)
│   └── equ.md                     # Cost equations
│
└── benchmark_data/                # Datasets (6,222 examples)
    ├── gpqa_diamond.jsonl         # PhD-level science (198)
    ├── math_500.jsonl             # Competition math (500)
    ├── mmlu_stem.jsonl            # College STEM (1,705)
    ├── gsm8k_test.jsonl           # Grade school baseline (1,319)
    └── hle/                       # Humanity's Last Exam (2,500)
```

---

## Connection to Research Program

| Layer | Component | Evaluation Role |
|-------|-----------|-----------------|
| **Prompt** | DIALECTICA | evaluation_framework.md defines 8-dimension rubric |
| **Training** | RL-O-CoV | Rubric scores → reward signals |
| **Business** | Cost Model | equ.md connects quality to operational cost |

The **Process-Confidence Coupling** metric (from `evaluation_framework.md`) directly informs RL-O-CoV's `resonance_reward`—both measure whether confidence traces to demonstrated reasoning.

---

## Quick Start

```bash
# Run single comparison
python -m get_responses.cli compare --query "Your question" --treatment dialectica

# Batch evaluation
python -m get_responses.cli batch \
  --queries evaluation/benchmarks/test_cases.jsonl \
  --prompts baseline,dialectica
```

See `/src/get_responses/` for full framework.

---

## Key Innovation

**Process-Confidence Coupling**: High confidence + shallow process = failure. Low confidence + deep oscillation = acceptable.

| Confidence | Required H-count | Required Oscillation |
|------------|------------------|---------------------|
| >90% | 5+ hypotheses | 4+ perspective shifts |
| 70-90% | 4+ | 3+ |
| 50-70% | 3+ | 2+ |
| <50% | 2+ | 1+ |

---

## Related Components

| Component | Purpose | Connection |
|-----------|---------|------------|
| `/src/get_responses/` | Execute evaluations | Runs tests, exports results |
| `/src/ANALYZER/` | Sentiment data | Calibrate frustration coefficient in equ.md |
| `/src/ARENA/` | Multi-turn evaluation | Measure escalation patterns |
| `/data/analysis/` | Results | Error rate calibration |
| `/designs/rft-evaluator/` | Design spec | Detailed rubric + preference pair format |