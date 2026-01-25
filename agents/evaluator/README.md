# Evaluator Agent

**Status**: Planned

Runs batch evaluations and computes aggregate metrics.

## Capabilities

- **Batch execution**: Run prompts against benchmark datasets
- **Cross-provider**: Compare Claude vs OpenAI vs Google vs xAI
- **Cost tracking**: Token usage, latency, $/query

## Datasets

Uses benchmarks from `/evaluation/benchmark_data/`:
- GPQA Diamond (PhD-level science)
- MATH-500 (competition math)
- MMLU STEM (college-level)
- GSM8K (baseline)

## Integration

```
/evaluation/benchmark_data/ → loaded by → evaluator → results → /data/analysis/
```

## Metrics

Computes cost equation from `/evaluation/benchmarks/equ.md`:
```
Total Cost = (Tokens × Price) + (Turns × User Time) + (Clarifications × Frustration) + ...
```
