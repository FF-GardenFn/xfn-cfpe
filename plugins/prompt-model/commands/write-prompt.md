---
description: Translate raw user intent into expert-level prompt instructions for execution by another LLM. Bare arguments, no quotes needed.
argument-hint: <describe what you want a prompt for>
allowed-tools: [Read, Write, Bash, Edit]
---

# /write-prompt — Mechanistic-aware prompt translator

User's raw request: $ARGUMENTS

## What this command does

Translate the user's request above into expert-level prompt instructions optimized for execution by another LLM. The translation is the output of orchestrating the prompt-model directory's technique files (lexicon, persona, position, formatting, negative-space, references, validation).

This is **not** a prompt-improver. It is a domain-expertise injector. The user lacks the lexicon, structural patterns, and mechanistic awareness to navigate the receiving LLM into dense, expert-authored regions of training distribution. The skill bridges that gap.

## Skill to invoke

The orchestration logic lives in:

```
plugins/prompt-model/skills/prompt-engineering/SKILL.md
```

Read it now. Apply the two-phase model defined there.

## Technique-file directory

All technique files referenced by the SKILL.md live under:

```
content/techniques/prompt-model/
```

When the SKILL.md says "consult `mechanistic-layer/preconditions-catalog.md`", that resolves to:

```
content/techniques/prompt-model/mechanistic-layer/preconditions-catalog.md
```

## Execution contract

1. **Phase A — Intake & Dispatch.** Parse the user's request. Walk the trigger matrix in `mechanistic-layer/preconditions-catalog.md`. Run the dissolution check from the SKILL.md. Interrogate strategically (≤2 rounds, flip-test) only if necessary.

2. **Phase B — Translation.** For each technique file the trigger matrix pulled in, apply that file's `## Procedure`. Synthesize per the SKILL.md output contract (ROLE / OBJECTIVE / SPECIFICATIONS / ANTI-PATTERNS / REFERENCE FRAME / CONSTRAINTS / DELIVERABLE FORMAT / ASSUMPTIONS).

3. **Quality gate.** Score against the composite rubric in `mechanistic-layer/validation-and-integration.md` §2 and §4. Surface failed dimensions if below the use-class threshold.

4. **Return.** The translated instructions in the structured block defined by the SKILL.md output contract. Anti-patterns block is mandatory (≥3, per SKILL.md C3). Assumptions block is mandatory if any decisions were made on the user's behalf (per SKILL.md C6).

If the request short-circuits (Category 9 in `preconditions-catalog.md` — single-question chat, pure execution, prompt < 500 tokens, throwaway), report "short-circuit dispatch: plain prose appropriate" and write a one-or-two-paragraph plain-prose prompt instead of the full structured block.
