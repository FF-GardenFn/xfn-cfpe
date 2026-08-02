#!/usr/bin/env python3
"""Concept-erasure validation runner (exp_proposal.md, Phases 3–6).

Per concept pair and condition, the protocol is:

  1. extract v_T contrastively (concept_vectors)
  2. validate erasure:      recall probes should FAIL under erasure
  3. validate preservation: prerequisite probes should PASS under erasure
     (if not, sweep strength down / layer up per the proposal, then stop)
  4. measure derivation:    P-only problems under erasure

Conditions (proposal Phase 6):
  A  base model, no erasure      -> expected: succeeds by retrieval
  B  base model + erasure        -> expected: fails (no retrieval, no derivation)
  C  RL-O-CoV adapter + erasure  -> the hypothesis test: derivation from P alone

Requires torch + transformers + a GPU (and, for condition C, a trained LoRA
adapter directory from RL_O_CoV_Training_V5). This machine has none of that:
the module is import-safe without torch and `--dry-run` exercises everything
that does not need a model (fixture integrity, grading, erasure arithmetic).

Usage:
  python3 run_erasure_validation.py --dry-run
  python3 run_erasure_validation.py --model Qwen/Qwen2-7B-Instruct \
      --conditions A,B [--adapter path/to/adapter --conditions A,B,C] \
      [--strength 3.0] [--mode steer] [--out results/erasure_validation.jsonl]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from interp.concept_vectors import (  # noqa: E402
    ConceptVectorSpec, default_target_prompts, extract_concept_vector, two_thirds_layer,
)
from interp.erasure import concept_erasure, self_test as erasure_self_test  # noqa: E402
from interp.probes import CONCEPT_PAIRS, grade, self_test as probes_self_test  # noqa: E402

CONTROL_CONCEPTS = [
    "the water cycle", "supply and demand", "photosynthesis", "plate tectonics",
]


def dry_run() -> int:
    e = erasure_self_test()
    p = probes_self_test()
    n_probes = sum(
        len(c.recall_probes) + len(c.preservation_probes) + len(c.derivation_probes)
        for c in CONCEPT_PAIRS
    )
    print(f"erasure arithmetic: {e}/5 · probes/grading: {p}/7 · "
          f"{len(CONCEPT_PAIRS)} concept pairs, {n_probes} probes total")
    return 0 if (e == 5 and p == 7) else 1


def generate(model, tokenizer, prompt: str, max_new_tokens: int = 512) -> str:
    import torch
    messages = [{"role": "user", "content": prompt}]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt").to(next(model.parameters()).device)
    with torch.no_grad():
        out = model.generate(
            **inputs, max_new_tokens=max_new_tokens, do_sample=False,
            pad_token_id=tokenizer.pad_token_id,
        )
    return tokenizer.decode(out[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)


def run_condition(model, tokenizer, condition: str, layer_idx: int, strength: float, mode: str, out_path: Path):
    """One condition over all pairs; appends one JSONL row per probe."""
    rows = []
    for pair in CONCEPT_PAIRS:
        vector = None
        if condition in ("B", "C"):
            spec = ConceptVectorSpec(
                concept_name=pair.target_concept,
                target_prompts=default_target_prompts(pair.target_concept),
                control_prompts=[p for c in CONTROL_CONCEPTS for p in default_target_prompts(c)],
                layer_idx=layer_idx,
            )
            vector = extract_concept_vector(model, tokenizer, spec)

        def _ask(probe, phase):
            if vector is not None:
                with concept_erasure(model, vector, layer_idx, strength=strength, mode=mode):
                    response = generate(model, tokenizer, probe.prompt)
            else:
                response = generate(model, tokenizer, probe.prompt)
            g = grade(probe, response)
            rows.append({
                "ts": datetime.now(timezone.utc).isoformat(),
                "condition": condition, "pair": pair.name, "phase": phase,
                "prompt": probe.prompt, "response": response,
                "grading": g, "layer_idx": layer_idx, "strength": strength, "mode": mode,
            })

        for probe in pair.recall_probes:
            _ask(probe, "erasure_validation")
        for probe in pair.preservation_probes:
            _ask(probe, "prerequisite_preservation")
        for probe in pair.derivation_probes:
            _ask(probe, "derivation")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "a") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="fixture/arithmetic checks only; no model")
    ap.add_argument("--model", default="Qwen/Qwen2-7B-Instruct")
    ap.add_argument("--adapter", default=None, help="LoRA adapter dir (condition C)")
    ap.add_argument("--conditions", default="A,B", help="comma-set of A,B,C")
    ap.add_argument("--layer", type=int, default=None, help="default: ~2/3 depth")
    ap.add_argument("--strength", type=float, default=3.0)
    ap.add_argument("--mode", choices=["steer", "project"], default="steer")
    ap.add_argument("--out", default="results/erasure_validation.jsonl")
    args = ap.parse_args()

    if args.dry_run:
        return dry_run()

    try:
        import torch  # noqa: F401
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError:
        print("torch/transformers unavailable — only --dry-run works here", file=sys.stderr)
        return 2

    conditions = [c.strip().upper() for c in args.conditions.split(",") if c.strip()]
    if "C" in conditions and not args.adapter:
        print("condition C requires --adapter", file=sys.stderr)
        return 2

    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        args.model, device_map="auto", trust_remote_code=True
    )
    layer_idx = args.layer if args.layer is not None else two_thirds_layer(model)
    out_path = Path(__file__).resolve().parent / args.out

    for condition in conditions:
        if condition == "C":
            from peft import PeftModel
            model = PeftModel.from_pretrained(model, args.adapter)
        n = len(run_condition(model, tokenizer, condition, layer_idx, args.strength, args.mode, out_path))
        print(f"condition {condition}: {n} probe rows -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
