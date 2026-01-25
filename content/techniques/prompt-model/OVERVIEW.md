# Template Writer: Design Foundation

The Template Writer generates high-quality prompt variants and test cases. This directory contains the design principles, cognitive models, and structural patterns that inform its generation strategies.

---

## Core Insight

Prompts don't instruct LLMs—they warp probability distributions in latent space. A rigorous prompt creates a gravity well that channels the model's trajectory toward desired outputs without fighting its probabilistic nature.

---

## What Template Writer Generates

**Prompt Variants**
- Ablations: Remove one component, measure impact
- Compressions: Minimize tokens, preserve intent
- Rephrases: Alternate framings of same instruction

**Test Cases**
- Domain transfers: Same structure, different topic
- Complexity scaling: Simple → nuanced versions
- Adversarial: Edge cases that stress prompts

**Evaluation Templates**
- Rubric-based scoring prompts
- Pairwise comparison prompts
- Multi-dimensional analysis frameworks

---

## Design Files

| File | Purpose |
|------|---------|
| `cognitive-models.md` | How agents think, not what they do |
| `structural-patterns.md` | The 6 principles that make prompts robust |
| `prompt-architecture.md` | Main prompt vs Skills, gravity wells |
| `generation-strategies.md` | How to create prompt variants |
| `validation-rubric.md` | How to validate generated prompts |

---

## Key Principle

"Claude is already very smart." Only add context Claude doesn't have. Challenge each piece with: Does Claude really need this explanation?