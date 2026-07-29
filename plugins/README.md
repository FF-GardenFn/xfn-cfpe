# Plugins

Two plugins packaging repo capabilities as slash commands, skills, and agents. Both are registered in the root [`.claude-plugin/marketplace.json`](../.claude-plugin/marketplace.json) at version 0.1.0. They are packaging, not new logic: each one wraps material that already exists elsewhere in the repo.

| Plugin | Wraps | Components |
|--------|-------|------------|
| [prompt-model/](./prompt-model/) | [`content/techniques/prompt-model/`](../content/techniques/prompt-model/) | 1 command, 1 skill |
| [training-insights/](./training-insights/) | [`training_insights/`](../training_insights/) | 4 commands, 2 agents, 2 skills |

## prompt-model

Mechanistic-aware prompt translation. Takes a raw request and returns expert-level prompt instructions intended for execution by a *different* model instance — the framing is a domain-expertise injector rather than a prompt polisher.

| File | Role |
|------|------|
| [commands/write-prompt.md](./prompt-model/commands/write-prompt.md) | `/write-prompt` — takes bare arguments, resolves the technique-file path prefix, and delegates to the skill |
| [skills/prompt-engineering/SKILL.md](./prompt-model/skills/prompt-engineering/SKILL.md) | Orchestration logic: two-phase model (intake/dispatch, then translation) with a fixed output contract |
| [.claude-plugin/plugin.json](./prompt-model/.claude-plugin/plugin.json) | Manifest |

Execution is a dispatch, not a single template. Phase A walks the trigger matrix in [`mechanistic-layer/preconditions-catalog.md`](../content/techniques/prompt-model/mechanistic-layer/preconditions-catalog.md) and runs a dissolution check; Phase B applies the `## Procedure` of every technique file the matrix pulled in, then scores the result against the composite rubric in [`validation-and-integration.md`](../content/techniques/prompt-model/mechanistic-layer/validation-and-integration.md). Output is a structured block (ROLE / OBJECTIVE / SPECIFICATIONS / ANTI-PATTERNS / REFERENCE FRAME / CONSTRAINTS / DELIVERABLE FORMAT / ASSUMPTIONS); the anti-patterns block is mandatory. Requests that trip the short-circuit conditions — single-question chat, pure execution, under ~500 tokens, throwaway — get plain prose and a note saying so.

This is the shipped form of the **prompt-maker** agent design tracked in [`agents/README.md`](../agents/README.md), whose spec lives in [`documentation/designs/template-writer/`](../documentation/designs/template-writer/). Note the divergence: the spec describes generating prompt *variants* for ablation and compression studies, while the plugin translates user intent into one prompt. The variant-generation half is still design only.

## training-insights

Command and agent surface for the autonomous training-experiment loop in [`training_insights/`](../training_insights/). One research direction goes in; a hypothesis is proposed, hyperparameters edited, training run, the checkpoint evaluated, and the result fed back into the next iteration. Every command shells out to the `training_insights` package, so the plugin requires that package and a working training setup — it does nothing standalone.

| Component | Role |
|-----------|------|
| [commands/experiment.md](./training-insights/commands/experiment.md) | `/experiment <direction>` — phase-gated pipeline; each phase has a checklist gate, with pre-flight before any run and a captured lesson after |
| [commands/status.md](./training-insights/commands/status.md) | `/status` — dashboard: best BPB, reward, Pareto frontier, family attribution, safety drift |
| [commands/analyze.md](./training-insights/commands/analyze.md) | `/analyze` — family attribution, Pareto frontier, safety drift, next-hypothesis suggestions across the full history |
| [commands/report.md](./training-insights/commands/report.md) | `/report [--step N \| --latest]` — per-checkpoint report compared against baseline and best |
| [agents/experiment-runner.md](./training-insights/agents/experiment-runner.md) | Executes one cycle: read insights, propose hypothesis, edit hyperparameters, commit, train, evaluate, log |
| [agents/insight-analyst.md](./training-insights/agents/insight-analyst.md) | Interpretation beyond the dashboards: family trends, why a direction keeps getting discarded, safety-drift causes |
| [skills/checkpoint-eval/](./training-insights/skills/checkpoint-eval/) | Scoring reference: quality (BPB improvement 60%, CORE 30%, MFU 10%), cost, safety, then sequential KEEP/DISCARD gates. Formulas in [references/scoring-formulas.md](./training-insights/skills/checkpoint-eval/references/scoring-formulas.md) |
| [skills/experiment-loop/](./training-insights/skills/experiment-loop/) | Loop architecture and its structural halts. References cover [autonomous-validation](./training-insights/skills/experiment-loop/references/autonomous-validation.md) and [lesson-capture](./training-insights/skills/experiment-loop/references/lesson-capture.md) |

Both skills describe the same composite reward used by [`src/ARENA/scoring/reward.py`](../src/ARENA/scoring/reward.py): `R = α·quality − β·cost − γ·safety`. The two surfaces score different objects — checkpoints here, conversations there — but share the shape.
