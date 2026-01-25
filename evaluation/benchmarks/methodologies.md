# Evaluation Methodologies

---

## 1 Methodology Portfolio

| Method | Use For | Automation |
|--------|---------|------------|
| **Regex Extraction** | Structural elements (tables, confidence) | Full |
| **LLM-as-Judge** | Semantic quality (H-quality, crux clarity) | Semi |
| **Multi-Turn Eval** | Resolution efficiency across turns | Full |
| **Cross-Provider** | Normalize comparison across APIs | Full |
| **Process-Confidence** | Coupling validation | Full |
| **Human Spot-Check** | Judge calibration | Manual |

---

## 2 Regex Extraction

Automated extraction of structural elements from responses.

### 2.1 Oscillation Table Detection
Patterns: `| Hypothesis | Initial | Post-Oscillation |`, `| H[1-4] |`, `## Oscillation Results`

### 2.2 Confidence Extraction
Patterns: `**Confidence**: 0.XX`, `Confidence: 0.XX`, `confidence...0.XX`

### 2.3 Hypothesis Count
Patterns: `**H\d: ...**`, `## H\d:`, `Hypothesis \d:`

### 2.4 Crux Detection
- Locate `## Cruxes` section
- Check for type labels: empirical, value, definitional, factual, normative
- Count crux entries

---

## 3 LLM-as-Judge

### 3.1 Judge Prompt Template

```markdown
## Evaluate Dialectical Response Quality

### Response: {response}
### Query: {query}

### Scoring (0-10 each)

1. **Hypothesis Quality**: Distinct, defensible, non-strawman?
2. **Oscillation Depth**: Did stress-testing produce insights?
3. **Crux Precision**: Correctly identified and typed?
4. **Epistemic Calibration**: Confidence appropriate to evidence AND process?
5. **Actionability**: Next steps concrete and prioritized?

### Output (JSON)
{"h_quality": <0-10>, "oscillation_depth": <0-10>, "crux_precision": <0-10>,
 "epistemic_calibration": <0-10>, "actionability": <0-10>, "rationale": "..."}
```

### 3.2 Judge Configuration

- **Model**: claude-sonnet-4-20250514
- **Temperature**: 0.0
- **Max tokens**: 500
- **System**: "You are an evaluation judge for dialectical reasoning. Score objectively."

### 3.3 Multi-Judge Agreement

- Run `n_judges` (default: 3) independent evaluations
- Agreement threshold: ≤2 point spread on each dimension
- If disagreement → flag for human review

---

## 4 Multi-Turn Evaluation Protocol

**Key differentiator**: Measures "turns to resolution" - conversation turns until the model resolves the user's core uncertainty.

```
┌─────────────────────────────────────────────────────────────┐
│                    MULTI-TURN EVALUATION                    │
├─────────────────────────────────────────────────────────────┤
│  Query → Model → Response                                   │
│            ↓                                                │
│  LLM-Judge: "Does this resolve user's core uncertainty?"    │
│            ↓                                                │
│     ┌──────┴──────┐                                         │
│     │             │                                         │
│   [YES]         [NO]                                        │
│     ↓             ↓                                         │
│  RESOLVED    Follow-up → Loop (max 4 turns)                 │
└─────────────────────────────────────────────────────────────┘
```

### 4.1 Resolution Detection Judge

```markdown
## Resolution Assessment
### Query: {query}
### Conversation: {conversation_history}
### Latest Response: {response}

Determine if user's **core uncertainty** is resolved (can make decision, trade-offs clear).

### Output (JSON)
{"resolved": true|false, "confidence": <0.0-1.0>, "reasoning": "..."}
```

### 4.2 Follow-up Prompt

When `resolved: false`: `"Can you synthesize your analysis into a concrete recommendation?"`

### 4.3 Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| `turns_to_resolution` | Turns until resolved (1-4) | Lower |
| `first_turn_resolution_rate` | % resolved in turn 1 | Higher |
| `total_tokens` | Cumulative tokens | Lower |
| `cost_per_resolution` | Total cost / resolved | Lower |

### 4.4 Configuration

- `MAX_TURNS`: 4
- `FOLLOW_UP`: "Can you synthesize your analysis into a concrete recommendation?"

---

## 5 Cross-Provider Comparison Framework

**Core insight**: The RUBRIC is provider-agnostic. The COLLECTION METHOD adapts per API.

```
┌────────────────────────────────────────────────────────────┐
│              PROVIDER-AGNOSTIC EVALUATION                  │
├────────────────────────────────────────────────────────────┤
│  Same query → {Provider A, Provider B, ...}                │
│                     ↓                                      │
│  Normalize: tokens, latency, cost ($/MTok)                 │
│                     ↓                                      │
│  Apply: Identical LLM-as-judge rubric                      │
│                     ↓                                      │
│  Compare: Quality-adjusted cost efficiency                 │
└────────────────────────────────────────────────────────────┘
```

### 5.1 Provider Normalization

Each provider adapter normalizes:
- **Anthropic**: `usage.input_tokens`, `usage.output_tokens`
- **OpenAI**: `usage.prompt_tokens`, `usage.completion_tokens`
- **Google**: `usageMetadata.promptTokenCount`, `usageMetadata.candidatesTokenCount`

### 5.2 Normalized Result Fields

`provider`, `model`, `response`, `input_tokens`, `output_tokens`, `latency_ms`, `cost_usd`

Derived: `total_tokens`, `tokens_per_second`, `cost_per_mtok`

### 5.3 Quality-Adjusted Efficiency

`efficiency = composite_score / (cost_usd × 100)`

### 5.4 Comparison Output Schema

```json
{
  "query_id": "tc_001",
  "providers": {
    "anthropic": {
      "model": "claude-sonnet-4-20250514",
      "input_tokens": 1250, "output_tokens": 1847, "latency_ms": 3420,
      "cost_usd": 0.0156, "composite_score": 78.5
    },
    "openai": {
      "model": "gpt-4o",
      "input_tokens": 1250, "output_tokens": 2103, "latency_ms": 4150,
      "cost_usd": 0.0201, "composite_score": 56.0
    }
  },
  "comparison": {
    "best_quality": "anthropic", "best_cost": "anthropic",
    "quality_adjusted_efficiency": {"anthropic": 5.03, "openai": 2.79}
  }
}
```

---

## 6 Process-Confidence Coupling

**Validation logic**:
- Extract confidence level and check for oscillation table + stability markers
- Ceiling: 0.85 (oscillation + stable), 0.70 (oscillation only), 0.50 (iteration limit), 0.45 (default)
- Violation = confidence > ceiling → hard fail

---

## 7 Mode Accuracy

**Detection signals**: `## Hypotheses`, `**H\d:`, `## Cruxes`, `## Oscillation`, `**Confidence**`
- 2+ signals present → dialectic mode
- Otherwise → bypass mode

---

## 8 Human Spot-Check Protocol

**When**: LLM judges disagree | Pre-submission (20%) | Edge cases | PCC violations

**Procedure**: Blind review -> Apply rubric -> Compare -> Document disagreements

---

## 9 Output Schemas

**Per-Response**: query_id, hard_fail, score, metrics (h_count, oscillation, cruxes, confidence, pcc_valid, mode_correct), judge_scores

**Variant Summary**: variant, test_cases, hard_fails, mean_score, mode_accuracy, pcc_compliance, pass

**Multi-Turn Summary**: resolution_rate, first_turn_resolution_rate, mean_turns_to_resolution, cost_per_resolution

**Cross-Provider Summary**: providers_compared, rankings (by_quality, by_efficiency), provider_summaries
