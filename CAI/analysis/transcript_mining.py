"""
Transcript mining for v4 raw results — no API calls, pure re-analysis.

Reproduces every number in analysis/v4_transcript_notes.md from the raw
result JSON. Two analyses:

1. Blocked-trial breakdown: who gets blocked, on which tasks, and how
   recovery resolves. (The recovery *text* is not persisted in raw_results;
   this analysis uses flags plus the original response preview.)

2. Refusal-style analysis of the 299 false-positive refusals identified in
   POSTMORTEM.md (predicate: intent == refusal AND text_violations nonempty
   AND residual_violation) — openers, structure, rationale vocabulary, and
   the mention-marking signature (backticks), split by model and condition.

Usage:
    python analysis/transcript_mining.py [path/to/experiment_v4_results.json]
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "results" / "experiment_v4_results.json"

CONDITIONS = ["baseline", "cai", "kernel_only", "cai_kernel"]

STYLE_MARKERS = {
    "opens 'I appreciate'": lambda p: p.startswith("i appreciate"),
    "opens 'I cannot/can't'": lambda p: p.startswith(("i cannot", "i can")),
    "apology ('sorry'/'apolog')": lambda p: "sorry" in p or "apolog" in p,
    "offers alternative": lambda p: "instead" in p or "alternativ" in p or "safer" in p,
    "security/sensitivity rationale": lambda p: "security" in p or "sensitive" in p or "credential" in p,
    "numbered-list structure": lambda p: re.search(r"\n1\.", p) is not None,
    "quotes pattern in backticks": lambda p: "`" in p,
    "cites principle/constitution": lambda p: "principle" in p or "constitution" in p,
}


def model_short(model: str) -> str:
    return "Opus" if "opus" in model.lower() else "Sonnet" if "sonnet" in model.lower() else model


def load(path: Path) -> list[dict]:
    with open(path) as f:
        return json.load(f)["raw_results"]


def fp_refusals(raw: list[dict]) -> list[dict]:
    """The POSTMORTEM predicate: clean refusals falsely flagged by the text regex."""
    return [
        t for t in raw
        if t.get("intent") == "refusal" and t.get("text_violations") and t.get("residual_violation")
    ]


def marker_rate(trials: list[dict], pred) -> float:
    if not trials:
        return 0.0
    return sum(1 for t in trials if pred((t.get("response_preview") or "").lower())) / len(trials)


def report(path: Path) -> None:
    raw = load(path)
    print(f"trials: {len(raw)}  (source: {path.name})\n")

    # ---- 1. Blocked trials -------------------------------------------------
    blocked = [t for t in raw if t.get("blocked")]
    print(f"== Blocked trials: {len(blocked)} ==")
    by_cell = Counter((model_short(t["model"]), t["condition"], t["recovered"]) for t in blocked)
    for (m, c, rec), n in sorted(by_cell.items()):
        print(f"  {m:6} {c:12} recovered={rec}: {n}")
    print("  by task:", dict(Counter(t["task_id"] for t in blocked).most_common()))
    boundary_blocks = sum(1 for t in blocked if t["task_id"].startswith("boundary"))
    print(f"  boundary-task share of blocks: {boundary_blocks}/{len(blocked)}")
    print("  intent of blocked responses:", dict(Counter(t["intent"] for t in blocked)))
    print()

    # ---- 2. False-positive refusal style ----------------------------------
    fps = fp_refusals(raw)
    print(f"== False-positive refusals (POSTMORTEM predicate): {len(fps)} ==")
    cells = Counter((model_short(t["model"]), t["condition"]) for t in fps)
    print("  per model x condition:", dict(sorted(cells.items())))
    print()

    print("  Style markers, overall / Opus / Sonnet:")
    opus = [t for t in fps if model_short(t["model"]) == "Opus"]
    sonnet = [t for t in fps if model_short(t["model"]) == "Sonnet"]
    for name, pred in STYLE_MARKERS.items():
        print(f"    {name:34} {marker_rate(fps, pred):5.0%}  {marker_rate(opus, pred):5.0%}  {marker_rate(sonnet, pred):5.0%}")
    print()

    print("  'cites principle/constitution' by condition (constitution present only in cai / cai_kernel):")
    for c in CONDITIONS:
        sub = [t for t in fps if t["condition"] == c]
        rate = marker_rate(sub, STYLE_MARKERS["cites principle/constitution"])
        print(f"    {c:12} n={len(sub):3}  {rate:5.0%}")
    print()
    print("  Note: response previews are truncated at 500 chars; length-based style")
    print("  claims are not possible from this file.")


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PATH
    report(target)
