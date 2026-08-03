# Memory-Spectrum Index (MSX)

**Status:** v0.1 design (2026-08-03). No data collected; the plant is a hypothesis; the falsification program
([p_ledger_protocol.md](./p_ledger_protocol.md)) is open and never closes. Full treatment: [design.md](./design.md).

## Thesis

Existing AI-exposure indices score tasks by surface-activity automatability — pricing by the *mean*, which is a
projection error when task value concentrates in memory modes the mean cannot see. This index prices the **memory
spectrum of a (task, executor) pair**: which knowledge modes carry the value, what each costs to reconstruct at
current token prices, which are tacit and *gating*, and how much correction debt the fast path stores.

The output discipline is fixed from the start: **(cost, feasibility) pairs — never a scalar without its ledger.**
Gated tacit knowledge makes exposure categorical, not numeric; an index that smooths over that discontinuity has
already mispriced the thing it exists to price.

## The task ledger (Layer 1 — model-free accounting)

| Column | Meaning | Receipt |
|---|---|---|
| `W` | Mechanical generation | uncached output tokens |
| `M_ext` | Reconstruction of externalized memory | cached/context reads, retrieval tokens |
| `M_tacit` | Tacit supply | human hours in decomposition, review, "what done means" |
| `M_pre` | Pretrained content (free at inference) | credited, with staleness `w` priced by the errors it induces |
| `D_fict` | Correction debt | post-acceptance fix stream on its own slow clock |

Ledger identity: `reported cost = W + M_ext + M_tacit − credit(M_pre) + D_fict(t)`, with `D_fict` integrated over
the debt clock — never truncated at "done."

## Index components (per task T, executor profile P)

| Component | Reads as | Form |
|---|---|---|
| **MRC** | Memory Reconstruction Cost | tokens to rebuild externalized content to acceptance threshold |
| **TMP** | Tacit Memory Premium | `J*(without P's tacit bits) − J*(with)` as (Δcost, Δfeasibility); gates ⇒ categorical |
| **SX** | Staleness exposure | `∂J*/∂w` of pretrained content; repriced per model release |
| **E** | Externalization ratio | machine-readable memory value / total |
| **L** | AI leverage | `J_human-only / J_hybrid` at equal acceptance, always with its decomposition |

**The headline law (falsifiable):** task exposure rises with `E`, and writing your memory down raises `E` while
lowering your own `TMP` — *the practitioner's blind trade, priced.*

## What exists vs. what is future work

Exists: this design, its stated limits ([design.md §5](./design.md)), and the pre-registered recurring
falsification protocol with its prediction registry ([predictions/](./predictions/)). Future work: the first
P-LEDGER round (opens with the next published agent-project postmortem), the small-task surgery benchmark, and
any implementation of the Layer-2 counterfactual engine.

## Where it sits in this repo

The primitive ancestor is the cost-equation note in [evaluation/benchmarks/equ.md](../../evaluation/benchmarks/equ.md)
(Layer 1 without the memory decomposition). The measurement doctrine — receipts over recollections, corrections as
pre-stated mechanical rules, denominators before headlines — is the same one documented across
[CAI/](../../CAI/README.md). The societal-impact face is the worker-side dual report: *which future event still
prices your expertise.*
