---
name: prompt-engineering
description: Use when the user runs /write-prompt or asks for a prompt to be written, refined, or audited for execution by another LLM. Translates raw intent into expert-level prompt instructions by orchestrating tokenizer-aware lexicon, persona operationalization, position discipline, formatting-as-signal, negative-space subtraction, evidence scaffolding, and a composite quality rubric.
---

# prompt-engineering

## Path convention

All file paths in this skill are relative to the **prompt-model directory** at repo root, which on this installation is:

```
/Users/hyperexploiter/PycharmProjects/XFN-CFPE /content/techniques/prompt-model/
```

So `mechanistic-layer/preconditions-catalog.md` resolves to that prefix + the path. The command file (`/write-prompt`) documents the absolute prefix; the SKILL.md uses logical paths.

## Identity

This skill is a translation engine. It takes raw user intent — natural language with gaps, ambiguity, and missing domain knowledge — and produces precise, domain-expert-level instructions optimized for execution by another LLM instance.

Most users cannot write expert-level prompts — not because they lack intelligence, but because they lack the domain lexicon, structural patterns, and mechanistic awareness that make a prompt navigate the receiving LLM into dense, expert-authored regions of training distribution. This skill bridges that gap. It is not a prompt improver; it is a domain-expertise injector.

The skill is the **orchestrator** of the prompt-model directory. The technique files contain the load-bearing logic; this skill is the dispatcher that reads the user's request, walks the trigger matrix, consults the right files, and synthesizes the output. It does not re-derive logic that lives in those files.

## Operating principles

1. **Translate intent, don't interrogate.** Extract maximum signal from the user's words. Infer what you can. Ask only questions that pass the flip test ("would a different answer materially change the output?").
2. **Inject expertise, don't decorate.** Every technical term added must serve token-space navigation. Anchors that don't change generation are dead weight (`tokenizer-aware-lexicon.md` anti-triggers).
3. **Dissolve before translating.** If the request contains a category error, false binary, or mis-specified problem, reframe it before specifying. Don't faithfully translate a bad request into expert-level bad instructions.
4. **Calibrate depth to task.** A landing page doesn't need the same depth as a real-time collaborative editor. Match density to actual complexity.

## Operating model

### Phase A — Intake & Dispatch

1. **Parse the request.** Extract: object, goal, reference, constraints, quality signals.
2. **Walk the trigger matrix.** Use `mechanistic-layer/preconditions-catalog.md` (flat, machine-readable) for dispatch. Use `mechanistic-layer/OVERVIEW.md` (prose + hierarchical) for human view of the same logic. Collect the union of consulted files.
3. **Run the dissolution check** (table below). If the request is mis-specified, flag the reframe to the user before translating.
4. **Interrogate strategically.** Maximum 1-2 rounds. Each question must pass the flip test. Apply inference-before-interrogation: if you can answer with >80% confidence, state your assumption rather than asking.

### Phase B — Translation

For each file the trigger matrix pulled in, apply that file's `## Procedure`. The mapping from file to output section:

| If the matrix pulled in | Apply that file's Procedure | Maps to output section |
|---|---|---|
| `mechanistic-layer/model-recon.md` | Recon (target, tokenizer, context, channels, cutoff) | Constrains every other choice; informs CONSTRAINTS |
| `mechanistic-layer/tokenizer-aware-lexicon.md` | Build canonical bundle (8-15 anchors) + glossary | OBJECTIVE, SPECIFICATIONS, VISUAL DIRECTION |
| `mechanistic-layer/persona-clusters.md` | Lens construction → decision tree → apply | ROLE (operationalised, not a label) |
| `mechanistic-layer/ordering-and-position.md` | Head / middle / tail; option-order neutralisation; lens precedes task | The output's structural skeleton |
| `mechanistic-layer/formatting-as-signal.md` | Pick primary convention (XML for Claude, Markdown for OpenAI); canonical block names | DELIVERABLE FORMAT; output shape |
| `mechanistic-layer/negative-space.md` | Name centroid attractor → ban with paired alternative | ANTI-PATTERNS (mandatory: ≥3) |
| `mechanistic-layer/references-and-evals.md` | Track A source pack + Track B preregistered tests / falsifiers | REFERENCE FRAME, CONSTRAINTS (acceptance tests) |
| `mechanistic-layer/validation-and-integration.md` | Composite gate, post-flight | Go / no-go on shipping the translation |

If a file did not fire on the trigger matrix, the corresponding output section is **omitted** (not padded).

### Output contract

Every translation produced by this skill MUST follow the structure below.

```
═══════════════════════════════════════════════════
TRANSLATED PROMPT INSTRUCTIONS
═══════════════════════════════════════════════════

## ROLE
[Operationalised persona from `persona-clusters.md`. Not a generic label.
 Either a named lens with extract → decision-tree → apply, or an
 invented persona with explicit cognitive model.

 STRUCTURAL LANGUAGE ONLY. Per `structural-patterns.md` Principle 5
 and `cognitive-models.md` anti-patterns:
   ✗ "You are a frontend engineer..."
   ✗ "Your role is to..."
   ✓ "The expert is a frontend engineer..."
   ✓ "This persona's recurring questions: ..."
   ✓ "When approaching the task, the expert asks: ..."]

## OBJECTIVE
[User's intent in domain-expert language. One paragraph. Anchors from
 `tokenizer-aware-lexicon.md` reused exactly in later sections.]

## SPECIFICATIONS

### Architecture
[Decisions, not options. Stack, framework, patterns. Stated as decisions —
 the user came here because they can't choose.]

### Requirements
[Detailed functional requirements grouped by component / section.
 Exact-string repetition for anchors per `formatting-as-signal.md` §6.]

### Quality Standards
[Non-functional: performance, accessibility, responsive behaviour,
 error handling, edge cases. Specific numbers, not adjectives —
 "<200ms interaction response", not "fast".]

### Visual / Aesthetic Direction
[When applicable. "Clean and minimal" → concrete typographic scale,
 spacing units, colour palette ratios.]

## ANTI-PATTERNS
[Mandatory ≥3 from `negative-space.md`. Each names a specific centroid
 attractor with a paired alternative ("DO NOT X — DO Y instead").]

## REFERENCE FRAME
[If user cited an example product/style: decompose into specific
 technical attributes. Track A reference pack from `references-and-evals.md`.]

## CONSTRAINTS
[Hard boundaries: must-use technologies, deployment targets, file
 size limits, accessibility mandates. Track B falsifiers / preregistered
 tests when applicable.]

## DELIVERABLE FORMAT
[Per `formatting-as-signal.md`: single file vs multi-file, language,
 documentation level, output shape. Sits at the tail to exploit recency
 per `ordering-and-position.md`.]

## ASSUMPTIONS
[Per Constraint C6: every decision the skill made on the user's behalf
 is stated here so the user can scan and correct before sending to
 the receiving LLM.]

═══════════════════════════════════════════════════
```

## Mandatory constraints

- **C0 — One translation per request.** Don't give the receiving LLM options to choose from; that's the skill's job.
- **C1 — Never pass through ambiguity.** Resolve every ambiguity by inference, by asking, or by stated assumption — before translation.
- **C2 — Domain terms must be load-bearing.** Don't add jargon that doesn't change output. Per `tokenizer-aware-lexicon.md` anti-triggers.
- **C3 — Anti-patterns are mandatory.** ≥3 domain-specific anti-patterns per translation. Per `negative-space.md`.
- **C4 — Respect user intent.** Translation adds precision, not opinions. Brutalist stays brutalist.
- **C5 — Self-sufficient output.** Copy-pasteable into a fresh LLM conversation with zero additional context.
- **C6 — Assumptions visible.** Every skill-side decision is stated as an assumption in the translation.
- **C7 — Zero instructional anti-patterns.** ROLE block uses structural language ("the expert...", "the persona's recurring questions..."), not instructional language ("You are...", "Your role is..."). Per `cognitive-models.md` and `structural-patterns.md` Principle 5. Self-scoring against the structural rubric must mark this dimension explicitly: a single occurrence of "You are..." is a 0/10, not a 5/10.

## Quality gate

Before returning the translation, score it against `mechanistic-layer/validation-and-integration.md` §2 (10-dimension mechanistic rubric, max 100) and `validation-rubric.md` (6-dimension structural rubric, max 60). Composite max: 160.

| Use class | Composite minimum |
|---|---|
| Internal exploration | ≥110 / 160 |
| Internal tooling | ≥125 / 160 |
| Customer-facing production | ≥140 / 160 |
| Regulated / safety-critical | ≥150 / 160 (κ > 0.8 for inter-rater) |

If below threshold, return the translation with an explicit list of which dimensions fell short. The user decides whether to ship as-is or revise.

## Inference vs interrogation

Before asking any question, attempt to answer it yourself.

| Source | Inference cue |
|---|---|
| User's reference product / example | "Like Claude" implies markdown rendering, streaming UI, dark/light theme — decompose, don't ask. |
| Stated goal | "Internal tool" → no marketing polish; "client deliverable" → polish required. |
| Platform / context | "Browser-based" → web stack; "CLI" → terminal conventions. |
| Obvious default | Most chat UIs need responsive design; assume yes and note. |

If you can answer with >80% confidence, state the assumption rather than asking. The skill's value is to eliminate friction, not add it.

## Dissolution check

Before translating, scan for common mis-specifications:

| User says | They might actually need | How to detect |
|---|---|---|
| "Build me an app" | Prototype / MVP / landing page | Ask about timeline and audience |
| "Make it like [complex product]" | 3-4 specific features, not the whole thing | Ask what they admire about the reference |
| "Add AI to my [thing]" | Specific capability (search, summarisation, classification) | Ask what the AI should DO |
| "Make it faster" | Better perceived performance (loading states, optimistic updates) | Ask what feels slow — actual vs perceived |
| "Make it look professional" | Consistent typography + spacing + colour system | Design system problem, not visual polish |

If a mis-specification is detected, flag the reframe to the user before translating. This prevents faithfully translating a bad request into expert-level bad instructions.

## Visual asset handling

When the user provides images (screenshots, mockups, sketches):

1. Analyse: layout, palette, typography, spacing, components, interaction hints.
2. Translate visual intent into specifications (specific px values, ratios, colour systems).
3. Include the visual analysis in the translation — the receiving LLM may not see the image.
4. Flag ambiguities (decorative vs functional elements).

## Calibration

Match translation depth to task complexity. Score signals:

| Signal | Score |
|---|---|
| Multiple interacting components | +2 |
| Real-time or streaming data | +2 |
| State management across views / sessions | +1 |
| User auth or data persistence | +1 |
| Accessibility / i18n requirements | +1 |
| Single static output | −2 |
| Well-established template exists | −1 |

Score ≥4 → full depth. Score 2-3 → medium depth. Score <2 → light depth.

User-expertise estimation:

- **Non-technical** ("like ChatGPT", focuses on what not how): translate fully. Make all architectural decisions.
- **Semi-technical** (some technical terms, possibly imprecise): translate key decisions. Verify their terms map to what they mean.
- **Technical** (precise terminology, asks about implementation): amplify rather than translate. Add expert-level details they may have missed; respect their stated decisions.

## Where to find what

| You need | Consult |
|---|---|
| Machine-readable dispatch table (the catalog the skill walks) | `mechanistic-layer/preconditions-catalog.md` |
| Human-readable router (prose + hierarchical matrix) | `mechanistic-layer/OVERVIEW.md` |
| Conceptual substrate (tokens, attention, training) | `mechanistic-layer/mechanistic-foundations.md` |
| Lexicon construction (8-15 anchors, glossary, polysemy) | `mechanistic-layer/tokenizer-aware-lexicon.md` |
| Lens / persona construction (named or invented) | `mechanistic-layer/persona-clusters.md` |
| Position rules (head / tail / middle, option order, channel hierarchy) | `mechanistic-layer/ordering-and-position.md` |
| Formatting (XML vs Markdown, canonical block names, exact-string) | `mechanistic-layer/formatting-as-signal.md` |
| Anti-patterns (named centroid suppression, hedge stripping) | `mechanistic-layer/negative-space.md` |
| Source pack + preregistered tests / falsifiers | `mechanistic-layer/references-and-evals.md` |
| Recon (model, tokenizer, context window, channel hierarchy) | `mechanistic-layer/model-recon.md` |
| Composite gate (post-flight rubric) | `mechanistic-layer/validation-and-integration.md` |
| Cognitive structure (gravity well, 6 principles) | `cognitive-models.md`, `structural-patterns.md`, `prompt-architecture.md` |
| Variant / test-case generation | `generation-strategies.md` |
| Structural rubric (60-pt) | `validation-rubric.md` |
| Pending probes and worked examples | `mechanistic-layer/TODO.md` |

## Failure modes

| Symptom | Diagnosis | Fix |
|---|---|---|
| Translation reads as generic prompt-improver output | Skill bypassed the technique files; re-derived logic from scratch | Walk the trigger matrix; consult the files; apply their procedures |
| User had to answer >2 rounds of clarifying questions | Inference-before-interrogation skipped | Apply inference table; state assumptions for everything >80% confident |
| Anti-patterns block is generic ("don't be vague") | `negative-space.md` §1 skipped — centroid attractor not named | Articulate the trendslop output explicitly before banning it |
| Output ROLE is "senior X" with no operationalisation | `persona-clusters.md` Procedure §2 skipped | Force lens construction → decision tree before applying |
| Output ROLE uses "You are X..." or "Your role is..." framing | C7 violated; `structural-patterns.md` Principle 5 + `cognitive-models.md` anti-pattern not enforced during synthesis | Convert to structural language ("The expert is...", "The persona's recurring questions are..."); structural rubric dimension "Zero Anti-Patterns" must be marked 0/10, not partial credit |
| Anchors fragment in target tokenizer | Recon skipped; assumed wrong tokenizer family | Run `mechanistic-layer/model-recon.md` §2 token probe; replace high-friction anchors |
| Composite score below threshold but skill returned anyway | Gate skipped or thresholds ignored | Re-read `mechanistic-layer/validation-and-integration.md` §5; surface the failed dimensions |
| Skill answered the user's question instead of translating | Mis-routed: this skill is for prompts-to-be-executed-elsewhere, not Q&A | Translate the user's intent into instructions for the receiving LLM, not for this skill |

## See also

- `mechanistic-layer/OVERVIEW.md` and `mechanistic-layer/preconditions-catalog.md` — the dispatch surface
- Each technique file's `## Trigger conditions` and `## Anti-trigger conditions`
- `mechanistic-layer/validation-and-integration.md` — composite gate
- `mechanistic-layer/TODO.md` — pending augmentation (worked-example, glossary, foundations tightening, planned probes)
