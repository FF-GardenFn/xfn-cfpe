# Training Insights — Experiment Log

Narrative log of experiment sessions. Each entry records the hypothesis,
the full composite reward breakdown, the decision rationale, and the insight
extracted for the next iteration.

The numbers come from `results.tsv` + per-experiment JSON in `runs/`.
The reasoning is written by the agent or researcher after each experiment.

---

## How to Write a Log Entry

```markdown
### Experiment N — KEEP / DISCARD

**Hypothesis**: [what you changed and why]
**Commit**: [short hash]

**Results**:
  val_bpb=X.XXXXXX  CORE=0.XXX  MFU=XX.X%  VRAM=XX.XGB  wall_time=XXXs
  R=±X.XXXX  (Q=X.XXX  C=X.XXX  S=X.XXX)

**Decision**: KEEP / DISCARD
**Reason**: [the evaluator's reason string]

**Insight**: [what this tells you about the model/training dynamics]
**Next**: [what this implies for the next hypothesis]
```

---

## Session Template

> Copy this block to start a new session.

```markdown
## Session: [date] — [tag]

Branch: autoresearch/[tag]
Platform: [GPU type, count]
Starting BPB: [baseline val_bpb]
Starting R:   [baseline composite reward]
```

---

## Example Session

### Session: 2026-03-10 — mar10

Branch: `autoresearch/mar10`
Platform: 1× H100 80GB
Starting BPB: 1.023400 (baseline)
Starting R:   +0.3821

---

### Experiment 1 — KEEP

**Hypothesis**: Baseline — establish BPB and composite reward baseline before any changes.
**Commit**: `a1b2c3d`

**Results**:
```
val_bpb=1.023400  CORE=0.248  MFU=42.3%  VRAM=38.2GB  wall_time=300.1s
R=+0.3821  (Q=0.512  C=0.481  S=0.000)
```

**Decision**: KEEP
**Reason**: first valid result — baseline composite R=+0.3821

**Insight**: Baseline is healthy. MFU 42.3% on H100 is reasonable for this model size.
CORE 0.248 gives headroom. Safety clean.
**Next**: Try embedding_lr first — it's a high-leverage single parameter with a clear
theory (embeddings may be underfitting given the 4-group LR structure).

---

### Experiment 2 — KEEP

**Hypothesis**: Increase `embedding_lr` from 0.6 → 0.8. Theory: embedding LR is
the bottleneck — with separate LR groups, embeddings may be undertrained relative
to the rest of the network at LR=0.6.
**Commit**: `b4e1f9a`

**Results**:
```
val_bpb=1.019800  CORE=0.251  MFU=42.1%  VRAM=38.2GB  wall_time=300.3s
R=+0.3944  (Q=0.531  C=0.479  S=0.000)
```

**Decision**: KEEP
**Reason**: composite R improved +0.0123 (R=+0.3944, BPB delta=−0.003600)

**Insight**: Hypothesis confirmed. Embedding LR increase improved both BPB (−0.0036)
and CORE (+0.003). Cost negligible (same VRAM, ~0.2s more wall time). Safety clean.
The theory holds: embeddings were undertrained.
**Next**: Try pushing embedding_lr further (0.8 → 0.9) to find the ceiling.
Also consider unembedding_lr — same logic applies.

---

### Experiment 3 — DISCARD

**Hypothesis**: Change `WINDOW_PATTERN` from `SSSL` → `SSLL`. Theory: more local
attention layers might help with token-level pattern matching.
**Commit**: `e5d2b8f`

**Results**:
```
val_bpb=1.024500  CORE=0.245  MFU=40.8%  VRAM=39.1GB  wall_time=302.7s
R=+0.3701  (Q=0.498  C=0.482  S=0.000)
```

**Decision**: DISCARD
**Reason**: composite R=+0.3701 did not improve (delta=−0.0243, BPB delta=+0.004700)

**Insight**: Window pattern change hurt on all dimensions — BPB regressed, CORE dropped,
MFU dropped slightly. SSLL allocates more local attention, but the model appears to
benefit from the global attention layers (S) that SSSL provides.
**Next**: Window pattern is a dead-end for now. Flag family as `dead_end` in insight engine.
Return to LR family — try unembedding_lr.

---

### Experiment 4 — DISCARD

**Hypothesis**: Double `TOTAL_BATCH_SIZE` from 512k → 1024k. Theory: larger batches
smooth gradient noise, potentially allowing more aggressive LR without divergence.
**Commit**: `c9a3f7e`

**Results**:
```
val_bpb=1.018700  CORE=0.249  MFU=38.1%  VRAM=71.4GB  wall_time=298.1s
R=+0.3612  (Q=0.541  C=0.891  S=0.000)
```

**Decision**: DISCARD
**Reason**: BPB improved +0.001100 but composite R=+0.3612 did not improve
(cost or safety offset quality gain). VRAM 71.4GB → cost score 0.891.

**Insight**: **This is the key insight composite reward catches that val_bpb misses.**
BPB improved, but the cost penalty from 71.4GB VRAM (vs 38GB baseline) overwhelmed
the quality gain. This experiment would have been KEPT under the old single-metric loop.
Under composite reward, it's correctly discarded: the marginal BPB gain isn't worth
consuming 90% of GPU memory.
**Next**: Batch size at this scale is a dead-end unless we're on multi-GPU. Note this
finding. Continue with LR family.

---

*Log continues as experiments run. Each entry is written after the evaluator decision,
before the next hypothesis is proposed.*
