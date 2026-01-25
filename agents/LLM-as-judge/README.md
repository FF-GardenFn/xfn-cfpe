# LLM-as-Judge Agent

**Status**: Planned

Scores response pairs against evaluation rubric, produces preference pairs for RFT.

## Capabilities

- **Rubric scoring**: 8-dimension evaluation (H-count, oscillation, crux, epistemic honesty, etc.)
- **Preference pairs**: chosen/rejected format for training
- **Aggregate metrics**: win rate, score delta, per-dimension breakdown

## Design Spec

See `/designs/rft-evaluator/DESIGN.md` for full specification.

## Integration

```
/src/get_responses/ → produces pairs → LLM-as-judge → preference data
                                                    → training pipeline
```

## Rubric

Uses Process-Confidence Coupling from `/evaluation/benchmarks/evaluation_framework.md`:
- High confidence + shallow process = failure
- Low confidence + deep oscillation = acceptable
