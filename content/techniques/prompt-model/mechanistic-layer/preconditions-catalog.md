# Preconditions Catalog — Flat Dispatch Table

The **machine-readable** dispatch table the skill consults first. Where
`OVERVIEW.md` has prose and a hierarchical matrix, this file is one flat
table per category, designed for an executor to walk top-to-bottom and
collect a list of files to consult.

For human reading, prefer `OVERVIEW.md`. For agent dispatch, prefer this file.

## Format

Each row is:

| Signal | Detection cue | Consult |
|---|---|---|

- **Signal**: a property of the request, draft, or target.
- **Detection cue**: how the skill (or human) recognises the signal — a
  regex, a keyword class, a metadata field, or an explicit user statement.
- **Consult**: the file or section to apply if the signal fires.

Multiple signals can fire on the same request. Consult **all** that match.
Deduplicate the resulting file list before applying.

## Category 1 — Target model and tokenization

| Signal | Detection cue | Consult |
|---|---|---|
| Target model is named | Explicit model name in spec OR plugin / skill config | `model-recon.md` (always first) |
| Tokenizer family known | `cl100k_base` / `o200k_base` / Claude / Llama / Mistral / Gemma | `model-recon.md` §2 + `tokenizer-aware-lexicon.md` §2 |
| Tokenizer family unknown | No model name; portable across families | `model-recon.md` §6 (conservative defaults) |
| Context window known and < 8K | Recon `<context_window>` < 8000 | `ordering-and-position.md` §6 (skip context index) |
| Context window known and > 32K | Recon `<context_window>` > 32000 | `ordering-and-position.md` §1, §6 (head-tail dup, context index) |
| Training cutoff predates required facts | Task references events / APIs / data after cutoff | `references-and-evals.md` Track A (mandatory) |
| Reasoning model | Recon `<reasoning_mode>` = reasoning / extended-thinking | `model-recon.md` §5 + `persona-clusters.md` (less CoT scaffolding) |
| Tool access available | Recon `<tool_access>` includes code-execution / browse | `references-and-evals.md` §B.2 (executable tests) |
| Channel hierarchy strict | Recon `<channel_hierarchy>` = strict | `ordering-and-position.md` §8 |
| Vision-capable target | Recon supports image input | `references-and-evals.md` §A.5 (screenshots first-class) |

## Category 2 — Domain and lexicon

| Signal | Detection cue | Consult |
|---|---|---|
| Technical domain with named standards | Keywords: RFC, ISO, NIST, IFRS, SOC 2, HIPAA, GDPR, CWE, CVE, WCAG, SLO | `tokenizer-aware-lexicon.md` |
| Software / engineering | Keywords: race condition, idempotency, schema migration, contract test | `tokenizer-aware-lexicon.md` (software bundle) |
| Application security | Keywords: threat model, attack surface, SSRF, authz, exploitability | `tokenizer-aware-lexicon.md` (security bundle) |
| Finance / investing | Keywords: ROIC, FCF, ARR, NRR, burn multiple, unit economics | `tokenizer-aware-lexicon.md` (venture / finance bundle) |
| Systems performance | Keywords: USE method, p99, queue depth, GC pause, lock contention | `tokenizer-aware-lexicon.md` (performance bundle) |
| Cross-domain synthesis (polysemy risk) | Two domain keyword classes co-occur | `tokenizer-aware-lexicon.md` §5 (disambiguation, high density) |
| Plain-audience writing requested | User says "explain to non-experts" / "plain language" | Skip lexicon technique; one defined term per concept |
| Vague verb + domain object | Regex: `(analyze\|review\|look at\|improve\|make better) .* (auth\|db\|cache\|...)` | `tokenizer-aware-lexicon.md` (anchor the verb) |
| Library / API mentioned | Recognisable package or framework name | `tokenizer-aware-lexicon.md` §6 (library anchors) |

## Category 3 — Judgment and lens

| Signal | Detection cue | Consult |
|---|---|---|
| Judgment / evaluation / design / critique task | Keywords: audit, evaluate, design, recommend, choose, compare | `persona-clusters.md` |
| Pure execution task | Keywords: translate, sort, format, convert | Skip lens technique |
| Trade-off across orthogonal axes | Two distinct optimisation targets in scope | `persona-clusters.md` §4 (stacked lens) |
| User wants stress-tested recommendation | "Steel-man", "challenge", "stress test" | `persona-clusters.md` §5 (persona loop with convergence rule) |
| Internal-workflow / no public figure fits | Domain is company-specific or no canonical practitioner | `persona-clusters.md` §6 (invented persona) |
| Output could be mistaken as endorsement | Public figure in financial / medical / legal advice | Avoid named lens; use invented persona |
| Small target model (≤7B params) | Recon `<model_type>` = small_fast | Skip named-lens technique; centroid is too diffuse |

## Category 4 — Position and structure

| Signal | Detection cue | Consult |
|---|---|---|
| Multi-block prompt | Has more than one of: role, task, context, examples, constraints | `ordering-and-position.md` + `formatting-as-signal.md` |
| Ranking / comparison of candidates | Multiple `<option>` blocks OR list of items to choose between | `ordering-and-position.md` §5 (option-order neutralisation) |
| Persona / lens used | `<lens>` or `<persona>` block present | `ordering-and-position.md` §4 (lens precedes task) |
| Long-context source bundle | > 5 source documents OR > 16K tokens of evidence | `ordering-and-position.md` §6 (context index) |
| Constraint and data far apart in draft | Detected by linter / inspection | `ordering-and-position.md` §7 (locality) |
| Prompt rendered > 80% of context window | Token count probe | `model-recon.md` §3 (compress) |

## Category 5 — Formatting

| Signal | Detection cue | Consult |
|---|---|---|
| Multiple semantic blocks | Multi-block signal from category 4 | `formatting-as-signal.md` |
| Output must follow predictable structure | JSON / schema / sectioned report / code+explanation | `formatting-as-signal.md` |
| Prompt mixes content types | Prose + code + tables + lists | `formatting-as-signal.md` |
| Prompt reused programmatically with substitution | Has `{{variable}}` placeholders | `formatting-as-signal.md` §6 (exact-string repetition + tag boundaries on variables) |
| Target = Anthropic | Recon `<provider>` = Anthropic | `formatting-as-signal.md` §1 (XML primary) |
| Target = OpenAI | Recon `<provider>` = OpenAI | `formatting-as-signal.md` §1 (Markdown primary) |
| Target = small / OSS / unknown | Recon = small_fast / unknown | `formatting-as-signal.md` §1 (Markdown + delimiters) |
| Single-question chat | Short turn, no structure required | Skip; plain prose |

## Category 6 — Negative space

| Signal | Detection cue | Consult |
|---|---|---|
| Known-bad centroid output predictable | Domain is consultancy / generic security / generic code review | `negative-space.md` |
| Revision after observed centroid-trap | User says "previous output was generic / vague / hedge-y" | `negative-space.md` |
| Named anti-patterns in domain | SOLID, OWASP, data leakage, allocation patterns | `negative-space.md` |
| Output evaluated against rubric with disqualifying failures | Rubric has explicit "fail if X" rules | `negative-space.md` (mirror rubric as bans) |
| Open-ended creative task | Keywords: poem, story, brainstorm, free-form | Skip negative-space technique |
| Vague positive instruction in draft | Many bans proposed for unclear positive | Fix positive first; bans cannot rescue |
| Hedge-laden prompter prose | `analyze`, `consider`, `look at`, `try to`, `maybe` in user request | `negative-space.md` §5 (strip prompter hedges) |

## Category 7 — References and evals

| Signal | Detection cue | Consult |
|---|---|---|
| Factual claims can be wrong | Empirical results / API behaviour / regulations / benchmarks | Track A |
| Training cutoff predates relevant facts | Already in category 1 | Track A (mandatory) |
| High-stakes; fluent-but-wrong materially worse than "don't know" | Recon stakes flag | Track A |
| Authoritative sources exist (RFCs, standards, peer-reviewed) | Domain has standards body | Track A |
| Output cited / audited downstream | Compliance / regulatory output | Track A (with reliability tiers) |
| Code generation | Task is "implement X", "build Y" | Track B (preregistered tests) |
| Strategic / analytical task | Task is "decide X", "recommend Y" | Track B (falsifiability) |
| Multiple revisions expected | User signals iteration | Track B (prevents goalpost-moving) |
| LLM-as-judge will score | Evaluation pipeline known | Track B §B.4 (surface judge rubric to generator) |
| Pure-opinion / creative task | "Write a poem about..." | Skip Track A |
| No objective success criterion | Subjective output | Skip Track B |
| Sources lower-quality than training memory | Misleading sources available | Skip Track A |
| Fast-moving API + stale official docs | API shipped major version since docs updated | Track A §A.2 (override rule) |

## Category 8 — Validation gate

| Signal | Detection cue | Consult |
|---|---|---|
| Production deployment | Going behind public API / customer-facing skill / billed agent | `validation-and-integration.md` (full gate) |
| Part of versioned skill or plugin | Regression risk | `validation-and-integration.md` |
| Regulated workflow | Medical / legal / financial / safety-critical | `validation-and-integration.md` (inter-rater κ > 0.8) |
| Invoked at scale (many runs/day) | High failure-rate compounding | `validation-and-integration.md` (full LLM judge + author) |
| Prompt revised after observed failure | Revision iteration | `validation-and-integration.md` (regression catalogue §6) |
| Author is also the only reviewer | Risk of motivated reasoning | `validation-and-integration.md` §3 (LLM judge primary, author secondary) |
| Throwaway / one-off prompt | Not deployed | Skip; lightweight gate (per-file structural checks only) |
| Pure-execution prompt with deterministic success | Single API wrapper | Skip; deterministic check suffices |

## Category 9 — Short-circuit anti-triggers

If **all** of these apply, skip the entire dispatch and write the prompt with
one or two paragraphs of plain prose:

| Signal |
|---|
| Single-question single-answer chat |
| Pure execution task (no judgment surface) |
| Prompt < 500 tokens |
| Throwaway / one-off, not deployed |
| Target model is small / specialised / weak instruction tuning |

The technique overhead would exceed the prompt's lifetime value.

## Dispatch contract

Given a request, the executor:

1. Walks categories 1–8 top-to-bottom.
2. Collects the union of consulted files.
3. Deduplicates (`tokenizer-aware-lexicon.md` may appear from multiple rows).
4. Adds `model-recon.md` first and `validation-and-integration.md` last (always).
5. Applies each file's `## Procedure` in dispatch order.
6. Reports the dispatch list to the user before drafting, so the user can
   override (drop a file or add one).

If category 9 fires (anti-triggers), report "short-circuit dispatch: plain
prose appropriate" and do not consult the technique files.

## See also

- `OVERVIEW.md` — the human-readable router (prose + hierarchical matrix).
- Each technique file's `## Trigger conditions` and `## Anti-trigger conditions`
  sections — the per-file canonical signal lists this catalog draws from.
