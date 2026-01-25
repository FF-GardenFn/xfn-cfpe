# Data Directory

Experimental results from DIALECTICA prompt evaluation across the Claude model family.

## Structure

```
data/
├── {model}/                    # Model-specific results (haiku, sonnet, opus)
│   ├── baseline/               # Standard Claude responses
│   └── dialectica/             # DIALECTICA-enhanced responses
├── benchmarks/                 # GPQA and HLE baseline evaluations
├── adversarial/                # Adversarial scenario testing (6 files)
├── analysis/                   # Evaluation reports and findings (9 files)
├── multi_turn/                 # Multi-turn conversation evaluations (2 files)
└── archive/                    # Historical experimental runs
    ├── 2026-01-16/             # Initial Opus baseline vs dialectica (23 files)
    └── 2026-01-17/             # Cross-model validation (50 files)
```

## Models

| Model | Baseline | Dialectica | Model ID |
|-------|----------|------------|----------|
| **haiku** | 13 | 17 | claude-haiku-4-5-20251001 |
| **sonnet** | 5 | 12 | claude-sonnet-4-20250514 |
| **opus** | 12 | 11 | claude-opus-4-5-20251101 |

## File Naming

`{model}_{condition}_q{N}_{HHMMSS}.json`

Examples:
- `haiku_baseline_q1_125540.json`
- `opus_dialectica_q7_162638.json`
- `test_run_dialectica_20260123_132044.json`

## Query Schema

```json
{
  "query_id": "q1",
  "category": "Personal/Impossible Choice",
  "mode_requested": "MEGATHINK|ULTRATHINK|null",
  "model": "claude-{model}-{version}",
  "input_tokens": 391,
  "output_tokens": 631,
  "latency_ms": 17879.43,
  "answer": "...",
  "thinking": "..."
}
```

## Related

- `/content/prompts/dialectica/` - DIALECTICA prompt definitions
- `/content/tests_queries/` - Test question sets
- `/src/get_responses/` - Testing framework