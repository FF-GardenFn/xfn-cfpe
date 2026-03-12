---
description: Generate a full markdown report for a specific experiment or the latest run, with structured comparison against baseline and best
argument-hint: "[--step N | --latest]"
allowed-tools: [Bash, Read]
---

# /report -- Generate Experiment Report

Generate a detailed report for a specific experiment checkpoint and present structured comparison analysis.

## Environment

```bash
export TI_ROOT="/Users/hyperexploiter/PycharmProjects/XFN-CFPE /training_insights"
export PYTHONPATH="/Users/hyperexploiter/PycharmProjects/XFN-CFPE :$PYTHONPATH"
export PYTHON="$TI_ROOT/../bin/python3"
```

## Run

For the latest experiment:
```bash
cd "$TI_ROOT" && PYTHONPATH="/Users/hyperexploiter/PycharmProjects/XFN-CFPE " $PYTHON -m training_insights report --latest
```

For a specific step:
```bash
cd "$TI_ROOT" && PYTHONPATH="/Users/hyperexploiter/PycharmProjects/XFN-CFPE " $PYTHON -m training_insights report --step $ARGUMENTS
```

## Comparison Protocol

After the report is generated, read the report file and construct two comparisons. Both are mandatory -- do not present one without the other.

### Comparison 1: vs Baseline

The baseline is the most recent KEEP experiment. Both `baseline_bpb` and `baseline_composite` advance together on each KEEP. On session resume, the baseline is the best-composite-R kept experiment from the prior session.

For each metric, compute and present the delta:
- val_bpb: absolute and relative change (lower is better)
- CORE score: absolute change
- MFU: absolute change (percentage points)
- Wall time: absolute and relative change
- Peak VRAM: absolute change
- Composite reward R: absolute change
- Safety penalty: absolute change

Flag any metric where the experiment is worse than baseline. A KEEP decision with degraded individual metrics means the composite reward offset the regression -- note which component compensated.

### Comparison 2: vs Current Best

The current best is the experiment with the highest composite reward R in the history (read from results.tsv or the report metadata).

For each metric, compute the delta relative to the best:
- If this experiment IS the new best: state this explicitly and note by how much it surpassed the previous best
- If this experiment is NOT the best: state the gap to the best and identify which metric dimension is responsible for the gap (quality, cost, or safety)

### Comparison Output Format

```
EXPERIMENT REPORT: Step <N>
  Hypothesis: <full hypothesis string>
  Decision: KEEP / DISCARD
  Gate: <which gate triggered, if DISCARD>

METRICS
  val_bpb:    <value>  (baseline: <value>, delta: <delta>, <pct>%)
  CORE score: <value>  (baseline: <value>, delta: <delta>)
  MFU:        <value>% (baseline: <value>%, delta: <delta>pp)
  Wall time:  <value>s (baseline: <value>s, delta: <delta>s, <pct>%)
  Peak VRAM:  <value>GB (baseline: <value>GB, delta: <delta>GB)
  Safety:     <value>  (baseline: <value>, delta: <delta>)

COMPOSITE REWARD BREAKDOWN
  Quality (alpha=1.0): <value>
    BPB component (60%):  <value>
    CORE component (30%): <value>
    MFU component (10%):  <value>
  Cost (beta=0.5):    <value>
    Time component (70%):  <value>
    VRAM component (30%):  <value>
  Safety (gamma=2.0): <value>
  R = <value>  (deltaR = <value> vs baseline)

VS CURRENT BEST (step <N>, R=<value>)
  <This experiment is the new best / Gap to best: <deltaR>, driven by <dimension>>

FAMILY IMPACT
  Family: <name>
  Experiments in family: <n> (kept: <n>, discarded: <n>)
  Family mean deltaR: <value>
  Family verdict: <promising / dead-end / neutral>
```

## Structured Output Requirements

1. Every numeric value in the output must come from the report data or results.tsv. Do not estimate or round beyond one decimal place.
2. The comparison deltas must be arithmetically correct: delta = current - reference. Verify the sign.
3. If a metric is unavailable (e.g., CORE score not computed for this experiment), state "N/A" rather than omitting the row.
4. The family impact section requires reading the analyze output or results.tsv to compute family-level statistics. Run `ti analyze` if this data is not available in the report itself.
5. If $ARGUMENTS specifies a step number that does not exist, report the error and list available steps from results.tsv.
