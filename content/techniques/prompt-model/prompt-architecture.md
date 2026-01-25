# Prompt Architecture

How to structure prompts that channel LLM behavior through architecture rather than verbose instruction.

---

## The Gravity Well Model

Prompts create gravity wells in latent space:
- **Weak prompts** = shallow wells (model drifts easily)
- **Strong structure** = deep wells (model stays in region)
- **Principles** define the CENTER of each well
- **Algorithms** define the SHAPE and DEPTH

Alternative metaphors:
- **Circuit board**: Prompt channels current (LLM output) productively
- **Train rails**: Rails don't tell train how to move—they channel where energy goes

---

## The Fusion Approach: Principles + Algorithms

**Principles alone** (weak gravity well):
```
"Write clean, testable code."
```
Too vague. Model guesses what "clean" means.

**Algorithms alone** (fights model nature):
```
"1. Initialize test_count = 0
 2. For each function: a. Write test b. Increment count"
```
Too rigid. LLMs don't execute pseudocode.

**Fusion** (deep gravity well):
```
PRINCIPLE: "A senior engineer writes tests FIRST to verify understanding"

METHODOLOGY:
1. Before writing implementation, ask: "What should this do?"
2. Write a test that expresses that expectation
3. Run the test (should fail)
4. Write minimal code to make it pass
5. Verify the test passes

This is RED → GREEN → REFACTOR discipline.
```

Why fusion works:
- Principle defines optimization target
- Methodology provides structure (attractors in latent space)
- Framed as simulation ("senior engineer thinks this way")
- Model can execute (it's a pattern, not pseudocode)
- Creates checkpoints (can't skip to implementation)

---

## Main Prompt vs Skills Separation

**Main Agent Prompt** (always active):
- Identity: Who is this agent?
- Cognitive Model: How do they think?
- Methodology: What are their phases?
- Principles: What do they optimize for?
- Size: Concise enough to shape ALL generation

**Skills** (consulted on-demand):
- WHEN to use each tool (triggers)
- HOW to use tools effectively (patterns)
- WHAT patterns work (codebase navigation)
- WHY certain approaches work better

**Key difference**: Main prompt always active; Skills consulted as needed.

---

## Degrees of Freedom

Match specificity to task fragility:

**High Freedom** (text-based instructions):
- Multiple approaches valid
- Decisions depend on context
- Example: Code review process

**Medium Freedom** (templates with parameters):
- Preferred pattern exists
- Some variation acceptable
- Example: Report generation

**Low Freedom** (exact scripts):
- Operations are fragile
- Consistency critical
- Example: Database migrations

**Bridge analogy**: Narrow bridge with cliffs = low freedom (one safe path). Open field = high freedom (many paths work).

---

## Token Economics

Context window is a public good. Progressive disclosure optimizes:

```
Without progressive disclosure:
10 agents × 2000 tokens = 20,000 tokens always loaded

With progressive disclosure:
10 agents × 50 tokens metadata = 500 tokens always
1 triggered agent × 2000 tokens = 2,000 tokens when needed
Total: 2,500 tokens (87% reduction)
```

---

## Architecture Checklist

- [ ] Main prompt under 500 lines
- [ ] Cognitive model (how expert thinks) explicit
- [ ] Phase-based methodology with checkpoints
- [ ] Principles stated clearly
- [ ] Tool usage at high level (WHEN, not HOW)
- [ ] Details in reference files
- [ ] One level deep references
- [ ] Framed as simulation, not instruction
