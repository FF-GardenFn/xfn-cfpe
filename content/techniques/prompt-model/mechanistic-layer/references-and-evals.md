# References, Source Packs, and Preregistered Evals

## What

Ground generation in **external anchors that constrain what counts as evidence and what counts as success**. Two related but distinct techniques:

- **Track A — Source Pack**: inject citations and evidence with explicit reliability tiers and `use_for` labels so the model attends to provided sources before drawing on unstated training memory.
- **Track B — Preregistered Evals**: bake pass/fail criteria (executable tests for code, falsifiability conditions for analysis) into the prompt itself so success is defined *before* generation, not negotiated after.

Both tracks share a single mechanism (external anchors), so they live in one file. Each has its own triggers and procedure.

## Mechanism

**Sources suppress fluent hallucination.** When a prompt provides explicit `<source>` blocks with attached `use_for` labels, the model's attention preferentially routes through the provided tokens rather than reaching into general training memory. The mechanism is the same as in retrieval-augmented generation (Lewis et al. 2020): explicit context dominates parametric knowledge when the explicit context is structurally legible. Without sources, the model fills gaps with confident-sounding interpolation; with sources, it has explicit material to bind claims to. Adding `<evidence_contract>` rules ("attach source IDs to factual claims", "do not cite a source for a claim it does not support") makes the binding inspectable.

**Preregistration aligns the prompt with the rubric.** When the prompt declares the success criteria upfront (`acceptance_tests`, `falsifiability` conditions, `must_pass` commands), generation is conditioned on those criteria from the first token. The model's next-token distribution is shifted toward outputs that satisfy the named criteria, because the criteria are part of the prompt's residual stream. Without preregistration, the model optimises for "looks correct" — the centroid of pleasing-sounding answers — which is exactly the trendslop the eval is supposed to filter out. The asymmetry is sharp: a test mentioned after the fact is a check; a test stated before generation is a constraint.

**Source-ladder authority gradient.** Different source types carry different authority for the model. Official specifications and standards bodies activate the model's "this is the canonical answer" attractor; secondary blogs activate the "popular interpretation" attractor; forum posts activate the "community workaround" attractor. The reliability tier you state in the source block influences how the model weighs conflicting evidence within the prompt itself.

These are behavioural correlates of how training data and instruction-following data shape attention. Validate per task (see Validation), not by faith.

## Trigger conditions

### Track A (Source Pack) — apply when **any** are true

- The task involves **factual claims** that can be wrong: empirical results, API behaviour, regulatory rules, financial data, published benchmarks, historical events, code-library specifics.
- The model's training cutoff predates the relevant facts (newer APIs, post-cutoff events, recent papers).
- The task is **high-stakes** enough that fluent-but-wrong is materially worse than honest "I don't know".
- The prompt is in a domain with **established authoritative sources** (RFCs, ISO standards, official docs, peer-reviewed literature).
- You expect the output to be **audited or cited downstream** — the source IDs become traceability for the audit.

### Track B (Preregistered Evals) — apply when **any** are true

- The output will be evaluated against a **specific, namable success criterion** (passing tests, hitting a benchmark, satisfying a rubric, meeting a contract).
- The task is **code generation** (preregister the tests).
- The task is **strategic analysis or design** (preregister the falsifiers — what evidence would change the conclusion).
- The task involves **multiple revisions** — preregistration prevents goalpost-moving across iterations.
- The output will be **scored by an LLM judge** — preregistering the criteria the judge uses aligns generator and judge.

Apply both tracks together when the task is high-stakes AND has executable success criteria (production code with required test coverage, regulated analysis with mandated citations).

## Anti-trigger conditions

### Track A (Source Pack) — do **not** apply when **any** are true

- **Pure-opinion or creative tasks.** "Write a poem about autumn" needs no source pack; injecting one constrains creativity for no benefit.
- **The user asked the model to operate from its own knowledge specifically.** "What do you know about X" is a request to *reach into parametric memory*, not to defer to provided sources.
- **The available sources are lower-quality than the model's training knowledge.** A blog post citing a misreading of an RFC is worse than nothing; the model would have given a more accurate answer without the misleading source.
- **Source pack would dwarf the actual task.** If providing 20 papers for a 1-paragraph question, you've inverted the signal-to-noise ratio.

### Track B (Preregistered Evals) — do **not** apply when **any** are true

- **The task has no objective success criterion.** "Write something interesting" cannot be preregistered; the eval would be subjective and the prompt would invite gaming.
- **The criteria are not knowable in advance.** Genuine exploration / brainstorming where the user does not yet know what good looks like.
- **The criteria would over-constrain a legitimately open task.** Preregistering "must use X library" when the task is "pick the best library" defeats the task.
- **The "test" is just restating the task.** A `must_pass: code compiles` for a code task is dead weight; compilation is implicit.

If anti-triggers fire for either track, drop that track but consider keeping the other — they are independent.

## Procedure

### Track A — Source Pack

#### A.1 Build the source pack with explicit `use_for`

Every source needs three things: an **ID** (for citation), a **reliability tier**, and a **`use_for`** label. The `use_for` is the lever — it tells the model *why* this source is in scope.

```xml
<source_pack>
  <source id="S1" type="paper" reliability="high">
    <title>Lost in the Middle: How Language Models Use Long Contexts</title>
    <url>https://arxiv.org/abs/2307.03172</url>
    <use_for>Position-effect measurements for long-context QA.</use_for>
  </source>
  <source id="S2" type="docs" reliability="high">
    <title>OpenAI tiktoken</title>
    <url>https://github.com/openai/tiktoken</url>
    <use_for>Token counting and BPE behaviour for OpenAI-family models.</use_for>
  </source>
  <source id="S3" type="blog" reliability="medium">
    <title>Practitioner notes on prompt-injection mitigations</title>
    <url>...</url>
    <use_for>Real-world failure-mode catalogue. Do not cite for theoretical claims.</use_for>
  </source>
</source_pack>
```

The reliability tag is not decoration — it tells the model how to weigh the source against other sources and against its own memory.

#### A.2 Source reliability ladder (with override rule)

Default authority order, highest to lowest:

```
1. Official spec / standards body (RFC, ISO, W3C, IFRS)
2. Peer-reviewed paper / conference proceedings
3. Official model card / technical report
4. Official documentation (API docs, library docs, framework guides)
5. Source code / tests of the canonical implementation
6. Reputable secondary analysis (textbook, established practitioner blog)
7. Forum / Stack Overflow / community wiki
8. Social-media post / undated blog
```

**Override rule (when to invert the ladder):**

For **fast-moving APIs and libraries**, source code and tests can outrank stale official documentation. If the official docs were last updated two years ago and the library shipped a major version since, the docs may be wrong; the test suite for the current version is authoritative. Mark the override explicitly in the source pack:

```xml
<source id="S4" type="source_code" reliability="high"
        override_ladder="true" override_reason="API changed in v3, official docs not updated">
  <path>node_modules/auth.js/src/server.ts</path>
  <use_for>Authoritative current API for Auth.js v5; preferred over the v4-era docs site.</use_for>
</source>
```

Other valid overrides:
- **Regulatory/legal**: jurisdiction-current statutes outrank federal-level summaries when the case is jurisdictional.
- **Medical**: post-trial published results outrank pre-trial protocol docs.
- **Security**: current CVE advisories outrank vendor marketing for the same product.

#### A.3 Evidence contract

```xml
<evidence_contract>
  <rule>Use provided sources before relying on unstated memory.</rule>
  <rule>Attach source IDs (S1, S2, ...) to every factual claim.</rule>
  <rule>Mark unsupported claims as assumptions, not facts.</rule>
  <rule>Do not cite a source for a claim it does not support.</rule>
  <rule>If sources conflict, surface the conflict; do not silently pick one.</rule>
</evidence_contract>
```

The rules are operational. Without them, the source pack is decoration.

#### A.4 Reference placement (locality, not segregation)

Place sources **near the claims they constrain**, not in a giant references block at the start.

```xml
<!-- Bad: sources segregated from the analysis they support -->
<references>... 20 links ...</references>
<task>Analyse revenue recognition.</task>

<!-- Better: sources adjacent to the analysis -->
<revenue_analysis>
  <standard>IFRS 15</standard>
  <source id="S1">Official IFRS 15 summary, Section 5.</source>
  <data>... contract terms ...</data>
  <test>Identify performance obligations before recognising revenue.</test>
</revenue_analysis>
```

Same rule as `tokenizer-aware-lexicon.md`: anchors near their use sites, not segregated.

#### A.5 Screenshots and runtime artefacts

Treat screenshots, logs, and traces as **first-class evidence**, not illustrations. Each gets the same `use_for` and `observations` treatment.

```xml
<screenshot id="UI1">
  <path>artifacts/screenshots/billing-empty-state.png</path>
  <caption>Current billing empty state at 1440x900.</caption>
  <observations>
    <item>Primary CTA is below fold.</item>
    <item>Error copy overlaps plan selector.</item>
  </observations>
  <use_for>Layout constraint and visual regression baseline.</use_for>
</screenshot>

<log id="L1">
  <path>artifacts/logs/payment-failure-2026-04-30.txt</path>
  <observations>
    <item>Stack trace at line 142 of payment_processor.py.</item>
    <item>Race condition signature: two concurrent webhooks for same charge ID.</item>
  </observations>
  <use_for>Reproduction trigger and root-cause anchor.</use_for>
</log>
```

If a screenshot or log isn't available, link the issue, design file, or browser test that would produce it.

#### A.6 Citation density calibration

| Task | Source count |
|---|---|
| Plain conversational answer | 0 |
| Simple coding change | 0–3 (just docs/tests for the touched module) |
| Library integration | 2–6 (official docs + 1-2 examples) |
| Strategic analysis | 5–12 (mixed authority tiers, indexed) |
| Literature review | 10–30 (indexed and grouped by topic) |
| Legal / medical / financial / compliance | Authoritative sources required, no upper limit |

Drowning the prompt in sources dilutes attention; under-citing invites hallucination. Calibrate by stakes.

### Track B — Preregistered Evals

#### B.1 For code: preregister the tests

Tests are the executable definition of correct. State them before the implementation prompt.

```xml
<preregistered_tests>
  <test id="T1">
    <command>pytest tests/billing/test_proration.py::test_midcycle_upgrade_rounds_to_cents</command>
    <expected>pass</expected>
    <guards_against>Incorrect rounding and partial-period double charge.</guards_against>
  </test>
  <test id="T2">
    <command>pytest tests/billing/test_refund_ledger.py</command>
    <expected>pass</expected>
    <guards_against>Non-idempotent refund entries.</guards_against>
  </test>
</preregistered_tests>
```

The `guards_against` field matters. It tells the model what failure mode each test exists to catch — which conditions generation just as much as the test command itself.

#### B.2 Test-first prompt pattern

```xml
<task>Implement monthly-to-annual plan upgrade proration.</task>

<acceptance_tests>
  <must_pass>pytest tests/billing/test_proration.py</must_pass>
  <must_pass>pytest tests/billing/test_invoice_preview.py</must_pass>
</acceptance_tests>

<workflow>
1. Read existing billing code.
2. Confirm or add failing tests for the acceptance cases.
3. Implement the smallest change that makes tests pass.
4. Run the preregistered tests and report exact commands and results.
5. Do NOT report success without showing test output.
</workflow>
```

The "do NOT report success without showing test output" rule is critical — without it, models produce confident "implemented and tested ✓" claims with no actual run. Preregistration without enforcement is theatre.

#### B.3 For strategic / analytical tasks: falsifiability contract

When tests aren't executable, use falsifiability — name the evidence that would change the answer.

```xml
<falsifiability>
  <claim id="C1">The product can win through developer-led distribution.</claim>
  <would_weaken>If activation-to-paid conversion is below 3% after 90 days.</would_weaken>
  <would_strengthen>If organic usage grows in teams without sales intervention.</would_strengthen>
</falsifiability>
```

The output must state, per claim, what evidence would update it. This converts opinion-shaped output into Popper-shaped output: a claim is only useful if you can name what would refute it.

#### B.4 Preregister the LLM-judge rubric (when applicable)

If the output will be scored by another LLM (judge or evaluator), include the rubric in the prompt itself. Generator and judge then optimise the same target.

```xml
<judge_rubric>
  <criterion weight="0.4">Cites source IDs for every factual claim.</criterion>
  <criterion weight="0.3">Identifies at least one disconfirming consideration per recommendation.</criterion>
  <criterion weight="0.2">Final recommendation is actionable (specifies who, what, when).</criterion>
  <criterion weight="0.1">Adheres to <output_contract> shape.</criterion>
</judge_rubric>
```

If you don't surface the judge rubric to the generator, the generator optimises for centroid-pleasingness and the judge filters on something else — silent disagreement that costs runs.

#### B.5 Evidence-aware output contract (Track A + Track B together)

```xml
<output_contract>
  <section name="Claim">State the recommendation in one sentence.</section>
  <section name="Evidence">List source-backed evidence using source IDs (S1, S2, ...).</section>
  <section name="Assumptions">List unsupported but necessary assumptions.</section>
  <section name="Tests">List preregistered tests or falsifiers, with status.</section>
  <section name="Uncertainty">State what evidence would change the conclusion.</section>
</output_contract>
```

When both tracks are active, the output contract enforces both: every claim cites a source AND every claim has a falsifier. This is the production-grade shape.

## Validation

### Structural checks (the LLM can self-verify)

#### Track A
- [ ] Every source has an ID, a reliability tier, and a `use_for` label.
- [ ] Sources are placed adjacent to the claims they constrain (locality, not a giant references block at start).
- [ ] `<evidence_contract>` rules are stated (especially "do not cite a source for a claim it does not support").
- [ ] Source-ladder overrides (when applied) are marked explicitly with `override_reason`.
- [ ] Citation density matches stakes per the table in §A.6.
- [ ] Screenshots and logs include `<observations>`, not just paths.

#### Track B
- [ ] Acceptance tests / falsifiers preregistered before the task block.
- [ ] Each test has a `guards_against` field.
- [ ] Workflow forbids reporting success without showing test output.
- [ ] If LLM-judged: judge rubric is included in the prompt itself.
- [ ] Output contract requires citing test status / falsifier evaluation in the response.

### Probe-based validation

- **Citation-coverage check** (planned `probes/citation_coverage.py`): regex for source IDs in the model's output; flag any factual-shaped sentence (subject-verb-object claim) that has no adjacent ID. Output a directive: "12 factual claims, 7 cited, 5 uncited — require citation or label as inferred."
- **Test-execution honesty**: in agent settings, log whether the model actually executed the preregistered tests vs. reported success without running them. False-success rate above ~5% means the workflow rule needs strengthening.
- **Source-pack ablation**: run the prompt with and without the source pack; if outputs are nearly identical, the pack was decorative — either the model already knew, or the sources weren't bound to claims. Either way, fix the binding (`use_for`, evidence contract) or drop the pack.
- **Falsifier coverage**: count claims; count claims with explicit `would_weaken` / `would_strengthen` conditions. Aim for ≥80% coverage of load-bearing claims.

### Empirical sanity check

For Track A: a/b test with the source pack present (a) vs. with deliberately-misleading sources injected (b). If output changes appropriately in (b) — i.e. the model defers to the (now wrong) provided source — the binding is working. If output ignores the misleading source and gives the correct answer from training memory, the source pack isn't actually constraining generation; tighten the evidence contract.

For Track B: run the prompt 10 times. Count how many runs (a) actually ran the preregistered tests, (b) reported test output verbatim, (c) honestly flagged failures. False-success rate >0% on (c) is a workflow bug, not a model bug.

## Interactions

| Stacks well with | Conflicts with | Order rule |
|---|---|---|
| `tokenizer-aware-lexicon.md` | — | Source `<use_for>` labels should reuse the canonical anchors from the lexicon — same exact strings |
| `persona-clusters.md` | — | Lens construction's `<source_basis>` block IS a Track A source pack scoped to the lens — same pattern, narrower scope |
| `formatting-as-signal.md` | — | `<source_pack>`, `<evidence_contract>`, `<acceptance_tests>`, `<falsifiability>`, `<output_contract>` are canonical block names; reuse them |
| `ordering-and-position.md` | — | Sources adjacent to claims (attention locality); `<output_contract>` at tail; per-section sources inside per-section blocks |
| `negative-space.md` | — | Bans like "do NOT cite sources you cannot verify" belong inside `<evidence_contract>`; "do NOT report success without showing test output" belongs inside `<workflow>` |
| `model-recon.md` | — | Recon's **training cutoff** field tells you which facts MUST come from sources (post-cutoff); recon's **tool access** field tells you whether the model can actually run the preregistered tests |
| **Pure creative / opinion task** | ✗ Track A | Source pack constrains creativity; drop |
| **No objective success criterion** | ✗ Track B | Preregistration would invite gaming; drop |
| **Sources lower-quality than training memory** | ✗ Track A | Misleading sources actively degrade output; better to skip |
| **"Test" that just restates task** | ✗ Track B | Dead weight; drop the trivially-passing assertion |

**Order within a single prompt**: `<source_pack>` near the head (sets evidence base) → `<acceptance_tests>` / `<falsifiability>` near the head or just before the task (gates success) → `<task>` → `<workflow>` (with execution rules) → `<output_contract>` at tail (forces the citation/test-status shape).

## Failure modes

| Symptom | Diagnosis | Fix |
|---|---|---|
| Output cites sources that don't support the claim | Evidence contract missing or weak; "do not cite a source for a claim it does not support" rule absent | Add explicit rule; require `<source_id>` quoted excerpt for high-stakes claims |
| Output ignores provided source pack and answers from training memory | No `use_for` labels; sources segregated in a `<references>` block instead of placed near claims | Add `use_for`; move sources adjacent to relevant analysis blocks |
| Output uses fast-moving-API source incorrectly because it followed stale official docs | Source-ladder override rule not applied; docs outranked source code by default | Mark current source code with `override_ladder="true"` and `override_reason` |
| Output reports "tests pass ✓" without actually running tests | Workflow rule ("do NOT report success without showing test output") missing | Add the rule; if agent can run shell, require verbatim command output in response |
| Falsifiability section is generic ("more research is needed") | Falsifiers not preregistered per-claim; model added them as afterthought | Preregister falsifiers in the prompt with `would_weaken` / `would_strengthen` per `<claim>` |
| Source-ablation test shows identical output with/without sources | Sources weren't bound to generation — likely no evidence contract, no per-claim citation requirement | Add `<evidence_contract>` rules; require source IDs in the output contract |
| LLM-judge scores low despite strong-looking output | Judge rubric not surfaced to generator; generator optimised for centroid-pleasing | Include `<judge_rubric>` in the generator prompt; align targets |
| Output drowns in citations, every sentence has 3 source IDs | Citation density miscalibrated; injected source pack too large | Reduce sources to top-N most authoritative per claim; drop tertiary sources |
| Output cites a non-existent source ID | Source pack referenced an ID that's not actually in the pack OR model hallucinated an ID | Validate generated source IDs against the pack regex; reject responses with unknown IDs |

## References

- [Retrieval-Augmented Generation](https://arxiv.org/abs/2005.11401) — Lewis et al. 2020, the source-grounding mechanism this file relies on
- [Evaluating Large Language Models Trained on Code](https://arxiv.org/abs/2107.03374) — Chen et al. 2021, the preregistration-of-tests pattern
- [Constitutional AI](https://arxiv.org/abs/2212.08073) — Anthropic, principles-based steering including evidence rules
- [Self-Rewarding Language Models](https://arxiv.org/abs/2401.10020) — Yuan et al. 2024, generator-judge alignment
- [Anthropic XML tags](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/use-xml-tags) — canonical block-name conventions
- [OpenAI evals framework](https://github.com/openai/evals) — preregistered eval tooling
- See also: `mechanistic-foundations.md` (the why), `tokenizer-aware-lexicon.md` (anchors that source `use_for` should reuse), `persona-clusters.md` (`<source_basis>` is lens-scoped source pack), `formatting-as-signal.md` (canonical block names), `ordering-and-position.md` (source locality near claims, output contract at tail), `negative-space.md` (evidence-contract rules ARE explicit subtraction), `model-recon.md` (training cutoff and tool access constrain both tracks), `validation-and-integration.md` (composite rubric)
