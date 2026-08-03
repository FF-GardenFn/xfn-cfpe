# MSX Design — Pricing the Memory Spectrum of AI-Assisted Work

**Status:** v0.1 (2026-08-03). Design only; no data. The relaxation plant (§2) is a posited model that earns its
keep solely through §6. The optimization machinery here (event-based acceptance sets, LP/convex duality,
relaxation dynamics) is adapted from prior unpublished work by the author in an unrelated domain; it stands in
this document on its own definitions and needs nothing imported to be checked.

## 0. Thesis

Existing AI-exposure indices score tasks by surface-activity automatability — pricing by the mean, the projection
error. This index prices the memory spectrum of a (task, executor) pair: which knowledge modes carry the value,
what each costs to reconstruct at current token prices, which are tacit and gating, and what correction debt the
fast path stores.

**Calibration point #1 (publicly reported figures; see §5 on their standing):** the Bun Zig→Rust port — 11 days,
~$165k API spend, ~72B cached reads (the reconstruction bill), 11 expert-days (the tacit slot), a regression tail
(the correction debt), and a ~million-assertion test suite (externalized memory that made the task automatable at
all).

## 1. Layer 1 — the task ledger (model-free accounting)

Delivered task value decomposes into receipt-backed columns:

- **W** — mechanical generation: uncached output tokens.
- **M_ext** — reconstruction of externalized memory: cached/context reads, retrieval tokens.
- **M_tacit** — tacit supply: human hours in decomposition, review, and defining what "done" means.
- **M_pre** — pretrained content: free at inference; carries staleness `w` (a model calibrated to an old world),
  priced by the errors it induces rather than assumed away.
- **D_fict** — fictive ("as-if-done") correction debt: the post-acceptance fix stream on its own slow clock —
  regressions, CI churn, the cost of annealing the fast path's shortcuts.

Ledger identity:

```
reported project cost = W + M_ext + M_tacit − credit(M_pre) + D_fict(t)
```

with `D_fict` integrated over the debt clock, not truncated at "done." Truncating at acceptance is the accounting
error that makes fast paths look cheap: the debt does not disappear at the demo, it moves to a slower clock.

Layer 1 requires no model of anything. Every column has a receipt: token telemetry (cached vs uncached is the
key split — it prices `M_ext` directly and already exists in every agent run), timesheets, and the
post-acceptance issue stream.

## 2. Layer 2 — the plant (counterfactual engine)

A task is a set of requirement clusters `i` with sizes `s_i` and characteristic clocks. Residual debt `R_i(t)`
relaxes under spend:

```
Ṙ_i = −λ_i(k, u) · R_i,        λ_i = λ_i⁰ · (ε + (1−ε) k_i)
```

with exploration floor `ε` and knowledge levels `k_i ∈ [0,1]`. **Gates:** some clusters have `λ_i = 0` absent a
specific tacit bit — memory whose value is *feasibility*, not marginal cost. Knowledge dynamics:
`k̇_i = acquisition(tokens: read externalized; human-hours: interview/pairing) − staleness`. Acceptance is a set
of event conditions over `R` (tests, reviews, SLAs). `J*(x₀)` is the minimum cost to the acceptance set
(LP/convex where linearized).

The counterfactual mapping — the four questions the index exists to answer:

1. **Different person** → swap the k-vector, re-solve: `ΔJ*`.
2. **If they knew / forgot X** → `∂J*/∂k_i` — the shadow price of memory item `i` ("which future event prices
   your expertise"). Shadow prices are the worker-side output of the whole apparatus.
3. **How much did experience steer it** → human actions as actuator columns; path attribution against the
   no-human twin.
4. **Would the model have failed** → remove gated bits ⇒ an infeasibility certificate.

Index output is always (cost, feasibility) pairs — never a scalar without its ledger.

## 3. Measurement doctrine (objective ∧ interview ∧ surgery)

**Objective = identification.** Burndown curves are the domain's step responses (the calibration arc:
translation wave → mass compile errors → test-pass → regression tail is visibly multi-exponential). Order
selection on the burndown estimates the number of task clocks. Token telemetry (cached/uncached) prices `M_ext`
directly. The post-acceptance issue stream identifies the debt clock.

*Stated limit (see §5): sums of exponentials are a classically ill-conditioned inverse problem. Burndown fits
are hypothesis-generating; interventional identification (surgery, below) is the load-bearing form wherever
affordable, and order-selection claims carry confidence statements or they carry nothing.*

**Interview = pre-registered tacit inventory.** Before the run: "list what only you know; for each, what breaks
without it; rate its reconstructibility." After: compare predicted gates to the realized dual support. The
practitioner's self-model becomes a falsifiable prediction; disagreement calibrates both the human and the index.
Bias is expected and measured, not assumed away.

**Surgery (where affordable).** Same task, ablated: tests hidden (content erasure); no human-in-loop (efficacy
erasure); older model checkpoint (staleness); memory transplant across executors (playbooks). Small-task
benchmark versions are cheap; lab-scale runs are calibration gold. The paired-checkpoint ablation is also the
only clean identification of `credit(M_pre)` within a task — at task scale, pretrained credit and mechanical
generation are otherwise confounded.

## 4. Index components (per task T, executor profile P)

- **MRC — Memory Reconstruction Cost:** tokens to rebuild externalized content to the acceptance-relevant
  threshold.
- **TMP — Tacit Memory Premium:** `J*(without P's tacit bits) − J*(with)`, reported as (Δcost, Δfeasibility);
  gating ⇒ categorical, not numeric.
- **SX — Staleness exposure:** `∂J*/∂w` of pretrained content; repriced per model release.
- **E — Externalization ratio:** machine-readable memory value / total. **Headline law (falsifiable):** task
  exposure rises with `E`, and writing your memory down raises `E` while lowering your own `TMP` — the
  practitioner's blind trade, priced.
- **L — AI leverage:** `J_human-only / J_hybrid` at equal acceptance, always shipped with its decomposition
  (capacity / reconstruction / tacit / debt). Publish the spectrum; permit the scalar.

## 5. Stated limits (not smoothed)

1. **No conservation.** Knowledge copies at ~zero marginal cost; erasure has no physical bill; transplant is
   nearly free once externalized. The pricing/duality machinery survives (it needs no conservation law); any
   intuition imported from conserved-quantity domains does not transfer. This is non-rival-goods economics.
2. **Posited dynamics.** The relaxation plant is a hypothesis; identification-first is mandatory, and §6 is the
   only court that counts.
3. **Ill-conditioned identification.** Multi-exponential decomposition of noisy burndowns frequently cannot
   distinguish two clocks from three at realistic n. Two very different plants can fit one curve. Interventional
   evidence outranks curve fits everywhere the two disagree.
4. **Independent clusters misprice teams.** `λ_i(k_i)` carries no knowledge complementarities — tacit bits whose
   value exists only jointly (the expert whose insight is worthless without the reviewer who can consume it).
   v0.1 flags this as a regime limit; interaction terms are the first v0.2 item.
5. **In-task learning.** `k̇` from doing is the strongest nonlinearity; v0.1 freezes it for short tasks and
   flags the regime limit.
6. **Survivor-biased receipts — including the anchor.** Public postmortems are successes, and the calibration
   point's own figures are publicly reported numbers, not audited receipts; the index treats its anchor with the
   same suspicion it applies everywhere else. The failure column exists inside AI labs (telemetry + outcomes at
   panel scale) — the natural research-collaboration surface for this program.

## 6. Pre-registered falsification (live, recurring)

**P-LEDGER:** before reading any newly published agent-project postmortem, predict its cost split
(`W : M_ext : M_tacit : D_fict`, ± bands) from repo observables alone (LOC, test coverage / assertion density as
E-proxy, issue history, dependency churn). Score against the receipt. Postmortems publish roughly monthly; the
test never closes. Failures are diagnosed before any refit.

**P-GATE:** interview-predicted gates vs realized dual support: report the confusion matrix. The index is
working when practitioners are surprised in both directions at nonzero rates.

Protocol, prediction format, and registry: [p_ledger_protocol.md](./p_ledger_protocol.md), [predictions/](./predictions/).

## 7. Products this implies (noted, not committed)

Pre-flight feasibility certificates for agent projects (the infeasibility check *before* the six-figure spend);
quote engines from `(E, tacit inventory)` → predicted `J*` ± band; token repricing by role (reconstruction reads
vs exploration burn); practitioner-side dual reports ("which future event still prices your expertise" — the
societal-impact face of the index). The main deliverable remains §6: getting it right in public.

## 8. Positioning

Activity-based exposure indices (occupation- and task-level automatability scoring in the economic-index
literature) answer "what fraction of this job's activities can a model do?" This index answers a different
question: "what does this *task* actually cost, through which memory modes, for *this* executor, and what breaks
without them?" The two are complements: theirs scales across an economy, this one prices the unit their mean
abstracts over. The nearest in-repo relative is the cost-equation note
([evaluation/benchmarks/equ.md](../../evaluation/benchmarks/equ.md)), which is Layer 1 before the memory
decomposition; the epistemic machinery — preregistration, receipts, corrections as mechanical rules — is the
program documented in [CAI/framework.md](../../CAI/framework.md).
