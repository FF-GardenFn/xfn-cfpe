# Tokenizer-Aware Lexicon Design

## What

Replace generic phrasing with deliberately-chosen field-specific terms (anchors) that compress assumptions, navigate token space toward dense expert-written training data, and lock local meaning so subsequent reasoning does not drift.

## Mechanism

Three independent forces make canonical jargon work, all of which trace back to how transformers store and retrieve information.

**BPE merge depth.** Subword tokenizers (BPE, SentencePiece, tiktoken) assign token IDs in merge order. Early merges are byte-level fallbacks and the most common short patterns (`the`, ` is`, `make`, `sure`). Late merges are rare multi-character patterns assembled because a specific corpus needed them (`idempotency`, `SSRF`, `proration`). A high token ID is a coarse proxy for "this string mostly appeared in specialised training data."

```
"make sure it works correctly"  →  ["make", " sure", " it", " works", " correctly"]
                                    early merges, low IDs, filler
"verify idempotency under retry" →  ["verify", " idemp", "otency", " under", " retry"]
                                    mixed, with " idemp" + "otency" carrying high IDs
```

**MLP key-value lookup.** Mid-stack MLP layers act like a soft key-value store: the input vector is matched against $W_{in}$ "key" rows; matched keys gate $W_{out}$ "value" rows that are added back to the residual stream. Canonical anchors point at sharper keys with denser, more specific values — typically expert-authored documentation, standards, postmortems, textbook prose. Generic verbs (`analyze`, `consider`, `look at`) point at smeared keys whose values are the centroid of every blog post.

**Co-occurrence retrieval.** A term like `threat model` co-occurs in training data with adjacent procedure tokens (`STRIDE`, `attack surface`, `trust boundary`, `mitigation`). Conditioning on the anchor pulls the adjacent procedure tokens up the next-token distribution, even when the prompt does not name them. Anchors are recall handles for entire procedural patterns, not just labels.

These are heuristics — token rarity correlates with model attention but is not a direct measurement of internal computation. Validate empirically (see Validation), not by faith.

## Trigger conditions

Apply this technique when **any** are true:

- The task spans a **technical domain** with established standards, procedures, metrics, or failure modes (software, security, finance, medicine, law, ML, infra, design systems, scientific methodology).
- The user's request contains **vague verbs** (`analyze`, `review`, `look at`, `improve`, `make better`) attached to a domain-specific object — i.e. the verb is filler and the object is the actual signal.
- The output will be evaluated against **domain-specific quality criteria** that have canonical names (WCAG levels, p99 latency, ROIC, CWE classifications).
- The receiving prompt will be reused across many similar tasks — investing in a precise lexicon pays back over many runs.

Apply with **higher density** (12-15 anchors, full glossary) when additionally:

- The task involves cross-domain synthesis (the prompt has to reason across two technical fields and avoid polysemy collisions).
- The output is a strategic decision, an audit, or a compliance artefact where every load-bearing term must be defined locally.
- Stakes are high enough that drift into the wrong adjacent meaning would be costly.

## Anti-trigger conditions

Do **not** apply heavy lexicon when **any** are true:

- **General-audience writing.** Marketing copy, explainers for non-experts, plain-language summaries. Jargon here excludes the actual reader; the wrong neighborhood for the output, not just the prompt.
- **Pure execution task with no judgment.** "Sort this list", "convert this CSV to JSON", "translate to French" — anchors add tokens without changing the answer.
- **The user explicitly asked for plain language.** Honor it; the model will respect a plain-language directive *more* if the prompt itself is plain.
- **The "anchor" is fake jargon.** If a term cannot be cited from at least one authoritative source in the field, it is buzzword-shaped noise. Smearing on words like `synergy`, `holistic`, `next-gen`, `paradigm-shift`, `disruptive` activates marketing centroids and degrades output. Better to use no anchor than a fake one.
- **The model is small or out-of-domain.** Sub-7B models often lack tight representation of late-merge tokens; the anchor degrades to a high-friction split with no payoff. Non-English domains hit similar problems on English-trained tokenizers.
- **Anchors would override an explicit user constraint.** If the user says "use my company's internal terminology" and provides a list, do that — your canonical bundle is an opinion, not a law.

If anti-triggers fire, fall back to: (a) plain-language with a *single* well-defined load-bearing term per concept, or (b) skip anchoring entirely.

## Procedure

### 1. Build the canonical bundle (extract → filter → probe → cap)

The "domain lexicon build process" — made executable.

1. **Collect authoritative sources** for the field: textbooks, RFCs, standard-body documents, peer-reviewed survey papers, canonical practitioner blogs, official documentation, postmortems. Aim for ≥5 sources, mixing theory and practice.
2. **Extract candidate n-grams** (1-3 word) by tf-idf against a general-corpus baseline (or by manual ranking if no corpus tooling is at hand). Rank descending. Take top ~200.
3. **Filter for procedurality.** Keep only terms that imply a verb, a check, a metric, a failure mode, or a known artefact. Drop tone words, brand words, sentiment words. Procedural test: *can a practitioner immediately name what they would do differently if this term applies?* If no, drop.
4. **Tokenizer probe.** Encode each surviving candidate across the target tokenizer(s). Drop or define candidates that fragment into many fragile pieces (high friction — see step 2 below for the probe).
5. **Cap at 8-15 anchors.** More is noise. Lexicon density beyond ~15 starts to fight itself: anchors crowd each other and the model's attention budget gets diluted.
6. **Reuse the exact strings** in three places: the `<domain_anchors>` block, the task block, and the output contract / rubric. Repetition of the *exact* spelling lets the model bind the local meaning to the same token sequence each time it appears.

### 2. Tokenizer probe (runnable, falls back gracefully)

```python
# Requires: pip install tiktoken
import tiktoken

CANDIDATES = ["idempotency", "ARR", "Q4FY26 ARR", "SSRF",
              "make it good", "blast radius", "your-internal-AcRoNyM"]

for enc_name in ("cl100k_base", "o200k_base"):
    enc = tiktoken.get_encoding(enc_name)
    print(f"\n{enc_name}")
    print(f"  {'string':<28}  {'n_tok':>5}  fragments")
    for s in CANDIDATES:
        ids = enc.encode(s)
        frags = [enc.decode([i]) for i in ids]
        print(f"  {s:<28}  {len(ids):>5}  {frags}")
```

Read the output for two signals:

- **Token count vs character count.** A 12-character canonical term that produces 2 tokens is well-merged (the corpus uses it often). A 12-character custom acronym that produces 6 tokens fragments badly — it is high-friction.
- **Fragment shape.** `["idemp", "otency"]` is two coherent merges. `["Q", "4", "F", "Y", "26", " AR", "R"]` is byte-level fallback territory — the tokenizer has no useful merge for this, so attention has nothing to anchor onto.

If `tiktoken` is unavailable: use the heuristic *character count divided by ~4* as a baseline expectation for English text. Strings that come out materially worse than that ratio are high-friction. Or use the Hugging Face tokenizers playground at https://huggingface.co/spaces.

### 3. Glossary anchor pattern (lock local meaning)

Define load-bearing terms locally even when they're well-known to the model. The point is not to teach the model what ARR is. The point is to **lock the local meaning** and prevent drift into adjacent terms.

```xml
<glossary>
  <term id="arr">
    <name>ARR</name>
    <definition>Annual recurring revenue. Subscription revenue normalised to yearly run rate.</definition>
    <do_not_confuse_with>GAAP revenue, bookings, GMV</do_not_confuse_with>
  </term>
  <term id="nrr">
    <name>NRR</name>
    <definition>Net revenue retention from existing customers, including expansion, contraction, and churn.</definition>
    <decision_relevance>Tests whether growth is durable without constant new acquisition.</decision_relevance>
  </term>
</glossary>
```

`<do_not_confuse_with>` is the lever. Naming the adjacent meanings explicitly lets the model suppress them — the same trick the negative-space technique applies more generally.

### 4. Canonical term bundles by field (starter set)

These are seed bundles, not gospel. Extend per task. Each bundle is intentionally 8-12 anchors, cap at 15.

```xml
<domain_anchors field="software_architecture">
bounded context; idempotency; backpressure; schema migration; contract test;
observability; rollback; eventual consistency; blast radius
</domain_anchors>

<domain_anchors field="application_security">
threat model; attack surface; trust boundary; SSRF; authz bypass;
secret leakage; dependency confusion; exploitability; compensating control
</domain_anchors>

<domain_anchors field="venture_investing">
market size; wedge; distribution; burn multiple; net dollar retention;
founder-market fit; platform risk; switching cost; power law
</domain_anchors>

<domain_anchors field="systems_performance">
USE method; tail latency; saturation; queue depth; cache thrash;
GC pause; lock contention; allocator pressure; CPU stalls
</domain_anchors>
```

Generic-anchor lookup table for quick reference:

| Field | Generic phrasing (avoid) | Canonical anchor (prefer) |
|---|---|---|
| Software | "make it good" | `red-green-refactor`, `contract test`, `idempotency`, `race condition` |
| Security | "check risks" | `threat model`, `CWE`, `CVE`, `SSRF`, `least privilege` |
| Finance | "is this a good company" | `ROIC`, `free cash flow`, `unit economics`, `working capital` |
| Medicine | "is this safe" | `contraindication`, `differential diagnosis`, `standard of care` |
| Law | "legal issue" | `jurisdiction`, `burden of proof`, `material breach`, `precedent` |
| Product | "users like it" | `activation`, `retention cohort`, `switching cost`, `jobs-to-be-done` |
| ML / data | "improve the model" | `validation split`, `data leakage`, `label drift`, `class imbalance` |
| Infra / SRE | "make it reliable" | `error budget`, `SLO`, `blast radius`, `mean time to recovery` |

### 5. Anti-polysemy disambiguation

Some words mean different things in different fields. If the prompt mixes domains, the model picks the wrong sense and reasoning silently drifts.

| Word | Possible meanings |
|---|---|
| margin | profit margin, CSS margin, safety margin, page margin |
| model | ML model, financial model, conceptual model, fashion model |
| agent | LLM agent, legal agent, sales agent, biological agent |
| token | LLM tokenizer unit, crypto token, OAuth token, arcade token |
| context | prompt context, business context, database context |
| latency | network latency, perceived latency, neural response latency |

Disambiguate explicitly when the polysemy is in scope:

```xml
<disambiguation>
  <term>token</term>
  <meaning>LLM tokenizer unit, not crypto token and not OAuth token.</meaning>
</disambiguation>
```

### 6. Library and API anchors (for coding tasks)

Exact package, version, framework, and API names reduce generic-tutorial drift far more than abstract anchors do.

Weak:

```xml
<task>Build authentication.</task>
```

Strong:

```xml
<stack>
  <language>TypeScript</language>
  <framework>Next.js 15 App Router</framework>
  <auth>Auth.js v5</auth>
  <database>Postgres with Prisma</database>
</stack>

<docs>
  <source id="authjs-session">https://authjs.dev/reference/core</source>
  <source id="next-middleware">https://nextjs.org/docs/app/building-your-application/routing/middleware</source>
</docs>
```

Naming `Auth.js v5` instead of "an auth library" pulls generation toward Auth.js v5's actual API surface — `auth()`, `signIn()`, server-component sessions — instead of the centroid of every "build auth" tutorial ever written. Same idea as named-persona vs generic role.

### 7. Calibrate density to task

Lexicon density is a dial, not a constant. Over-anchoring is the most common failure mode for users new to the technique.

| Task type | Lexicon density | Notes |
|---|---|---|
| Plain-audience explainer | none / low (1-3 anchors with definitions) | Anchors here are pedagogical, not navigational |
| Single-domain technical task | medium (5-10 anchors) | Standard case |
| Cross-domain synthesis | high (12-15 anchors, separated by `<field>` tags) | Disambiguation mandatory |
| Strategic / audit / compliance | high with full glossary | Every load-bearing term defined locally |
| Pure execution / format conversion | none | Anchors are dead tokens |

If you find yourself reaching for a 16th anchor, you are probably solving the wrong problem — split the task into two prompts or accept that the marginal anchor is decorative.

## Validation

### Structural checks (the LLM can self-verify)

- [ ] Anchors are real domain terms (each can be cited from at least one authoritative source).
- [ ] Anchor count is in the 8-15 band (or explicitly justified outside it for plain-language / pure-execution / cross-domain cases).
- [ ] Load-bearing terms are defined locally with `<glossary>` or `<term_definitions>` blocks.
- [ ] Polysemous words appearing across domain boundaries are disambiguated.
- [ ] The same exact anchor strings appear in `<domain_anchors>`, the task block, and the output contract / rubric.
- [ ] No buzzword-shaped tokens (`synergy`, `holistic`, `next-gen`, `paradigm`, `disruptive`).

### Probe-based validation

- **Anchor density** (planned `probes/anchor_density.py`): tokenize the draft, classify each token by ID percentile against the prompt-wide distribution, count tokens above the 80th percentile in instruction slots. Below ~15% in instruction slots = under-anchored. Above ~50% = jargon-dumping.
- **Tokenizer friction** (planned `probes/tokenizer_friction.py`): run the §2 tokenizer probe over each candidate anchor across cl100k / o200k / llama3 / gemma. Flag any anchor whose token count exceeds 1.5× its character-count / 4 baseline in the target tokenizer — these are high-friction and need definitions.
- **Polysemy-collision check**: scan anchor list against a known-polysemy set; if a polysemous word appears without an adjacent `<disambiguation>` block, flag.

### Empirical sanity check

For a fixed task, run three variants: (a) generic phrasing only, (b) anchored prompt with full canonical bundle, (c) anchored prompt with the bundle replaced by random domain-irrelevant jargon. If (b) is not noticeably better than (a) **and** (c) is not noticeably worse than both, the anchors are decorative — refine the bundle or drop the technique for this task.

## Interactions

| Stacks well with | Conflicts with | Order rule |
|---|---|---|
| `persona-clusters.md` | — | Apply lexicon **first**: anchors define the field neighborhood, then the lens constrains *which* anchors get foregrounded |
| `ordering-and-position.md` | — | Place `<domain_anchors>` and `<glossary>` near the **top** of the prompt, before the task block — they condition the entire residual stream |
| `formatting-as-signal.md` | — | XML tags around `<glossary>`, `<domain_anchors>`, `<term>` are load-bearing — these tag patterns appear in enough training data to be recognised structurally |
| `negative-space.md` | — | `<do_not_confuse_with>` inside glossary terms is a local instance of negative-space subtraction; reuse the same pattern for explicit anti-anchor lists |
| `references-and-evals.md` | — | The output contract / rubric should reuse the *exact* anchor strings as evaluation criteria; eval terms and prompt anchors must match token-for-token |
| `model-recon.md` | — | Recon output (target tokenizer, model size) tells you which anchors are high-friction — do recon **before** finalising the bundle |
| **Buzzword density** | ✗ | Adding `synergy` / `holistic` / `next-gen` to a canonical bundle pollutes it; remove all buzzword-shaped tokens before shipping |
| **Plain-language constraint** | ✗ | If the user explicitly asked for plain language, anchors fight the request; respect the user constraint |

**Order within a single prompt**: `<glossary>` → `<domain_anchors>` → `<lens_construction>` (if persona) → `<task>` → `<output_contract>` (with anchor strings reused). Glossary first because it locks meaning before any other block can use the terms.

## Failure modes

| Symptom | Diagnosis | Fix |
|---|---|---|
| Output uses anchor vocabulary but reaches generic conclusions | Anchors are decorative, not load-bearing; no glossary, no reuse in task / output contract | Define load-bearing terms locally; reuse the same anchor strings in the task block AND the output rubric |
| Output silently drifts to wrong adjacent meaning (e.g. answers a CSS question when prompt was about safety margins) | Polysemy collision; ambiguous word activated wrong field | Add `<disambiguation>` for the polysemous term; consider adding a `<field>` tag to the prompt as a whole |
| Tokenizer probe shows anchors fragmenting into 5+ pieces each | High-friction anchors; custom acronyms or mixed-case identifiers without merges | Define the term locally with the exact spelling repeated; or replace with a lower-friction synonym |
| Adding more anchors stops helping or starts hurting | Density too high; anchors crowd each other and dilute attention | Cap at 15; cut anchors that don't survive the procedurality test from §1.3 |
| The "canonical bundle" is mostly buzzwords | Source corpus was marketing material rather than authoritative practice | Restart §1.1 with textbooks / RFCs / standards / practitioner postmortems instead of vendor blogs |
| Plain-audience output reads as exclusionary or condescending | Lexicon technique applied where anti-trigger should have fired (general-audience writing) | Drop anchors; keep at most one defined load-bearing term per concept; respect the audience |
| Output fabricates plausible-sounding citations / standards / library APIs | Anchors named real-sounding artefacts that the model interpolated rather than retrieved | Pin to exact versions / URLs / RFC numbers in `<docs>` or `<references>`; require `documented` vs `inferred` labels |
| Model treats `Q4FY26 ARR` as separate concepts and reasons about Q4 in isolation | High-friction string fragmented into byte-level tokens with no merged representation | Define the compound term explicitly: `<term name="Q4FY26_ARR">Annualised recurring revenue measured at the close of fiscal Q4 of FY2026.</term>` and repeat the exact spelling |

## References

- [BPE for rare words](https://arxiv.org/abs/1508.07909) — original byte-pair encoding paper
- [SentencePiece](https://arxiv.org/abs/1808.06226) — language-agnostic subword tokenization
- [Hugging Face tokenizer summary](https://huggingface.co/docs/transformers/tokenizer_summary) — practical guide
- [OpenAI tiktoken](https://github.com/openai/tiktoken) — runnable probe library
- [Transformer Feed-Forward Layers Are Key-Value Memories](https://arxiv.org/abs/2012.14913) — Geva et al., the MLP K-V mechanism
- [Anthropic XML tags](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/use-xml-tags) — tag patterns Claude is trained on
- See also: `mechanistic-foundations.md` (the why), `persona-clusters.md` (apply after anchors), `ordering-and-position.md` (where to place glossary), `model-recon.md` (target tokenizer choice), `formatting-as-signal.md` (XML tag rationale)
