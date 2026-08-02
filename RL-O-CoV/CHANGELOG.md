# RL-O-CoV — Changelog

One entry per version. The training files themselves are kept immutable once a
version has been run: each is the artifact of its own run, and fixes land in
the next version instead.

## V1 — `time_to_put_the_pump_on_claude_v0.0.1.py` (2026-01)

The original prototype: LoRA rank 128, LR 3e-5, GSM8K only, no warmup, no
quantization. Accuracy collapsed 88% → 0% inside 200 steps — catastrophic
forgetting. Kept as the cautionary artifact; every later version's
hyperparameter conservatism traces back to this run.

## V2 — `RL_O_CoV_Training_V2.py` (2026-02)

The conservative rehabilitation: LoRA 32, LR 5e-6, 4-bit quantization,
100-step warmup, a wider Goldilocks zone [0.15, 0.85], and real similarity
logging. Training was stable and the baseline was preserved. Established the
reward decomposition (correctness / structure / resonance) that every later
version refines.

## V3 — `RL_O_CoV_Training_V3.py` / `.ipynb` (2026-02-21)

An iteration on V2, superseded after an audit found two disqualifying defects:
hard-label ground-truth and comparator errors (some expected answers were
simply wrong), and reward-judge contamination — the similarity judge shared
the adapter being trained, so training moved the ruler that measured it. Kept
for lineage; its numbers should not be cited.

## V4 — `RL_O_CoV_Training_V4.py` / `.ipynb` (2026-06-13)

The corrected relaunch: frozen, adapter-disabled reward judge with
mean-centered hidden-state geometry; corrected labels with stricter
math-equivalence checks; shaped resonance (Gaussian targets on H1/H2
distinctness and oscillation engagement, replacing the binary zone); K-sample
leave-one-out group baselines; deterministic LoRA forwards; true LR warmup;
greedy held-out evaluation isolated from training reward statistics. Launched
on a Colab A100 (Qwen2-7B-Instruct); the archived log covers configuration,
initial evaluation (28% accuracy, 100% structure rate on the held-out set),
and early steps — the full run's final metrics were not preserved. The file
pair is unchanged since launch: it is the run artifact.

## V5 — `RL_O_CoV_Training_V5.py` / `.ipynb` (2026-08-02, current — not yet run)

Folds in every finding from the 2026-07-30 post-launch code review, none of
which was visible in V4's initial-eval numbers but several of which would have
biased a full run:

- Phase-boundary detection matches marker *forms* (`[X]`, `**X**`, line-start
  `X:`, headings) instead of bare substrings — the word "answer" in prose no
  longer truncates a section or scores a present phase as missing.
- Final-answer extraction takes the *last* `Answer:` line, not the first.
- `evaluate()` no longer reseeds RNG at all: V4 restored only the CPU state
  while reseeding CUDA, so every eval silently reset the training sampling
  stream.
- Sampling temperature moved to config; history rows stay step-aligned (NaN
  fill); answer normalization handles "The answer is: …" and `$…$.` endings.
- Synthetic hard pool doubled to 20 problems, every label re-derived by hand
  before inclusion (wrong labels were V3's cardinal sin).
- Pure-text parsing moved to module level and covered by a 22-case
  stdlib-only self-test that runs without torch.
