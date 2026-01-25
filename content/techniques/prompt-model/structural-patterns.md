# Structural Patterns: The 6 Principles

These patterns create gravity wells in latent space—deep attractors that prevent model drift and ensure consistent, interpretable outputs.

---

## Principle 1: File Dependencies

Phases require artifacts from previous phases, creating gravity wells that prevent skipping.

```
Phase 1: Reconnaissance → produces context understanding
    ↓ (requires context)
Phase 2: Design → produces plan
    ↓ (requires plan)
Phase 3: Implementation → produces code
    ↓ (requires code)
Phase 4: Verification → produces confirmation
```

**Why it works**: Cannot proceed to Phase N without completing Phase N-1. Each dependency creates a mandatory checkpoint.

---

## Principle 2: Progressive Disclosure

Main file (~400-500 lines) navigates to supporting files for details. Load only what's needed.

**Structure**:
- Main AGENT.md: Overview + navigation (400-500 lines)
- Supporting files: Detailed patterns (100-300 lines each)
- One level deep (no nested references)

**Token economics**:
- Metadata: ~50 tokens per agent (always loaded)
- Main file: 200-2000 tokens (when triggered)
- Reference files: 0 tokens until accessed
- Scripts: 0 tokens (only output loaded)

---

## Principle 3: Gates/Checklists

Cannot proceed without completing current phase. Checklists enforce completeness.

```markdown
## Gate: Phase 1 Complete

- [ ] Existing patterns identified
- [ ] Conventions documented
- [ ] Dependencies mapped
- [ ] Assumptions explicit

**This gate is mandatory. Do not proceed until all items checked.**
```

**Why it works**: Mandatory checkpoints prevent corner-cutting and ensure thoroughness.

---

## Principle 4: Auto-Loading Patterns

Context triggers file navigation. Keywords automatically load relevant files.

```markdown
When analysis detects:
- Security vulnerability → Load security/vulnerabilities.md
- Performance issue → Load performance/optimization.md
- Architecture smell → Load patterns/component-design.md
```

**Why it works**: Progressive disclosure happens automatically based on context, not explicit instruction.

---

## Principle 5: Zero Instructional Anti-Patterns

No "You are...", "Your role is...", "You should...". Pure structural navigation.

**Anti-patterns to avoid**:
-  "You are a code reviewer"
-  "Your role is to analyze code"
- "You should follow these steps"

**Correct pattern**:
```markdown
## Phase 1: Security Analysis → security/

Detect vulnerabilities through static analysis.

**Process**:
- Run security scanners
- Check for injection patterns
- Validate authentication

**Output**: Security findings report

→ security/vulnerabilities.md
```

---

## Principle 6: Cognitive Model Embodiment

Structure embodies the mental process of the domain expert, not just lists of actions.

**Mental Process Embodied**:
1. Security-First Mindset (Phase 1) → "What could an attacker exploit?"
2. Quality Assurance (Phase 2) → "Will this be maintainable?"
3. Performance Awareness (Phase 3) → "Where are the bottlenecks?"

**Why it works**: Structure mirrors how the expert actually thinks, leveraging LLM's strength at simulation.

---

## Validation Rubric (Target: 60/60)

| Principle | Criteria | Points |
|-----------|----------|--------|
| File Dependencies | Strong phase dependencies, cannot skip | 10 |
| Progressive Disclosure | Main 400-500 lines, details in files | 10 |
| Gates/Checklists | Mandatory checkpoints, explicit blocking | 10 |
| Auto-Loading Patterns | Context-based file navigation | 10 |
| Zero Anti-Patterns | No "You are...", pure structural | 10 |
| Cognitive Model | Expert mental process embodied | 10 |

---

## Quick Checklist

- [ ] Each phase depends on previous phase's output
- [ ] Main file under 500 lines
- [ ] Reference files one level deep
- [ ] Gates between every phase
- [ ] No instructional language
- [ ] Expert thinking visible in structure
