"""
Position Pulse — score each sentence in a draft prompt by anchor-density
(token rarity proxy) and report where the top-leverage sentences sit.

Why
---
Lost-in-the-middle is the rule, not the exception. A model attends most
strongly to the first and last few hundred tokens; sentences buried at
35-65% of the prompt get a smaller share of the attention budget. If
your highest-leverage sentence sits in that zone, move it.

Mechanism (proxy)
-----------------
Token IDs in BPE tokenizers are assigned in merge order. The lowest IDs
are byte-level fallbacks and the most common merges (function words,
short common patterns). The highest IDs are the latest, rarest merges —
jargon, named entities, multi-character technical terms. So the *mean
token ID over a sentence* is a cheap proxy for lexical specificity, and
the *count of tokens above the prompt-wide 75th percentile* is a cheap
proxy for "anchor density".

This is a heuristic, not a measurement of the model's actual attention.
But it correlates well in practice, costs nothing to run, and gives a
concrete number you can act on.

Usage
-----
    python position_pulse.py "your prompt text..."
    python position_pulse.py < prompt.txt
    python position_pulse.py                 # built-in example

Requires
--------
    pip install tiktoken
"""
from __future__ import annotations

import re
import sys
from typing import List, Tuple

try:
    import tiktoken
except ImportError:
    sys.exit("install tiktoken: pip install tiktoken")

ENC = tiktoken.get_encoding("o200k_base")  # gpt-4o family


def split_sentences(text: str) -> List[str]:
    """Cheap sentence segmentation — tolerates abbreviations badly but
    fine for prompt-sized text."""
    parts = re.split(r"(?<=[.!?])\s+|\n{2,}", text.strip())
    return [p.strip() for p in parts if p.strip()]


def position_pulse(text: str, top_k: int = 3, mid_lo: float = 35.0, mid_hi: float = 65.0) -> None:
    sents = split_sentences(text)
    if len(sents) < 3:
        print(f"too few sentences ({len(sents)}); position is moot")
        return

    all_ids = ENC.encode(text)
    total = len(all_ids)
    sorted_ids = sorted(all_ids)
    threshold = sorted_ids[int(0.80 * len(sorted_ids))]  # 80th pct = tighter anchor bar

    rows = []  # (leverage, density, anchor_count, mid_pct, sent, n_tok)
    cum = 0
    for s in sents:
        ids = ENC.encode(s)
        n = len(ids)
        if n == 0:
            continue
        anchors = sum(1 for tid in ids if tid >= threshold)
        density = anchors / n
        # leverage = anchor_count * density = anchor_count^2 / n_tok
        # rewards long sentences with many anchors; penalises short tag-lines
        # whose 1-2 anchor-class words inflate raw density.
        leverage = anchors * density
        mid_pct = 100.0 * (cum + n / 2) / total
        rows.append((leverage, density, anchors, mid_pct, s, n))
        cum += n

    rows.sort(key=lambda r: r[0], reverse=True)
    top = rows[:top_k]

    print(f"prompt: {len(sents)} sentences, {total} tokens")
    print(f"anchor threshold (80th-pct token id): {threshold}")
    print()
    print(f"top-{top_k} leverage sentences (score = anchor_count x density):")
    for leverage, density, anchors, pct, s, _ in top:
        bucket = "EDGE" if pct < 20 or pct > 80 else "MID " if mid_lo <= pct <= mid_hi else "ok  "
        snippet = (s[:78] + "...") if len(s) > 78 else s
        print(f"  [{bucket}] {pct:5.1f}%  score={leverage:5.2f}  anchors={anchors:>2}  density={density:.2f}  {snippet}")

    mid_count = sum(1 for r in top if mid_lo <= r[3] <= mid_hi)
    print()
    if mid_count >= 2:
        print(f"verdict: {mid_count}/{top_k} top-leverage sentences in the {mid_lo:.0f}-{mid_hi:.0f}% lost-in-middle zone — move to top or last paragraph.")
    elif mid_count == 1:
        print(f"verdict: 1/{top_k} top-leverage sentence in the lost-in-middle zone — consider moving.")
    else:
        print(f"verdict: leverage is well-positioned at the edges — ship.")


EXAMPLE = (
    "You are a senior software engineer. I want you to look at the following code and provide "
    "some thoughts on how it could be improved. The code handles user authentication for a web "
    "application that we are building. We want it to be production-ready and follow best practices "
    "in terms of security, maintainability, and performance. Specifically, please examine whether "
    "the rate-limiting on the login endpoint is sufficient to prevent credential-stuffing attacks "
    "under realistic adversarial pressure with idempotency guarantees. Also check error handling. "
    "The code is below. Make sure your suggestions are actionable and explain your reasoning. "
    "Thank you very much."
)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
    elif not sys.stdin.isatty():
        text = sys.stdin.read().strip()
    else:
        text = ""
    if not text:
        text = EXAMPLE
        print("(no input — using built-in example)\n")
    position_pulse(text)
