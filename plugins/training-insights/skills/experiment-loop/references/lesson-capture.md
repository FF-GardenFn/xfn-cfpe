# Lesson Capture Protocol

## Purpose

Lessons persist across experiment sessions. Without persistent memory, the
same failed directions get re-explored, the same boundary conditions get
re-discovered, and the same diagnostic triggers get re-diagnosed from scratch.

The lesson capture protocol eliminates this by appending structured entries
after every experiment. The insight engine reads lessons as prior context
when generating the next hypothesis.

## Storage

Lessons live at `$TI_ROOT/experiment_lessons.md` (per-iteration) and
`$TI_ROOT/lessons.md` (per-session summary).

### Per-Iteration Format (experiment_lessons.md)

One line per experiment:

```
[YYYY-MM-DD] step#<N> <KEEP|DISCARD> "<hypothesis>" deltaR=<value> | <key learning>
```

Examples:
```
[2026-03-11] step#1 KEEP "baseline (no changes)" deltaR=+0.1318 | Established baseline at val_bpb=1.0234, MFU=42.3%
[2026-03-11] step#2 KEEP "increase embedding_lr 0.6 -> 0.8" deltaR=+0.0163 | Embedding LR family confirmed promising
[2026-03-11] step#3 DISCARD "increase embedding_lr 0.8 -> 1.2" deltaR=-0.0412 | Upper bound between 0.8 and 1.2
[2026-03-11] step#4 DISCARD "switch window_pattern SSSL -> SSLL" deltaR=-0.0089 | SSLL degrades quality without cost savings
```

### Per-Session Format (lessons.md)

One structured block per experiment session (appended when the loop exits):

```markdown
## Lesson: [family] -- [direction] -- [date]

Direction: <researcher's original direction>
Experiments run: <N>
Kept / Discarded: <K> / <D>
Best delta-R: <value> (experiment <id>)
Family verdict: <promising | dead_end | neutral>

What worked: <1-2 sentences>
What failed: <1-2 sentences>
Structural insight: <what this reveals about the loss landscape>
Next time: <what to do differently if revisiting this family>
```

## When to Capture

### Per-Iteration (experiment_lessons.md)

After every Phase 4 (Decision) completion in the experiment loop.
Mandatory for both KEEP and DISCARD. A DISCARD without a lesson captured
is information lost.

### Per-Session (lessons.md)

After the experiment loop exits (any of the four terminal states).
This is a synthesis of the full session, not a repetition of individual
iteration entries.

## What Makes a Good Lesson

### Good lessons are:

- **Specific**: "embedding_lr=1.2 diverged (BPB +4.1%)" not "high LR bad"
- **Bounded**: "upper bound between 0.8 and 1.2" narrows the search space
- **Causal**: "OOM at batch_size=128 because DEPTH=12 increased param count"
- **Actionable**: "next time start at 0.9 instead of 1.2"

### Bad lessons are:

- **Vague**: "didn't work" -- no information content
- **Redundant**: repeating the hypothesis without adding interpretation
- **Speculative**: "probably would work with longer training" -- untested

## Integration with Agent Context

The InsightEngine reads only `results.tsv` and `runs/*.json` -- it does NOT
read `lessons.md` directly. Lessons influence the experiment loop because the
**agent** reads `lessons.md` as prior context when entering Phase 1
(Reconnaissance). The agent uses lessons to:

1. **Boundary constraints**: Known divergence points eliminate parameter
   values from consideration without re-testing.

2. **Family priors**: "What worked" and "What failed" entries bias the
   agent's hypothesis formation toward proven directions.

3. **Diagnostic shortcuts**: "OOM at batch_size=128 with DEPTH=12" prevents
   the agent from proposing batch_size=128 when DEPTH >= 12.

## Relationship to Forge Lesson Pattern

This protocol adapts the Forge orchestration system's lesson capture pattern
for the training experiment domain. Key adaptation:

- Forge captures lessons about test design and convergence loop behavior
  (oscillation, scope violations, iteration counts).
- Training Insights captures lessons about the hyperparameter loss landscape
  (parameter boundaries, family interactions, diagnostic trigger causes).
- Both share the structural principle: persistent memory prevents repeated
  mistakes and compounds learning across sessions.
