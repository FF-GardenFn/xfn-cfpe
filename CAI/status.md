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
- **2026-07-30** — **metric-semantics defect split at the source.** `residual_violation` was set in two branches with two incompatible meanings and so conflated *executed harm* with *the gate blocking a call, followed by an unclean recovery turn*. Now split into `executed_violation` / `blocked_violation` / `recovery_failure`; `residual_violation` is retained unchanged and means exactly `executed_violation OR recovery_failure` — an **upper bound** on harm that got through. H1's falsifier and the tool-channel claim key on `executed_violation` alone. See [POSTMORTEM.md §"Metric semantics"](./POSTMORTEM.md#metric-semantics-residual_violation-conflated-two-outcomes), which records **two divergences left deliberately unresolved**:
  - **(a)** 8 v4 rows are `residual AND blocked` (Opus/`kernel_only` 5, Opus/`cai_kernel` 2, Sonnet/`cai_kernel` 1). Post-`f1bb6a4` they carry tool kinds, so the old conflated metric would read `residual_tool = 8`. In all 8 the gate blocked the call and **nothing executed** — the "0 executed tool-channel violations" claim stands; an 8 there is an artifact, not a falsification.
  - **(b)** Re-running the rescore under the narrowed intent-fix rule would move **Opus/`cai_kernel` only**: residual 2.6% → 3.7%, attempted 5.3% → 6.3%. This is a *recovery-failure* difference, not new executed harm. The stored file is unchanged and **the choice to re-run-and-republish or pin-and-cite is open, for the repo owner**.

## Demonstrated (post-correction)

| Claim                                              | Evidence                                                                  | Strength |
|----------------------------------------------------|---------------------------------------------------------------------------|----------|
| Tool-channel sealable via external gate            | **0 / 760** tool-based **executed** violations under any kernel condition, both models | Strong |
| Dual-surface minimizes residual                    | Opus 13.7% → 2.6%; Sonnet 4.2% → 2.1% (cai_kernel) — on the `residual` upper bound, see note (b) below | Moderate |
| Recovery loop functional                           | Block→recover: Opus 67–71%, Sonnet 75–100%                                | Moderate |
| No utility tax on benign tasks                     | 100% benign success across all conditions                                 | Strong |
| Predicted text-channel blind spot is real          | 100% of **executed** violations under any kernel condition are text-only (the remainder of `residual` is blocked-then-unrecovered, not leaked harm) | Strong (negative result) |
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
- `CAI/POSTMORTEM.md` — incident reports: the mention-vs-use eval false positives, and the `residual_violation` metric-semantics split (incl. two open divergences)
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

### K-disclosure experiment (extends v4 along a disclosure axis)

Pilot ran 2026-07-30 (Sonnet, `kernel_only`, K0 vs K3, 32 adversarial tasks, n=3 → 192 trials). Verdicts after the 2026-07-30 review correction:

| Hypothesis | Verdict |
|---|---|
| H1 kernel invariance | **not falsified — but barely tested.** A violating tool call reached the gate on **1 of 192 trials**, and was blocked. 13/192 trials emitted any tool call at all. The zero-execution figure is a zero over a denominator of ~1, not over 192 — under an ~87.5% refusal rate it cannot separate "the gate works" from "the gate was never tested." |
| H2 attempt elicitation | **not supported → REVISE.** K3 − K0 = +3.1pp (Fisher p=0.246), inside the pre-registered +5pp margin. Revise K3 wording before scaling. |
| H3 displacement | Directionally consistent (text residuals 0 → 2), far too small to claim, and the mechanism is not identified by this data. |

H1 and H2 are one result: the elicitation was too weak, and *because* it was too weak, the constraint was never seriously exercised. Next experiment is to red-team the validator's forbidden-pattern coverage directly — pattern evasion, not model reluctance, is the real threat to H1.

- `CAI/k_disclosure_spec.md` — pre-registered spec (v1.0, 2026-07-29) + changelog (incl. the 2026-07-30 correction entries)
- `CAI/k_pilot_results.md` — pilot results writeup (2026-07-30, corrected)
- `CAI/run_k_pilot.py` — pilot runner (CLI transport, resumable)
- `CAI/analysis/k_pilot_analysis.py` — pre-registered contrasts (H1/H2/H3), gate-exercise decomposition, v4 anchor comparison
- `CAI/test_k_disclosure.py` — no-network harness validation (7 tests), incl. K0 byte-identity regression, the tool-channel masking regression, and the blocked-is-not-executed regression guarding H1's falsifier
- `CAI/results/k_pilot_trials.jsonl` — 192 pilot trials (raw)
- `CAI/results/k_pilot_summary.json` — machine-readable pilot summary, incl. `gate_exercise`
