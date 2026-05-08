# Validation and Integration — Post-Flight Composite

## What

The **post-flight gate** that integrates per-technique validation outputs into a portfolio score, applies a single composite rubric (merging the older `prompt-model/validation-rubric.md` with this layer's mechanistic checks), enforces an explicit scoring procedure (single rater / LLM judge / inter-rater), and produces a go / no-go decision for production deployment.

Unlike every other file in this directory, this is not itself a prompt technique — it is the **orchestrator** that decides whether the prompt is ready. It runs *after* every per-technique procedure has been applied; it operates on the prompt, the per-technique structural checks, the probe outputs, and the empirical sanity-check runs.

## Mechanism

Three forces make a composite gate worthwhile.

**Per-technique validation is necessary but not sufficient.** Each technique file has its own structural checklist and probe; passing them individually does not guarantee the assembled prompt works. Anchors, lens, ordering, formatting, negative-space, and references can each be valid in isolation and **interact destructively** when assembled — e.g. a load-bearing anchor placed in a band the position rule discounts, a lens whose decision tree contradicts the negative-space subtractions, a source pack that conflicts with the lexicon glossary. The composite catches interaction failures the per-file checks cannot see.

**Goodhart applies.** A rubric scored only by the prompt author will be optimised against, not validated by. A rubric scored by an LLM judge alone will reward whatever the judge attends to — usually surface structure rather than substance. A composite procedure (structural self-check + LLM judge + a single human spot-check on contested items) is robust where any single mechanism is exploitable.

**Production deployment is a step change in cost.** A prompt that fails in dev costs a re-run; a prompt that fails in production costs reputation, money, or worse. The gate exists to make the dev/prod boundary explicit. If the composite score does not pass, the prompt is not production-ready — period.

This file is methodology, not modelling. The "mechanism" is rubric design and rater calibration, not transformer internals.

## Trigger conditions

Apply the post-flight composite when **any** are true:

- The prompt is moving from **draft to production deployment** (going behind a public API, into a customer-facing skill, into a billed agent).
- The prompt is **part of a versioned skill or plugin** where regressions matter.
- The prompt has **stakes** — output drives a billed action, a regulated decision, customer communication, code that ships.
- The prompt was **revised after observed failure** — composite ensures the revision didn't fix one thing while breaking another.
- The prompt is being **handed off** between authors — composite is the contract that the next person inherits a known-good baseline.

Apply with **higher rigour** (full LLM-judge pass + human spot-check on contested items) when additionally:

- The prompt is part of a **regulated workflow** (medical / legal / financial / safety-critical).
- The prompt is **invoked at scale** (many runs per day; even small failure rates compound).

## Anti-trigger conditions

Do **not** apply the full gate when **any** are true:

- **Throwaway / one-off prompt** in a chat session. Rubric overhead exceeds prompt lifetime.
- **Exploratory drafting** — the prompt is still being shaped; running the gate now is premature optimisation.
- **Personal-use prompts** with no audit obligation. Self-review suffices.
- **Pure-execution prompts** with deterministic success criteria already enforced (a prompt that wraps a single API call doesn't need a 50-point rubric).

If anti-triggers fire, fall back to the **lightweight gate**: structural self-check from each technique file's `## Validation` section, no LLM judge, no human review.

## Procedure

### 1. Confirm per-technique structural checks have all passed

Each technique file has a `## Validation` section with structural self-checks. Before running the composite, confirm every applicable file's checks are green.

```xml
<per_technique_gate>
  <file name="tokenizer-aware-lexicon.md" applies="yes" passed="yes"/>
  <file name="persona-clusters.md" applies="yes" passed="yes"/>
  <file name="ordering-and-position.md" applies="yes" passed="yes"/>
  <file name="formatting-as-signal.md" applies="yes" passed="yes"/>
  <file name="negative-space.md" applies="yes" passed="yes"/>
  <file name="references-and-evals.md" applies="yes" passed="yes"/>
  <file name="model-recon.md" applies="yes" passed="yes"/>
</per_technique_gate>
```

A file marked `applies="no"` (e.g. `persona-clusters.md` for a pure-execution task) requires a one-line justification of *why* the technique doesn't fire — this catches accidental skips.

If any `applies="yes"` file is `passed="no"`, **stop**. Fix the per-technique failure first; the composite cannot rescue an unfinished technique.

### 2. Run the composite mechanistic rubric

Target: 100/100.

| Dimension | Score 0 (fail) | Score 5 (partial) | Score 10 (pass) |
|---|---|---|---|
| **Tokenizer Awareness** | No model/tokenizer awareness; load-bearing terms not probed | Some token budgeting; rough tokenizer estimate | Tokenizer/proxy chosen via `model-recon.md`; load-bearing terms probed; high-friction anchors defined or replaced |
| **Domain Anchors** | Generic vocabulary; no canonical bundle | Some field terms used inconsistently | 8–15 canonical anchors per `tokenizer-aware-lexicon.md`; glossary locks meaning; polysemy disambiguated; same exact strings reused in task and output contract |
| **Position Control** | Prompt order accidental; lost-in-middle bugs visible | Some head/tail awareness; option order arbitrary | Head/middle/tail per `ordering-and-position.md`; load-bearing constraint head-tail duplicated; option order neutralised; lens precedes task; V1–V5 invariance test passed |
| **Formatting Discipline** | Mixed conventions; orphan tags; inconsistent block names | One convention chosen but applied unevenly | Single primary convention per target family from `model-recon.md`; canonical block names; ALL-CAPS reserved for ≤2 hard imperatives; exact-string repetition for anchors |
| **Negative-Space Discipline** | No anti-patterns OR vague bans ("don't be biased") | Some bans, generic | 3–7 specific bans per `negative-space.md`; named attractor + paired alternative; placed after task; prompter prose stripped of hedges |
| **Lens Operationalization** | Generic role label OR "You are..." instructional framing OR no lens (when one would help) | Named lens but not operationalised; OR operationalised but wrapped in "You are..." | Lens construction → decision tree → apply per `persona-clusters.md`; **structural framing only (no "You are..." / "Your role is...")** per §7b; non-overlapping corpora if stacked; convergence rule if looped; identity-safety guardrail present |
| **Evidence Scaffolding** | Unsupported claims; no source pack | Some references | Source pack with IDs and `use_for` per `references-and-evals.md` Track A; evidence contract enforced; locality preserved |
| **Preregistered Eval** | No success criteria stated | Tests mentioned but not enforced | Acceptance tests / falsifiers preregistered per Track B; `guards_against` per test; "do NOT report success without showing output" rule when applicable |
| **Recon Coverage** | Target model unknown; conservative defaults applied unconsciously | Target identified but consequences not all applied | Full `model-recon.md` cross-tab applied; orphan recon fields removed; per-target adaptation evaluated against baseline |
| **Interaction Audit** | Techniques applied in isolation; no cross-check | Interactions noticed but not enforced | Each file's `## Interactions` table walked; ordering rules from interacting files honoured; no destructive combos |

10 dimensions × 10 = 100. Pass threshold: **≥90/100** for production; ≥70/100 for internal tooling; below 70 → revise.

### 3. Scoring procedure (the meta-review's missing piece)

A rubric is only as honest as its scoring procedure. Pick the procedure to match stakes; document the choice.

| Stakes | Scoring procedure |
|---|---|
| Internal / personal | **Single rater** (the prompt author). Risk: motivated reasoning. Mitigation: revisit the rubric the next day before shipping. |
| Internal team-shared | **Two raters** (author + one teammate), score independently, reconcile any cell with a >3-point gap via discussion. |
| Customer-facing / production | **LLM judge + author review**. Run the rubric as a structured prompt against an independent LLM (different family from the target if possible). Author reviews any cell where judge and self-score differ by >3 points. |
| Regulated / safety-critical | **LLM judge + two human raters + spot-check on disagreements**. Inter-rater agreement (Cohen's kappa or simple % agreement) must exceed 0.8 across the ten dimensions, or the rubric itself needs sharpening. |

The LLM-judge prompt:

```xml
<judge_task>
Score the attached prompt against the 10-dimension mechanistic rubric below.
For each dimension, assign 0 / 5 / 10 and quote the specific evidence in the
prompt that justifies the score.
Do NOT score on overall vibe; score each dimension independently against
its written criteria.
</judge_task>

<rubric>
[10-dimension table from §2 above, embedded verbatim]
</rubric>

<evaluated_prompt>
[the prompt under review]
</evaluated_prompt>

<output_contract>
For each of the 10 dimensions, return:
- Score (0/5/10)
- Evidence quote (exact substring from the prompt that justifies)
- Brief rationale (1 sentence)
End with the total /100 and a one-paragraph go / no-go recommendation.
</output_contract>
```

The judge rubric is the same one the author scored against. This is intentional — generator-judge alignment from `references-and-evals.md` §B.4.

### 4. Composite-rubric merge with `prompt-model/validation-rubric.md`

The older file at `prompt-model/validation-rubric.md` (60-point structural rubric) and this file's 100-point mechanistic rubric are **additive**, not parallel.

| Rubric | Scope | Maximum |
|---|---|---|
| Structural (existing `validation-rubric.md`) | Cognitive structure, file dependencies, gates, progressive disclosure | 60 |
| Mechanistic (this file, §2 above) | Tokenizer / anchors / position / formatting / negative-space / lens / evidence / preregistration / recon / interactions | 100 |
| **Composite** | All of the above | **160** |

Composite pass thresholds:

| Use | Composite minimum |
|---|---|
| Internal exploration | ≥110 / 160 |
| Internal tooling | ≥125 / 160 |
| Customer-facing production | ≥140 / 160 |
| Regulated / safety-critical | ≥150 / 160, with inter-rater κ > 0.8 |

A prompt that scores 58/60 structural + 85/100 mechanistic = 143/160 is shippable for customer-facing. A prompt that scores 60/60 structural + 70/100 mechanistic = 130/160 is shippable for internal tooling but **not** for customer-facing — the structural perfection didn't compensate for the mechanistic gap.

The two rubrics measure different failure modes. Treating them as one number that you negotiate within is the bug; treating them as two independent gates that both must pass is the fix.

### 5. Production gate — the final go / no-go

Production-ready requires **all** of:

- [ ] Per-technique structural checks all passed (per file `## Validation`).
- [ ] Composite rubric ≥ threshold for the use class.
- [ ] At least one **order-invariance** eval run (`probes/position_pulse.py` + V1–V5 from `ordering-and-position.md`).
- [ ] At least one **source-ablation** eval run (with vs. without source pack — confirm sources actually constrain).
- [ ] For coding: preregistered tests exist and pass/fail is reported verbatim.
- [ ] For lens-using prompts: public evidence + uncertainty boundaries included; `documented` / `inferred` / `speculative` labels honoured.
- [ ] For long context: critical facts at head/tail; not buried only in the middle.
- [ ] For target model: `model-recon.md` cross-tab applied; orphan recon fields explained or removed.
- [ ] **Brittleness roundtrip** (planned `probes/brittleness.py`): prompt survives reorder / truncate / paraphrase variants without behaviour change.

Failing any of these → not production-ready. Fix and re-gate.

### 6. Prompt variant strategies (regression catalogue)

When revising, run these variants to detect regressions:

| Strategy | Variant | What it catches |
|---|---|---|
| Token probe swap | Replace rare wording with canonical field terms | Tokenizer-friction regressions |
| Position shift | Move critical evidence head / middle / tail | Lost-in-middle regressions |
| Lens swap | Generic role vs named lens vs invented persona | Operationalization regressions |
| Source ablation | With and without source pack | Source-binding regressions |
| Test ablation | With and without preregistered tests | Preregistration enforcement regressions |
| Order randomisation | Rotate candidate order | Option-bias regressions |
| Channel relocation | Move constraint between system / user / body | Channel-priority regressions |
| Tokenizer swap | Rerun against secondary target tokenizer | Cross-model portability regressions |

Run a variant matrix (5+ variants × current vs prior prompt) before merging revisions. A revision that helps the canonical case but regresses on a variant is not a clean win.

### 7. Mechanistic test cases (canonical fixtures)

```jsonl
{"id":"mech_001","query":"Evaluate these options in randomised order","expected":"order_invariant","strategy":"option_order"}
{"id":"mech_002","query":"Use named lens then critic lens","expected":"non_generic_tension","strategy":"lens_stack"}
{"id":"mech_003","query":"Implement feature with preregistered tests","expected":"test_first_behavior","strategy":"preregistered_tests"}
{"id":"mech_004","query":"Long-context prompt with key fact at 50%","expected":"fact_recovered_with_index","strategy":"position_recovery"}
{"id":"mech_005","query":"Anchor reuse across task and output contract","expected":"exact_string_binding","strategy":"anchor_locality"}
{"id":"mech_006","query":"Negative-space subtraction with paired alternative","expected":"banned_pattern_absent","strategy":"negative_space"}
{"id":"mech_007","query":"Cross-model portability check","expected":"behavior_consistent_across_targets","strategy":"recon_adaptation"}
```

Add cases as new failure modes are observed. Each entry is a regression test for the rubric itself.

## Validation

This file's own validation — meta-validation, since the file IS the validator.

### Structural checks on the rubric

- [ ] All 10 mechanistic dimensions have explicit 0/5/10 anchors.
- [ ] Scoring procedure named explicitly, matched to stakes.
- [ ] Inter-rater agreement measured when ≥2 raters used.
- [ ] LLM-judge prompt is the same rubric, scored independently per dimension (not "overall vibe").
- [ ] Composite merge with `validation-rubric.md` documented; both rubrics treated as independent gates.
- [ ] Per-use-class threshold table present; thresholds defended (not arbitrary).

### Probe-based validation of the rubric itself

- **Calibration drift**: every quarter, re-score 5 known-good and 5 known-bad prompts from the archive. If scores have drifted, the rubric anchors need re-tuning.
- **Inter-rater agreement** (when applicable): Cohen's kappa or % agreement across all dimensions. Below 0.7 → the rubric is too subjective; rewrite the dimension descriptions until agreement rises.
- **Goodhart probe**: pick a high-scoring prompt, mutate it to game ONE dimension (e.g. add fake anchors that pass density check but are decorative). If the rubric still scores it high, that dimension's check is gameable; tighten with structural-check requirements.

### Empirical sanity check on the rubric

Annual: collect production failures from prompts that passed the gate. For each, identify which rubric dimension *should* have caught it. If a dimension never catches anything, it's decorative — drop or replace. If the same failure type recurs across dimensions, the rubric needs a new dimension.

## Interactions

This file integrates **every** other file in the directory. The composite rubric is the integration point.

| Source file | Rubric dimension(s) it feeds | Direction |
|---|---|---|
| `model-recon.md` | Recon Coverage; gates Tokenizer Awareness | Recon outputs → multiple dimensions |
| `tokenizer-aware-lexicon.md` | Domain Anchors; Tokenizer Awareness | Per-file pass → rubric inputs |
| `persona-clusters.md` | Lens Operationalization | Per-file pass → rubric input |
| `ordering-and-position.md` | Position Control | Per-file pass → rubric input |
| `formatting-as-signal.md` | Formatting Discipline | Per-file pass → rubric input |
| `negative-space.md` | Negative-Space Discipline | Per-file pass → rubric input |
| `references-and-evals.md` | Evidence Scaffolding; Preregistered Eval | Per-file pass → rubric inputs (two dimensions) |
| `mechanistic-foundations.md` | Background only — not directly scored | Conceptual substrate |
| `prompt-model/validation-rubric.md` | Structural rubric (60 pts) — separate axis | Composite merge per §4 |
| `prompt-model/cognitive-models.md` | Lens Operationalization (invented-persona path) | Source for invented-persona scoring |
| `prompt-model/structural-patterns.md` | Existing structural rubric content | Composite merge per §4 |
| `CoV/CoV.md` (O-CoV) | Persona-loop convergence; falsifiability | Mechanism for the loop-stop rule scored under Lens Operationalization |
| `RL-O-CoV` (training-side) | Reward features can use rubric dimensions as observables | This file is the eval target O-CoV trains toward |

**Order**: this file runs **last**, after every per-technique procedure has been applied and self-checked. Running the composite before the per-technique procedures is meaningless — there is nothing yet to integrate.

**Do not run twice in the same revision.** A composite that passes after revision A and fails after revision B is the signal that revision B regressed something. A composite that fails twice in a row indicates a deeper structural issue — return to per-technique work, do not iterate on the rubric score.

## Failure modes

| Symptom | Diagnosis | Fix |
|---|---|---|
| Rubric score is high but production failures continue | Rubric is being gamed; one or more dimensions reward surface structure rather than substance | Apply Goodhart probe per Validation §; tighten the gameable dimension's check |
| Inter-rater agreement is low (κ < 0.7) | Rubric anchors are too subjective | Rewrite dimension descriptions with specific structural criteria; remove vibes-based language |
| Author's score is consistently ≥10 points higher than independent judge | Motivated reasoning by author; rubric is being optimised against, not validated by | Switch to LLM-judge primary, author secondary; trust judge on disagreements |
| Composite passes but per-technique check failed and was ignored | Per-technique gate skipped | Re-introduce §1 hard stop; composite cannot rescue an unfinished technique |
| Production passes the gate but breaks under prompt-injection | Channel-hierarchy variant not in regression suite | Add channel-relocation variant to §6 strategies; gate against it |
| Two rubrics (structural + mechanistic) treated as one negotiable score | Composite-merge rules violated; high structural compensating for low mechanistic | Re-read §4; both must pass their independent thresholds, not just the sum |
| Same prompt scores differently across raters with no obvious reason | Rubric anchors drifting in the rater's heads | Run calibration drift probe; re-score archive fixtures; retune anchors |
| LLM-judge gives consistent 100/100 perfect scores | Judge prompt isn't structured per-dimension; defaulting to surface vibe | Audit judge output: does it quote evidence per dimension? If not, the judge prompt isn't enforcing the rubric |
| Production-class prompt deployed without composite | Gate skipped under deadline pressure | Make the gate enforcement automated where possible; for skill/plugin code paths, fail CI on missing composite block |
| Per-technique files updated, composite weights stale | The two layers drifted | When a technique file changes its `## Validation` section, audit the corresponding rubric dimension here for consistency |

## References

- [Validation rubric (existing)](../validation-rubric.md) — the 60-point structural rubric this composite merges with
- [Structural patterns](../structural-patterns.md) — feeds the structural rubric
- [Cognitive models](../cognitive-models.md) — feeds the Lens Operationalization dimension via invented-persona path
- [O-CoV framework](../../CoV/CoV.md) — convergence mechanism scored under Lens Operationalization
- [RL-O-CoV](../../../../RL-O-CoV/README.md) — uses this rubric's dimensions as reward observables
- [Self-Rewarding Language Models](https://arxiv.org/abs/2401.10020) — generator-judge alignment basis for §3 LLM-judge procedure
- [Cohen's kappa for inter-rater agreement](https://en.wikipedia.org/wiki/Cohen%27s_kappa) — measurement basis for the regulated-stakes scoring procedure
- [Goodhart's Law in evaluation](https://en.wikipedia.org/wiki/Goodhart%27s_law) — why this file requires composite gates rather than single scores
- See also: every other file in this directory feeds into this one (see Interactions table above)
