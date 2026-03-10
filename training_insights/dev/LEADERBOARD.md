# Training Insights — Experiment Leaderboard

Results from the autonomous experiment loop. Sorted by composite reward R (descending).
Decision driver: composite R = α·quality − β·cost − γ·safety (not just val_bpb).

## TSV Schema

```
step  commit   val_bpb    core    mfu%   vram_gb  reward   status   hypothesis
```

| Field | Description |
|-------|-------------|
| `step` | Experiment number (monotonic) |
| `commit` | Git short hash of the training code at time of run |
| `val_bpb` | Validation bits-per-byte (lower = better) |
| `core` | CORE benchmark score (higher = better) |
| `mfu%` | Model FLOP utilisation % |
| `vram_gb` | Peak VRAM usage in GB |
| `reward` | Composite R = α·quality − β·cost − γ·safety |
| `status` | `keep` / `discard` / `crash` |
| `hypothesis` | What was tested |

## How to Read This

**`reward` is the primary metric** — not `val_bpb`. A run with better BPB but
worse composite reward is discarded. The reward encodes the full tradeoff:
quality, efficiency, and safety in one scalar.

The leaderboard ranks kept experiments by composite reward. val_bpb is shown
for reference but is not the decision criterion.

## Live Leaderboard

> Populated automatically by `ExperimentTracker` during `ti run`.
> Run `ti status` for the live dashboard with family attribution and Pareto frontier.
> Run `ti analyze` for full insight extraction.

```
step  commit   val_bpb    core    mfu%   vram_gb   reward   status   hypothesis
----  -------  ---------  ------  -----  -------  --------  -------  ----------
(no experiments yet — run: ti run --hypothesis "baseline (no changes)")
```

## Example (after 7 experiments)

```
step  commit   val_bpb    core    mfu%   vram_gb   reward   status   hypothesis
----  -------  ---------  ------  -----  -------  --------  -------  ----------
7     f3a2c1d  1.018200   0.253   42.8   38.4     +0.4012   keep     embedding_lr 0.8→0.9
2     b4e1f9a  1.019800   0.251   42.1   38.2     +0.3944   keep     embedding_lr 0.6→0.8
1     a1b2c3d  1.023400   0.248   42.3   38.2     +0.3821   keep     baseline (no changes)
5     d7c4e2b  1.021100   0.250   41.9   38.5     +0.3790   keep     scalar_lr 0.04→0.06
```

Discarded (composite R did not improve despite BPB changes):
```
4     c9a3f7e  1.018700   0.249   38.1   71.4     +0.3612   discard  batch_size 512→1024
                                                                       [VRAM 71.4GB offset quality gain]
3     e5d2b8f  1.024500   0.245   40.8   39.1     +0.3701   discard  WINDOW_PATTERN SSSL→SSLL
6     g2h1i4j  0.000000   0.000    0.0    0.0     +0.0000   crash    double model width (OOM)
```

## Key Insights from Example Run

- **embedding_lr is the top promising family** (mean ΔR=+0.0231 across 2 experiments)
- **batch_size increase** improved BPB but was discarded due to VRAM cost (+32GB)
- **window_pattern changes** are a dead-end (ΔR=−0.0243 mean across tested variants)
- **No safety drift** detected — all kept experiments have safety_penalty=0.000
