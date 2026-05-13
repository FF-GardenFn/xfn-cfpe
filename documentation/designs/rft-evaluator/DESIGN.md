# RFT Evaluator

## Purpose

Automated evaluation agent for comparing baseline vs treatment LLM responses. Produces:

1. **Preference pairs** (chosen/rejected) for RFT training
2. **Rubric scores** per dimension
3. **Aggregate metrics** (win rate, score delta)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    RFT Evaluator                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   Input     │───▶│  Evaluator  │───▶│   Output    │     │
│  │   Loader    │    │    Core     │    │   Writer    │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│         │                 │                   │            │
│         ▼                 ▼                   ▼            │
│   Query +            Rubric              Preference        │
│   Response Pairs     Engine              Pairs (JSONL)     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Evaluation Rubric (Dialectica)

| Dimension | Weight | 0 (Fail) | 1 (Adequate) | 2 (Excellent) |
|-----------|--------|----------|--------------|---------------|
| **H-count** | 25% | Single view only | 2 hypotheses | 3+ with non-obvious |
| **Crux Clarity** | 25% | No cruxes | Vague "it depends" | Named + typed + resolution path |
| **Epistemic Honesty** | 20% | False certainty | Confidence stated | + justified + falsifiable |
| **Actionability** | 15% | "Think about it" | Generic steps | Specific + sequenced |
| **Brevity** | 15% | Buried in verbosity | Adequate | Tight + clear |

**Score**: `(h×.25 + crux×.25 + epistemic×.20 + action×.15 + brevity×.15) / 2.0` → 0-1 scale

---

## Input Format

```json
{
  "query_id": "q1",
  "query": "Should we prioritize growth or profitability?",
  "baseline": {
    "response": "You should focus on growth because...",
    "model": "claude-sonnet-4-20250514",
    "tokens": 450
  },
  "treatment": {
    "response": "## Hypotheses\n\n**H1: Growth-First**...",
    "model": "claude-sonnet-4-20250514",
    "tokens": 1200
  }
}
```

---

## Output Format

```json
{
  "query_id": "q1",
  "chosen": {"response": "## Hypotheses...", "source": "treatment"},
  "rejected": {"response": "You should focus...", "source": "baseline"},
  "scores": {
    "chosen": {"h_count": 2, "crux": 2, "epistemic": 2, "action": 2, "brevity": 1, "total": 0.90},
    "rejected": {"h_count": 0, "crux": 0, "epistemic": 0, "action": 1, "brevity": 2, "total": 0.30}
  },
  "preference_strength": 0.60,
  "justification": "Treatment provides multi-hypothesis reasoning with explicit cruxes. Baseline converges prematurely."
}
```

---

## Evaluation Modes

| Mode | Method | Speed | Use When |
|------|--------|-------|----------|
| **Heuristic** | Pattern matching (regex for H1/H2, crux markers) | Fast | Quick filtering, large batches |
| **LLM-as-Judge** | Opus evaluates against rubric | Slow | Final scoring, nuanced judgment |
| **Hybrid** | Heuristic first, LLM for close calls (delta < 0.2) | Medium | Best accuracy/cost tradeoff |

### LLM Judge Prompt (Core)

```
You are an evaluation judge. Score these two responses against the Dialectica rubric.

## Query
{query}

## Response A / Response B
{responses}

## Rubric
[Dimensions with 0/1/2 criteria]

Output: {"response_a_scores": {...}, "response_b_scores": {...},
         "preferred": "A"|"B", "confidence": 0.0-1.0, "justification": "..."}
```

---

## Metrics

| Metric | Description |
|--------|-------------|
| **Treatment win rate** | % where treatment scores higher |
| **Avg score delta** | Mean (treatment - baseline) |
| **Top dimensions** | Which dimensions show largest improvement |
| **Judge agreement** | Multi-judge consistency (if used) |

---

## Extensions

| Extension | Purpose |
|-----------|---------|
| Multi-judge consensus | Require N judges to agree |
| Human-in-the-loop | Flag low-confidence for human review |
| Custom rubrics | Support rubrics beyond Dialectica |
| Reward model training | Use preference pairs to train reward model |
