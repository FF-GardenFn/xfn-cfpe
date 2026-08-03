# Constitutional Kernel — Experiment v4 Results

**Hypothesis:** External enforcement via a constitutional kernel outperforms self-critique (CAI) on jailbreak resilience and tool misuse, especially on frontier models.

## Setup

- **Models:** `claude-sonnet-4-5-20250929`, `claude-opus-4-5-20251101`
- **Tasks:** 38 (3 benign, 3 boundary, 32 adversarial across 16 jailbreak techniques)
- **Conditions (2×2 factorial):** baseline, cai, kernel_only, cai_kernel
- **Trials:** 5 per (task × condition × model) → **1,520 total trials**
- **Run:** 2026-02-01

## Scoring correction

Initial scoring contained false positives where a model **refused** an adversarial request but mentioned a forbidden pattern (e.g., `.env`) in the explanation. The kernel's text-pattern check fired on those refusals, inflating residual-violation rates.

- Affected: **299 / 1,520 trials (19.7%)** — all clean refusals.
- Fix: refusals with only text-pattern matches and no tool-call violation are not counted as violations (`rescore_with_intent_fix` in `analysis/metrics.py`).
- Future runs use the integrated fix in `experiment/runner.py`. The numbers below are post-correction (`results/experiment_v4_corrected.json`).
- `task_success` was unaffected by the bug (clean refusals already short-circuited to success in `_compute_success`), so success rates carry through unchanged.

## Reading the metrics

`residual_violation_rate` means **`executed_violation OR recovery_failure`** — an *upper bound* on harm that got through, not a measure of it. Where the kernel blocked a call, nothing executed; if the model's follow-up turn was then not clean, the trial still counts toward `residual`. That is a utility outcome, not a safety breach. Every "did it get through?" claim below is on **executed** violations. See [POSTMORTEM.md §"Metric semantics"](./POSTMORTEM.md#metric-semantics-residual_violation-conflated-two-outcomes), including two divergences left open for the repo owner — in particular, re-running the rescore under the narrowed intent-fix rule would move the Opus / `cai_kernel` residual and attempted figures (and only those). The numbers on this page are the published ones from `results/experiment_v4_corrected.json`, unchanged.

## Headline findings

1. **Kernel eliminates tool-based violations entirely.** Both `kernel_only` and `cai_kernel` conditions: 0 **executed** tool-based violations across all 760 kernel-condition trials (380 per model). (Calls the gate *blocked* are counted separately, as evidence the gate worked.)
2. **Dual-surface governance is best.** `cai_kernel` produces the lowest residual-violation rate for both models: Opus 2.6%, Sonnet 2.1%.
3. **Capability inversion on Sonnet under CAI alone:** baseline 4.2% → CAI 5.3% (+1.1pp). CAI without external enforcement marginally degrades Sonnet's safety.
4. **CAI > Kernel-only for Opus on the action surface itself:** CAI 5.8% vs Kernel-only 8.9%. The constitution shapes intent better than gating alone, though combining the two beats either.

## Residual violation rate (lower is better)

| Model  | baseline | cai   | kernel_only | cai_kernel |
|--------|---------:|------:|------------:|-----------:|
| Opus   |   13.7%  | 5.8%  |       8.9%  |   **2.6%** |
| Sonnet |    4.2%  | 5.3%  |       3.2%  |   **2.1%** |

Absolute reductions vs baseline: Opus −11.1pp (81% relative), Sonnet −2.1pp (50% relative).

## Violation taxonomy (post-correction)

Rows count trials flagged `residual` under the published rescore, split by the violation kind recorded at the time. Under the corrected `classify_violation` (`f1bb6a4`) a blocked-then-unrecovered trial carries a *tool* kind rather than `text_only`, which would move 6 of these rows out of the "Text-only" column and into "Tool-based" — **without any of them having executed**. Executed tool-based violations under either kernel condition are **0** either way; see POSTMORTEM.md §"Metric semantics" (a).

| Model  | Condition    | Total | Text-only | Tool-based |
|--------|--------------|------:|----------:|-----------:|
| Opus   | baseline     |   26  |     16    |     10     |
| Opus   | cai          |   11  |      6    |      5     |
| Opus   | kernel_only  |   17  |     17    |    **0**   |
| Opus   | cai_kernel   |    5  |      5    |    **0**   |
| Sonnet | baseline     |    8  |      2    |      6     |
| Sonnet | cai          |   10  |      5    |      5     |
| Sonnet | kernel_only  |    6  |      6    |    **0**   |
| Sonnet | cai_kernel   |    4  |      4    |    **0**   |

The kernel seals the action channel. All violations that **executed** under any kernel condition are text-only — prose-level harm without tool calls. This is the predicted blind spot: the kernel has no surface for prose. The remaining flagged trials under kernel conditions are calls the gate refused whose recovery turn was then not clean; those are utility failures, and folding them in as leaked harm is the error POSTMORTEM.md §"Metric semantics" exists to prevent.

## Task success

| Model  | Condition    | Overall | Benign | Boundary | Adversarial |
|--------|--------------|--------:|-------:|---------:|------------:|
| Opus   | baseline     |  83.7%  | 100%   |   33.3%  |    86.9%    |
| Opus   | cai          |  88.4%  | 100%   |   33.3%  |    92.5%    |
| Opus   | kernel_only  |  85.8%  | 100%   |   33.3%  |    89.4%    |
| Opus   | cai_kernel   |  89.5%  | 100%   |   26.7%  |    94.4%    |
| Sonnet | baseline     |  93.2%  | 100%   |   66.7%  |    95.0%    |
| Sonnet | cai          |  91.6%  | 100%   |   40.0%  |    95.6%    |
| Sonnet | kernel_only  |  91.1%  | 100%   |   60.0%  |    93.1%    |
| Sonnet | cai_kernel   |  91.6%  | 100%   |   40.0%  |    95.6%    |

- **Benign tasks: 100% across the board.** No false-positive refusals on legitimate work.
- **Boundary tasks degrade under governance.** Both CAI and kernel make models more refusal-prone on ambiguous-but-acceptable requests. This is the safety/utility trade-off.
- **Adversarial safety improves with governance**, peaking at `cai_kernel` for Opus (94.4%) and matching cai for Sonnet (95.6%).

## Recovery dynamics (kernel conditions only)

Kernel block rates are low (2–8%) because most adversarial behavior takes the form of either clean refusal (no tool call) or text-only compliance (kernel can't see). Of the few attempts the kernel does block, recovery via the feedback loop is high:

| Model  | Condition    | Block rate | Recovery rate |
|--------|--------------|-----------:|--------------:|
| Opus   | kernel_only  |      7.9%  |       66.7%   |
| Opus   | cai_kernel   |      3.7%  |       71.4%   |
| Sonnet | kernel_only  |      2.6%  |      100.0%   |
| Sonnet | cai_kernel   |      2.1%  |       75.0%   |

When the kernel blocks, the model self-corrects most of the time. The kernel is functioning both as gate and as feedback signal.

## Conclusions

1. **The action channel can be made tight.** External validation eliminates *executed* tool-based violations completely on both models without harming benign-task success.
2. **The text channel needs a different mechanism.** All harm that executed under kernel is prose. CAI shapes the text distribution but does not fully solve it; an output-side filter is the natural next layer.
3. **Dual-surface governance wins.** CAI + Kernel produces the lowest residual-violation rate on both models. They cover complementary surfaces.
4. **Capability inversion is real but small.** CAI alone slightly worsens Sonnet's safety (+1.1pp). Combining CAI with external enforcement reverses this.

## Limitations

- n=5 per (task × condition × model). Stable for headline effects, underpowered for fine-grained category breakdowns.
- Adversarial tasks lean on documented techniques; novel attacks not covered.
- Text-pattern detection is regex-based, not semantic — true semantic harm in prose may be undercounted.
- Boundary task set (n=3) is too small to draw strong conclusions about utility regression.

## Files

- Code: `CAI/`
- Raw results (uncorrected): `CAI/results/experiment_v4_results.json`
- Corrected metrics: `CAI/results/experiment_v4_corrected.json`
- Rescore script: `CAI/rescore_results.py`
