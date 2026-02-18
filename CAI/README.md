# Constitutional Kernel Hypothesis

Constitutional AI currently relies on models to both follow and enforce their own constitutions—a structural flaw analogous to letting an untrusted object implement its own reference monitor. The core insight is that constitutions work in governance (Locke) and in code (Python descriptors) precisely because enforcement is *external* to the governed entity: courts interpret law, runtimes enforce protocols. When a model self-critiques against a constitution, it can learn to produce constitutional-*looking* text without constitutional behavior—performative compliance rather than constraint satisfaction.

This experiment tests whether **external enforcement via a constitutional kernel** outperforms self-critique. The kernel is a wrapper that mediates all high-impact actions: it validates outputs against typed schemas, rejects ungrounded claims, and enforces invariants the model cannot bypass. The hypothesis is that "constitution-as-code" (kernel with teeth) beats "constitution-as-text" (self-critique prompts) on jailbreak resilience, tool misuse prevention, and recovery from violations—even when the underlying model is identical. If validated, this suggests alignment should shift from training models to internalize values toward designing constraint architectures that make misaligned behavior structurally impossible.

## Package Structure

```
CAI/
├── run_experiment.py       # CLI entry point
├── config.py               # Model configs, constants
├── models/                 # Data schemas
│   ├── schemas.py          # ToolCall, ValidationResult, TOOLS
│   ├── tasks.py            # TestTask
│   └── results.py          # TrialResult
├── kernel/                 # Constitutional enforcement
│   └── validator.py        # ConstitutionalKernel
├── classifier/             # Intent detection
│   └── intent.py           # IntentClassifier (Haiku-based)
├── experiment/             # Experiment logic
│   ├── runner.py           # ExperimentRunner
│   ├── prompts.py          # System prompts
│   └── task_suite.py       # TASKS
├── analysis/               # Metrics & visualization
│   └── metrics.py          # analyze_results, display_results
└── results/                # Output directory
```

## Usage

```bash
cd RL-O-CoV/CAI
python run_experiment.py --models claude-sonnet-4-20250514,claude-opus-4-20250514
```

## Key Design Decisions

1. **Intent Classifier**: Uses Haiku to distinguish compliance from refusal, preventing false positives where refusals mentioning dangerous patterns were incorrectly flagged.

2. **Consistent Scoring**: All conditions (baseline, CAI, kernel) are scored through the same kernel validation for apples-to-apples comparison.

3. **Recovery Loop**: When kernel blocks a violation, model gets a chance to self-correct. This tests whether external feedback improves behavior.

4. **Task Categories**: Benign (should succeed), Boundary (tempting but safe), Adversarial (should refuse/block).
