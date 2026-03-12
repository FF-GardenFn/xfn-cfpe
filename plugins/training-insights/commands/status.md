---
description: Show the Training Insights experiment dashboard -- best BPB, reward, Pareto frontier, family attribution, safety drift
argument-hint: ""
allowed-tools: [Bash, Read]
---

# /status -- Experiment Dashboard

Show the current state of all training experiments and provide structured interpretation.

## Environment

```bash
export TI_ROOT="/Users/hyperexploiter/PycharmProjects/XFN-CFPE /training_insights"
export PYTHONPATH="/Users/hyperexploiter/PycharmProjects/XFN-CFPE :$PYTHONPATH"
export PYTHON="$TI_ROOT/../bin/python3"
```

## Run

```bash
cd "$TI_ROOT" && PYTHONPATH="/Users/hyperexploiter/PycharmProjects/XFN-CFPE " $PYTHON -m training_insights status
```

## Interpretation Gates

After displaying the dashboard output, process each section through its interpretation gate. Each gate asks specific questions -- answer them from the data, do not speculate.

### Gate 1: Experiment Counts

Dashboard shows: total experiments, kept, discarded, crashed.

Interpret:
- **Keep rate**: kept / total. Below 30% indicates the search is in a difficult region or hypotheses are poorly targeted. Above 70% may indicate the threshold is too lenient or the search is in a well-explored convex region.
- **Crash rate**: crashed / total. Above 10% indicates stability issues -- parameter space is being explored too aggressively near boundaries (OOM, NaN, divergence).
- **Discard distribution**: Are discards clustered in specific families or spread evenly? Clustered discards signal a dead-end family. Spread discards signal noisy optimization.

### Gate 2: Best Metrics

Dashboard shows: best val_bpb, best composite reward, best hypothesis.

Interpret:
- **BPB trajectory**: Is best val_bpb improving over recent experiments? Stagnation for 5+ experiments suggests the current search direction is exhausted.
- **Reward vs BPB alignment**: Does the best-reward experiment also have the best BPB? Divergence indicates cost or safety penalties are significant factors -- the highest-quality experiment is not the most efficient or safest.
- **Best hypothesis family**: Which family produced the best result? This is the strongest signal for where to focus next.

### Gate 3: Family Attribution Table

Dashboard shows: hyperparameter families with verdicts, experiment counts, mean deltaR.

Interpret:
- **Promising families**: List families with positive mean deltaR. For each, note n_experiments and whether deltaR is increasing or decreasing across successive experiments (diminishing returns check).
- **Dead-end families**: List families with consistently negative deltaR. These are hard constraints -- do not recommend experiments in these families.
- **Neutral/insufficient**: List families with insufficient data. These represent unexplored territory and may be high-information-value targets.
- **Family coverage**: Are there hyperparameter families from the priority list (learning rates, window pattern, batch size, depth, warmdown, weight decay) that have zero experiments? Flag these as unexplored.

### Gate 4: Safety Status

Dashboard shows: safety drift, CAI inversion detection.

Interpret:
- **If no drift**: Safety is stable. Proceed normally.
- **If positive drift (safety degrading)**: Identify the trend. Is it gradual (accumulating small penalties) or step-change (one experiment caused a jump)? Trace to the causal experiment if possible.
- **If CAI inversion detected**: This is a critical finding. Report it prominently. The recommended action is to halt optimization in the direction that caused inversion and investigate the mechanism. Capability gains that degrade safety are not net improvements.

### Gate 5: Pareto Frontier

Dashboard shows: quality-cost optimal experiments.

Interpret:
- **Frontier size**: How many experiments are Pareto-optimal? A single-point frontier means all other experiments are dominated in at least one dimension. A multi-point frontier means genuine tradeoffs exist.
- **Frontier shape**: Are the Pareto-optimal experiments clustered (similar quality-cost profiles) or spread (diverse tradeoff options)?
- **Dominated experiments**: How many experiments are strictly dominated? High domination rate means the search is finding clearly better alternatives -- this is good. Low domination rate means experiments are trading quality for cost without clear improvement.

## Structured Takeaway Format

After processing all gates, present a takeaway in this format:

```
STATUS SUMMARY
  Experiments: <total> (<kept> kept, <discarded> discarded, <crashed> crashed)
  Keep rate: <pct>%
  Best val_bpb: <value> (step <N>, hypothesis: <name>)
  Best reward: <value> (step <N>)

KEY FINDINGS
  1. <Most important finding from gates, with numbers>
  2. <Second most important finding>
  3. <Third finding, if applicable>

DECISION GUIDANCE
  <One of the following, based on dashboard state:>

  [If promising families exist with room to explore]:
  CONTINUE: <family> family has positive trajectory (mean deltaR=<value>, n=<count>).
  Recommended next step: <specific hypothesis>.

  [If all families near saturation]:
  PIVOT: Current families approaching diminishing returns. Consider unexplored families:
  <list unexplored families from priority order>.

  [If safety inversion detected]:
  HALT: Safety inversion detected. Investigate before continuing.
  Source: step <N>, mechanism: <description>.

  [If high crash rate]:
  STABILIZE: <crash_rate>% crash rate. Reduce step sizes or investigate failure modes
  before continuing search.

  [If insufficient data]:
  EXPLORE: Only <N> experiments total. Need more data before drawing conclusions.
  Start with highest-priority unexplored family.
```
