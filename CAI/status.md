# CAI — Status

## Hypothesis

External enforcement via a **constitutional kernel** beats self-critique (CAI) on jailbreak resilience and tool misuse, especially on frontier models.

- "Constitution-as-code" (kernel gating actions externally) > "constitution-as-text" (model self-enforcing).
- Frontier models need **dual-surface governance**: CAI shapes text generation; kernel gates tool execution. Together they cover both failure surfaces.

## Experiments

| Iter   | Date       | Conditions                                       | n / cell | Trials | Status        |
|--------|-----------:|--------------------------------------------------|---------:|-------:|---------------|
| v1–v2  | 2026-01-31 | baseline, CAI, kernel (3-cond)                   |    1–3   |    —   | archived      |
| v3     | 2026-01-31 | baseline, CAI, kernel (3-cond)                   |     3    |    —   | superseded    |
| v3.2   | 2026-01-31 | baseline, CAI, kernel (=CAI+gate, dual-surface)  |     3    |    —   | superseded    |
| **v4** | 2026-02-01 | baseline, cai, kernel_only, cai_kernel (2×2)     |   **5**  | **1,520** | corrected     |

**v4 setup:** Sonnet 4.5 + Opus 4.5; 38 tasks (3 benign / 3 boundary / 32 adversarial × 16 jailbreak techniques); intent classifier on Haiku.

## Engineering log

- **2026-02-01** — v4 run, raw JSON saved (`experiment_v4_results.json`).
- **Between 2026-02-01 and 2026-02-18** — false-positive bug identified: refusals mentioning forbidden patterns (e.g., `.env` in an explanation) were flagged as text violations. Two fixes:
  - Integrated intent-aware logic into `experiment/runner.py` for future runs.
  - Added post-hoc `rescore_with_intent_fix()` in `analysis/metrics.py` + CLI `rescore_results.py`.
- **2026-02-18** — code committed (`4330aef "track CAI"`).
- **2026-04-27** — rescore executed → `experiment_v4_corrected.json`. Bug affected **299 / 1,520 trials (19.7%)**. `task_success` was unaffected (clean refusals already short-circuit to success in `_compute_success`); only violation rates needed correction.
- **2026-04-27** — `results.md` written (post-correction summary).

## Demonstrated (post-correction)

| Claim                                              | Evidence                                                                  | Strength |
|----------------------------------------------------|---------------------------------------------------------------------------|----------|
| Tool-channel sealable via external gate            | **0 / 760** tool-based residual violations under any kernel condition, both models | Strong |
| Dual-surface minimizes residual                    | Opus 13.7% → 2.6%; Sonnet 4.2% → 2.1% (cai_kernel)                        | Moderate |
| Recovery loop functional                           | Block→recover: Opus 67–71%, Sonnet 75–100%                                | Moderate |
| No utility tax on benign tasks                     | 100% benign success across all conditions                                 | Strong |
| Predicted text-channel blind spot is real          | 100% of residual under any kernel condition is text-only                  | Strong (negative result) |
| Capability inversion on Sonnet under CAI alone     | baseline 4.2% → cai 5.3% (+1.1pp); reverses under cai_kernel              | Weak (n underpowered) |
| Monotone dose–response on Opus                     | 13.7% → 5.8% / 8.9% → 2.6% across baseline / cai / kernel_only / cai_kernel | Moderate |

## Open / not yet demonstrated

- **Text-channel sealing.** Blind spot identified; closure not shown. No output-side classifier tested.
- **Capability inversion as a phenomenon.** +1.1pp on n=190 is within noise. Needs ≥3 models.
- **Statistical robustness.** No bootstrapped CIs. n=5 per cell underpowers sub-category claims.
- **External validity.** Only internal task suite. No HarmBench / AdvBench comparison.
- **Gate-effect isolation.** Block rates 2–8%; can't fully disentangle direct gate effect from system-prompt effect at this n.
- **Boundary task utility cost.** Suggested (Sonnet 66.7% → 40% under CAI), but n=3 boundary tasks too small to claim.
- **Semantic vs regex.** Text-pattern detection is regex; true semantic harm in prose probably undercounted.

## Next steps (ordered by leverage)

1. **Bigger n.** Re-run v4 grid at n=20 per cell (~6,080 trials). Cheap; converts headline claims from "directionally true" to "defensible." Add bootstrapped 95% CIs.
2. **Add Haiku as 3rd model.** Co-runs with #1. Capability-inversion claim needs ≥3 data points to graduate from anecdote.
3. **Output-side text classifier.** Build complementary text gate. Re-run as 5-condition grid: baseline / cai / kernel_only / cai_kernel / cai_kernel+text_gate. This is the missing arm of the dual-surface argument.
4. **External benchmark.** Subset run against HarmBench or AdvBench for comparability with published methods.
5. **Stronger boundary set.** Expand from n=3 to n=15+ tasks. Required to claim utility cost / no-utility-tax credibly.
6. **Semantic text scoring.** Replace regex patterns with a small classifier (Haiku-based or fine-tuned). Will likely surface text violations the regex misses.

## Files

- `CAI/README.md` — package overview
- `CAI/results.md` — post-correction results writeup (2026-04-27)
- `CAI/status.md` — this doc
- `CAI/results/experiment_v4_results.json` — raw v4 (uncorrected violation rates)
- `CAI/results/experiment_v4_corrected.json` — rescored (2026-04-27)
- `CAI/run_experiment.py` — CLI
- `CAI/experiment/runner.py` — orchestrator (intent-aware fix integrated)
- `CAI/kernel/validator.py` — constitutional kernel
- `CAI/classifier/intent.py` — Haiku-based intent classifier
- `CAI/analysis/metrics.py` — `analyze_results`, `rescore_with_intent_fix`
- `CAI/rescore_results.py` — post-hoc patch CLI
