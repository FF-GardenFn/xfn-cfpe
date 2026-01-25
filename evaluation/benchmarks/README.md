# Dialectica Evaluation Framework

Standards for measuring dialectical reasoning prompt efficacy.

---

## Structure

```
benchmarks/
├── README.md                    # This file
├── equ.md                       # Cost equations
├── evaluation_framework.md      # CONSOLIDATED: principles + metrics + rubric
├── methodologies.md             # Collection methods + multi-turn + cross-provider
├── test_cases.jsonl             # Test corpus (15 cases)
└── archive/
    ├── TEMPLATE_generic.md      # Generic template (archived)
    └── api_price_anthropic.md   # Pricing reference (archived)
```

---

## Document Flow

```
evaluation_framework.md ──→ WHAT we measure (dimensions, targets, scoring)
         │
         ▼
methodologies.md ────────→ HOW we measure (collection, automation, judges)
         │
         ▼
test_cases.jsonl ────────→ WHAT we test on (15 cases, multi-domain)
         │
         ▼
equ.md ──────────────────→ HOW we cost (token + time + frustration)
```

---

## Key Innovations

### 1. Process-Confidence Coupling (evaluation_framework.md)
Confidence must trace to demonstrated dialectical work.
High confidence + shallow process = failure.
Low confidence + deep oscillation = acceptable.

### 2. Multi-Turn Evaluation (methodologies.md)
Single-turn metrics insufficient. Framework tracks:
- Clarification efficiency (questions asked vs. info gained)
- Convergence rate (turns to stable answer)
- Consistency under probing (position drift detection)

---

## Core Insight

> *"The measure of output is not confidence of tone, but rigor of process."*

Evaluates not just WHAT conclusions emerge, but WHETHER reasoning involved genuine oscillation between competing hypotheses.

---

## Quick Start

1. Read `evaluation_framework.md` → understand dimensions + targets
2. Load `test_cases.jsonl` → run prompts against corpus
3. Apply `methodologies.md` → collect metrics (LLM-judge or manual)
4. Compute cost via `equ.md` → compare variants holistically

**Run evaluation**:
```bash
python -m get_responses.cli compare --queries evaluation/benchmarks/test_cases.jsonl --treatment dialectica
```

See `/src/get_responses/` for full cross-provider testing framework.

---

## Files

| File | Lines | Purpose |
|------|-------|---------|
| evaluation_framework.md | ~350 | Principles, metrics, rubric (consolidated) |
| methodologies.md | ~420 | Collection methods, multi-turn, cross-provider |
| test_cases.jsonl | 15 | Test corpus with expected modes |
| equ.md | 13 | Cost equations |
