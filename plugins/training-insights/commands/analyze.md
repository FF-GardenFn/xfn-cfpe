---
description: Extract deep insights from experiment history -- family attribution, Pareto frontier, safety drift, next hypothesis suggestions
argument-hint: "[optional: --output insights.md]"
allowed-tools: [Bash, Read]
---

# /analyze -- Extract Training Insights

Run the full insight analysis on experiment history and present structured findings.

## Environment

```bash
export TI_ROOT="/Users/hyperexploiter/PycharmProjects/XFN-CFPE /training_insights"
export PYTHONPATH="/Users/hyperexploiter/PycharmProjects/XFN-CFPE :$PYTHONPATH"
export PYTHON="$TI_ROOT/../bin/python3"
```

## Run

```bash
cd "$TI_ROOT" && PYTHONPATH="/Users/hyperexploiter/PycharmProjects/XFN-CFPE " $PYTHON -m training_insights analyze
```

If the researcher provided additional context or flags via $ARGUMENTS, append them to the command.

## Structured Interpretation Protocol

After running, process the output through four sequential steps. Do not skip steps or merge them.

### Step 1: Family Verdict Extraction

For every hyperparameter family in the output, record:
- Family name
- n_experiments and n_kept
- mean deltaR (cite the exact number)
- Current verdict: promising / dead-end / neutral / insufficient_data
- Verdict change since last analysis (if detectable from the data): e.g., "neutral -> promising" or "unchanged"

If a family has fewer than 3 experiments, flag it as low-confidence regardless of verdict.

### Step 2: Pareto Frontier Assessment

From the analysis output, determine:
- Which experiments are currently on the Pareto frontier (cite step numbers)
- Whether recent experiments pushed the frontier outward (frontier advancing) or landed behind it (frontier stagnant)
- The gap on the frontier where the next experiment has the highest probability of extending it

### Step 3: Safety Drift Evaluation

Extract from the output:
- Current safety penalty level
- Drift direction and magnitude (cite numbers)
- CAI inversion status: YES/NO
- If YES: which experiment(s) caused inversion, what was the capability gain vs safety loss

Safety inversion findings override all other recommendations. If inversion is present, the primary recommendation must address it.

### Step 4: Next Experiment Recommendation

Synthesize steps 1-3 into a specific, actionable recommendation:
- State the recommended hypothesis in full format: `"<action> <parameter> <old> -> <new> -- <rationale>"`
- Cite the quantitative basis: which family verdict, what mean deltaR, what frontier position
- State the expected outcome and what will be learned regardless of KEEP/DISCARD
- If the insight engine's own suggestion conflicts with the data patterns from steps 1-3, note the discrepancy and explain which recommendation is better supported

## Output Format

Present findings in this structure:

```
FAMILY ATTRIBUTION
  <family>: <verdict> (n=<count>, kept=<count>, mean deltaR=<value>) [confidence: high/medium/low]
  ...

PARETO FRONTIER
  Frontier experiments: steps <list>
  Frontier status: advancing / stagnant / regressed
  Highest-leverage gap: <description>

SAFETY STATUS
  Drift: <magnitude> (<direction>)
  CAI inversion: YES/NO
  [If YES: source experiments and magnitude]

RECOMMENDED NEXT EXPERIMENT
  Hypothesis: "<full hypothesis string>"
  Basis: <quantitative justification citing specific deltaR values and family data>
  Expected information value: <what we learn regardless of outcome>
```

If the researcher's $ARGUMENTS contain a specific question, answer that question directly after the structured output, citing relevant data from the analysis.
