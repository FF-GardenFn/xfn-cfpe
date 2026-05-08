# Target Model Recon

## What

**Identify the target model's tokenizer, context window, training cutoff, instruction-hierarchy support, structural-convention preferences, and tool-access affordances** — *and* derive the consequent prompt-design choices (which structural convention to use, which lexicon density, which probes apply, which fallbacks). Recon is not curiosity; it is a **gate** that constrains every downstream technique in this directory.

## Mechanism

Different model families behave differently because they were trained on different data with different objectives.

**Tokenizer differences are real and measurable.** `gpt-4` uses `cl100k_base`; `gpt-4o` uses `o200k_base`; Claude uses a proprietary tokenizer; Llama-3 uses its own SentencePiece variant; Gemma uses yet another. The same string `Q4FY26 ARR` produces 5 tokens in one tokenizer and 8 in another, with entirely different fragment shapes. A prompt anchored to one tokenizer's behaviour silently misfires on another.

**Training-data conventions differ.** Anthropic's documentation explicitly trains Claude on XML tags as semantic boundaries; OpenAI's instruction-following data leans on Markdown headings; smaller open-source models often have weaker instruction-tuning and ignore both. Picking the wrong convention for the target leaves load-bearing structure invisible to the model.

**Channel hierarchy is family-specific.** Some models honour a strict system > user > tool gradient (OpenAI, Anthropic post-training); some treat all channels equivalently (smaller open-source); some have no system message concept at all. Prompt-injection resistance, instruction-override behaviour, and constraint authority all depend on which model is receiving the prompt.

**Reasoning-mode and tool-use modes change everything.** Reasoning models (o1, o3, Claude with extended thinking) do better with terse goals + clear constraints + less step-by-step micromanagement; standard models do better with explicit chain-of-thought scaffolding. Agent models with tool access can run preregistered tests; non-agent models can only declare what they would have run.

**Training cutoff is binding.** Any fact more recent than the cutoff is unknowable from parametric memory. Not "less reliable" — *unknowable*. Source pack is mandatory for post-cutoff content.

These are differences measurable from public model cards and confirmable with a one-line probe (see Procedure §2). They are not exotic; they are the price of writing prompts that work across the model landscape.

## Trigger conditions

Apply recon when **any** are true:

- The prompt will be **deployed against a specific named model** (production system, API integration, agent definition).
- The prompt is **portable across model families** (a skill that may be invoked on Claude, GPT, or local Llama). Recon per target family before specialising.
- The task involves **post-cutoff facts** — recon's `training_cutoff` field decides whether sources are mandatory.
- The task uses **structured output** (JSON schema, function calls, XML, tool calls). Recon's `structured_output` field decides whether to use the native format or fall back to instructed format.
- The prompt is **long** (>8K tokens). Recon's `context_window` and `max_output` fields determine whether it fits and how to budget it.
- The prompt **adapts to multiple models in production** (e.g. routing to cheaper models for simple cases, frontier for complex). Per-model adaptation rules.

Apply with **higher rigour** (full token-probe sweep, channel-hierarchy test, structured-output capability check) when additionally:

- The prompt is part of a **production agent or skill** that runs at scale.
- The cost of model-specific failure is high (regulated output, billing-affecting code, customer-facing).

## Anti-trigger conditions

Do **not** invest in heavy recon when **any** are true:

- **One-off ad-hoc prompt** in a chat session against a known model. The recon overhead exceeds the prompt's lifetime value.
- **The model is hidden behind an abstraction layer** that re-formats prompts before sending (some agent frameworks). Recon the abstraction layer's contract, not the underlying model.
- **The model is unknown and unstable** (preview API that may change without notice). Pick conservative defaults (Markdown over XML, low lexicon density, high source-pack reliance) and let stability decide the rest.
- **Recon would over-specialise to one model when the target audience uses many.** A document recommending best practices for "AI engineers" should not be GPT-4-specific.

If anti-triggers fire, fall back to **conservative defaults** documented in Procedure §6.

## Procedure

### 1. Answer the recon questions before final design

```xml
<model_recon>
  <model_name>Exact model snapshot (e.g. claude-sonnet-4-6, gpt-5-2026-01-15, llama-3.1-70b)</model_name>
  <provider>OpenAI / Anthropic / Google / Meta / Mistral / local / hosted-OSS</provider>
  <tokenizer>Exact tokenizer name + how to count tokens (tiktoken / API endpoint / HF tokenizer.json)</tokenizer>
  <context_window>Total input + output limit (in tokens)</context_window>
  <max_output>Maximum response tokens</max_output>
  <training_cutoff>Cutoff date from official model card</training_cutoff>
  <reasoning_mode>standard / reasoning / extended-thinking / tool-agent</reasoning_mode>
  <structured_output>JSON schema / tool calls / function calls / XML / markdown / none</structured_output>
  <tool_access>browse / code-execution / file-system / API-calls / none</tool_access>
  <channel_hierarchy>strict (system > user > tool) / weak / none</channel_hierarchy>
  <eval_harness>How prompt changes will be measured (LLM judge / unit tests / human review)</eval_harness>
</model_recon>
```

Write this block at the top of the prompt's design doc, not the prompt itself. The prompt is the *output* of having answered these questions; the recon block is the input.

### 2. Token probe (runnable, with fallback)

For OpenAI-family models:

```python
import tiktoken

CANDIDATES = [
    "Q4FY26 ARR bridge",
    "pytest tests/billing/test_proration.py::test_midcycle_upgrade_rounds_to_cents",
    "IFRS 15 performance obligation",
    "Bill Gates technology platform lens",
    "your-internal-product-AcRoNyM",
]

for enc_name in ("cl100k_base", "o200k_base"):
    enc = tiktoken.get_encoding(enc_name)
    print(f"\n{enc_name}")
    for s in CANDIDATES:
        ids = enc.encode(s)
        print(f"  {len(ids):>3} tok  {s}  →  {[enc.decode([i]) for i in ids]}")
```

For Claude: use Anthropic's API token-counting endpoint (`messages.count_tokens`); there is no public client-side tokenizer for Claude — confirm token counts via API rather than estimate.

For Llama / Mistral / Gemma / other Hugging Face models:

```python
from transformers import AutoTokenizer
tok = AutoTokenizer.from_pretrained("meta-llama/Llama-3-70B-Instruct")
for s in CANDIDATES:
    ids = tok.encode(s, add_special_tokens=False)
    print(f"  {len(ids):>3} tok  {s}")
```

If no tokenizer access is available: use `len(string) / 4` as a baseline expectation for English; flag any string that comes out >1.5× that ratio as high-friction.

### 3. Token budget map (per target window)

```xml
<token_budget total="200000" target_model="claude-sonnet-4-6">
  <head max_pct="10">Task, anchors, glossary, lens construction, decision rules.</head>
  <body max_pct="75">Evidence, examples, source extracts, repo context.</body>
  <tail max_pct="15">Output contract, anti-patterns, tests, final constraints.</tail>
</token_budget>
```

For smaller windows (8K-32K), shift toward `20% / 60% / 20%`. The output contract must always sit close to the generation point — non-negotiable regardless of total size.

### 4. Consequent prompt-design choices (the "what to do once you've reconned" layer)

Recon is only useful if it **decides downstream choices**. The cross-tab below maps recon outputs to the technique-file knobs they constrain.

| Recon output | Consequence | Linked technique file |
|---|---|---|
| Provider = Anthropic | Use **XML tags** as primary structural convention | `formatting-as-signal.md` §1 |
| Provider = OpenAI | Use **Markdown headings** as primary; XML acceptable but not preferred | `formatting-as-signal.md` §1 |
| Provider = Llama / Mistral / smaller OSS | Use **Markdown + clear delimiters**; avoid heavy structure | `formatting-as-signal.md` §1 |
| Tokenizer = cl100k / o200k | Run the §2 tiktoken probe; flag high-friction anchors | `tokenizer-aware-lexicon.md` §2 |
| Tokenizer = Claude (no client tokenizer) | Use Anthropic API token counter; estimate conservatively (×1.1 buffer) | `tokenizer-aware-lexicon.md` §2 |
| Context window < 8K | Skip context index; use tight head/tail; cut examples to one | `ordering-and-position.md` §6 |
| Context window > 32K | Use context index pattern; head-tail duplicate the load-bearing constraint | `ordering-and-position.md` §2, §6 |
| Training cutoff < required-fact date | Source pack mandatory for post-cutoff content | `references-and-evals.md` Track A |
| Reasoning mode = on (o1, o3, Claude extended thinking) | **Less** chain-of-thought scaffolding; **more** terse goals + clear constraints | §5 below |
| Reasoning mode = standard | **More** explicit chain-of-thought scaffolding; show worked-example pattern | §5 below |
| Tool access = none | Preregistered tests can only be *declared*, not executed; switch to falsifiability for analysis | `references-and-evals.md` Track B |
| Tool access = code-execution | Preregistered tests CAN be run; require verbatim test output in response | `references-and-evals.md` §B.2 |
| Structured output = JSON schema | Prefer schema for extraction/classification over free-form output contract | §5 below |
| Structured output = none | Use XML/Markdown contract block in the prompt body | `formatting-as-signal.md` |
| Channel hierarchy = strict | Place load-bearing constraints in **system** message; wrap retrieved content explicitly | `ordering-and-position.md` §8 |
| Channel hierarchy = weak / none | All instructions share authority; explicit ordering in body matters more | `ordering-and-position.md` §8 |
| Vision support = yes | Treat screenshots as first-class evidence per Track A §A.5 | `references-and-evals.md` §A.5 |
| Cost per token high | Compress glossary, index sources, avoid head-tail duplication of the full constraint | this file §3 |
| Latency-sensitive | Avoid multi-pass O-CoV loops; single-pass with strong constraints | `persona-clusters.md` §5 |

### 5. Model-class adaptation rules

```xml
<adaptation_rules>
  <rule model_type="small_fast (≤7B params, edge inference)">
    Shorter context. Explicit output schema. Fewer or no lenses. Plain prose primary.
    XML tags ignored or weakly honoured — fall back to clear Markdown headings.
    Lexicon density LOW; one defined load-bearing term per concept.
  </rule>
  <rule model_type="frontier_standard (GPT-4 class, Claude Sonnet)">
    Rich evidence. Operationalised lenses. Preregistered tests. XML tags honoured (Anthropic) or Markdown
    headings (OpenAI). Explicit chain-of-thought scaffolding for non-trivial reasoning.
    Lexicon density MEDIUM-HIGH; full glossary for domain anchors.
  </rule>
  <rule model_type="frontier_reasoning (o1, o3, Claude extended thinking)">
    Terse goals + clear constraints + rich success criteria. Avoid micromanaged step-by-step.
    The model does the chain-of-thought internally; over-specifying steps degrades performance.
    Source pack mandatory for factual claims; falsifiability for analysis.
  </rule>
  <rule model_type="long_context (200K+ window)">
    Add context index at head. Head-tail duplicate the single load-bearing constraint.
    Per-section locality preserved. Run order-invariance probe before shipping.
  </rule>
  <rule model_type="code_agent (with tool access)">
    Provide repo paths. Preregister tests with executable commands. Workflow MUST forbid
    reporting success without showing test output. Diff constraints explicit.
  </rule>
  <rule model_type="multi_modal (vision/audio)">
    Screenshots as first-class evidence per refs §A.5. Audio transcripts as `<source>` blocks.
    Visual-layout claims must cite screenshot ID.
  </rule>
</adaptation_rules>
```

### 6. Conservative defaults (when target unknown)

If recon cannot be done (target model is variable, hidden, or unstable), pick defaults that work across the broadest range of models:

```
- Structural convention: Markdown headings (honoured by all major families)
- Lexicon density: medium (5-8 anchors with definitions)
- Source pack: present, with explicit `use_for` and reliability tiers
- Channel hierarchy: assume weak — put critical constraints in body with explicit imperatives
- Reasoning mode: assume standard — include explicit chain-of-thought scaffolding
- Tool access: assume none — declare tests but don't require execution
- Output format: explicit `<output_contract>` in body, even if model supports JSON schema
- Token budget: assume 32K context — use 20%/60%/20% head/body/tail
- Training cutoff: assume 1+ year ago — provide post-cutoff facts in source pack
```

These defaults are LCD; they will not maximise for any specific model but they will not silently break on any major one either.

### 7. Prompt-diff evaluation (after applying adaptations)

Every model-specific adaptation should be tested against the no-adaptation baseline.

```xml
<prompt_eval>
  <variant id="A">Conservative defaults baseline.</variant>
  <variant id="B">Model-specific adaptation per §4 cross-tab.</variant>
  <metrics>
    <metric>output specificity (anchor density)</metric>
    <metric>source-grounded claim rate</metric>
    <metric>order invariance score</metric>
    <metric>test pass / falsifier coverage</metric>
    <metric>hallucinated fact count</metric>
    <metric>token cost per response</metric>
    <metric>latency to first token</metric>
  </metrics>
</prompt_eval>
```

If (B) is not measurably better than (A), the adaptation is decorative — keep the simpler conservative version. Adaptations that don't pay off in the eval get removed.

## Validation

### Structural checks (the LLM can self-verify)

- [ ] Exact model snapshot identified (not just "GPT-4" — `gpt-4-2024-08-06` or similar).
- [ ] Tokenizer or proxy named with how to count tokens.
- [ ] Context window and max output limits known.
- [ ] Training cutoff stated; post-cutoff facts identified for source-pack inclusion.
- [ ] Reasoning mode, structured output, tool access fields all answered.
- [ ] Each recon output has a corresponding consequence applied (no orphan fields — if you reconned channel hierarchy but didn't act on it, the recon was decorative).
- [ ] Conservative defaults flagged when applied (so future readers know which choices weren't recon-driven).

### Probe-based validation

- **Token probe**: §2 runnable; verify load-bearing strings tokenize as expected on the target's tokenizer, not your assumed one.
- **Convention probe**: send a minimal prompt with the chosen structural convention and a structured task; check whether the model treats the convention as semantic boundaries or as inline content. If the latter, switch convention.
- **Channel-priority probe**: where applicable, send a prompt with conflicting instructions in system vs user channels; verify the model honours system. If not, channel hierarchy is weak — relocate critical constraints into body with explicit imperatives.
- **Token-budget probe**: render the final prompt; count tokens against `context_window − expected_output`. If tight (>80% of available), compress before shipping.

### Empirical sanity check

Run the prompt against the target model (or, if portable, against the 2–3 most likely targets). Measure: did the structural convention hold? Did anchors survive tokenization? Did the channel hierarchy override correctly? If any answer is no, adaptation needs another pass before production.

## Interactions

| Recon output gates | Linked technique file | Direction |
|---|---|---|
| Provider, structured output | `formatting-as-signal.md` (§1, §2) | Recon → formatting |
| Tokenizer | `tokenizer-aware-lexicon.md` (§2 tokenizer probe) | Recon → lexicon |
| Context window, max output | `ordering-and-position.md` (§6 context index, §1 head/tail sizing) | Recon → ordering |
| Training cutoff | `references-and-evals.md` (Track A: source pack mandatory for post-cutoff) | Recon → references |
| Tool access | `references-and-evals.md` (Track B: executable vs declarative tests) | Recon → evals |
| Channel hierarchy | `ordering-and-position.md` (§8 channel priority) | Recon → ordering |
| Reasoning mode | `persona-clusters.md` (lens depth), `formatting-as-signal.md` (CoT scaffolding) | Recon → persona, formatting |
| Vision support | `references-and-evals.md` (§A.5 screenshots) | Recon → references |

**Recon happens first.** Every other technique file's "Procedure" assumes recon outputs are available. If you skip recon, you are using conservative defaults whether you intended to or not.

**Do not duplicate work**: recon is a *one-time-per-target* investment. Once `claude-sonnet-4-6` is reconned for a given prompt design, the result is reusable across all prompts targeting that model. Cache the recon block.

## Failure modes

| Symptom | Diagnosis | Fix |
|---|---|---|
| Prompt works on Claude, fails on GPT-4 with same content | Structural convention specialised to one family without recon-driven adaptation | Re-recon for GPT-4 target; switch to Markdown primary; re-test |
| Anchor that worked locally fragments badly on the target tokenizer | Token probe skipped; assumed wrong tokenizer | Run §2 probe against actual target; replace high-friction anchors or define them locally |
| Output ignores post-cutoff facts and hallucinates outdated answers | Training cutoff field not consulted; source pack missing for post-cutoff content | Add source pack with current authoritative material; mark cutoff explicitly |
| Long prompt hits context window mid-task | Token budget map skipped; prompt rendered exceeded estimated size | Apply §3 budget map; compress glossary, index sources, cut redundant examples |
| Reasoning model performs worse with explicit step-by-step scaffolding | Treated reasoning model as standard; over-specified intermediate steps | Switch to terse goals + clear constraints per §5 reasoning_mode rule |
| Tool-equipped model declares "tests pass ✓" without running them | Recon's tool_access field said yes, but workflow didn't enforce execution | Add "do NOT report success without showing test output" rule per refs §B.2 |
| Prompt-injection via retrieved content overrides system constraint | Channel hierarchy field not consulted; constraint in user/body channel instead of system | Move load-bearing constraints to system channel; wrap retrieved content explicitly |
| Conservative defaults shipped to a frontier reasoning model | Recon never done; left LCD on the table for a model that could do more | Recon and re-adapt — frontier models reward density that LCD wastes |
| Recon block exists but no consequence applied | Recon was performed as ritual, not as input to design | For every reconned field, name the corresponding choice it informed; orphan fields = the field wasn't load-bearing, drop it |

## References

- [OpenAI models](https://platform.openai.com/docs/models) — current model list, context windows, knowledge cutoffs
- [OpenAI tiktoken](https://github.com/openai/tiktoken) — runnable tokenizer probe for OpenAI families
- [OpenAI tokenizer tool](https://platform.openai.com/tokenizer) — interactive probe
- [Anthropic models overview](https://docs.anthropic.com/en/docs/about-claude/models/overview) — Claude family specs
- [Anthropic context windows](https://docs.anthropic.com/en/docs/build-with-claude/context-windows) — context size guidance
- [Anthropic message counter](https://docs.anthropic.com/en/api/messages-count-tokens) — official token counting endpoint
- [Hugging Face tokenizer summary](https://huggingface.co/docs/transformers/tokenizer_summary) — local-model tokenizer recon
- [The Instruction Hierarchy](https://arxiv.org/abs/2404.13208) — channel-priority training and behaviour
- See also: `mechanistic-foundations.md` (the why), `tokenizer-aware-lexicon.md` (consumer of tokenizer recon), `formatting-as-signal.md` (consumer of provider recon), `ordering-and-position.md` (consumer of context-window and channel recon), `references-and-evals.md` (consumer of training-cutoff and tool-access recon), `persona-clusters.md` (consumer of reasoning-mode recon), `validation-and-integration.md` (final composite gate)
