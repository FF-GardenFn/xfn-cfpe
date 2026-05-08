"""
Mid-Prompt Entropy Salt — split a prompt into N equal token-bands,
measure each band's lexical specificity, and flag low-entropy bands
in the middle that need anchors.

Why
---
The middle of a long prompt is an attention sink. Models attend
strongly to the first and last few hundred tokens; the 40-60% zone
gets glossed. You can recover mid-prompt salience by salting it with
high-entropy tokens — rare jargon, named entities, exact numbers,
versioned identifiers. Bands of generic filler ("make sure", "in
terms of", "best practices") are wasted real estate.

Mechanism (proxy)
-----------------
Per-band mean of log(token_id) under a BPE tokenizer. Late merges
(high IDs) correspond to rarer multi-character patterns; early merges
(low IDs) correspond to bytes and the most common short patterns. So
mean log(id) is a cheap, monotonic-ish proxy for lexical specificity.

A band whose mean is materially below the prompt-wide mean is filler.
Filler in the middle is the worst place for filler.

Caveat: this measures lexical density, not actual model attention. It
is a heuristic that correlates well with how anchored a chunk feels.

Usage
-----
    python mid_entropy.py "your prompt text..."
    python mid_entropy.py < prompt.txt
    python mid_entropy.py                # built-in example

Requires
--------
    pip install tiktoken
"""
from __future__ import annotations

import math
import sys
from typing import List

try:
    import tiktoken
except ImportError:
    sys.exit("install tiktoken: pip install tiktoken")

ENC = tiktoken.get_encoding("o200k_base")
N_BANDS = 5
MID_BANDS = {1, 2, 3}        # 0-indexed bands inside 20-80% are "middle"
LOW_RATIO = 0.92             # band_mean / prompt_mean below this = filler
HIGH_RATIO = 1.05            # above this = anchored


def mid_entropy(text: str, n_bands: int = N_BANDS) -> None:
    ids = ENC.encode(text)
    n = len(ids)
    if n < 50:
        print(f"prompt is short ({n} tokens) — entropy banding is noisy below ~50 tokens")
        return

    band_size = n // n_bands
    bands: List[List[int]] = [ids[i * band_size : (i + 1) * band_size] for i in range(n_bands)]
    bands[-1].extend(ids[n_bands * band_size :])  # tail any remainder into the last band

    log_ids_all = [math.log(max(t, 1)) for t in ids]
    prompt_mean = sum(log_ids_all) / n

    print(f"prompt: {n} tokens, {n_bands} bands of ~{band_size} tokens")
    print(f"entropy proxy = mean log(token_id); prompt mean = {prompt_mean:.2f}")
    print()
    print(f"  {'band':>4}  {'pos %':>9}  {'mean':>5}  {'ratio':>6}  flag")

    flagged_mid: List[int] = []
    for i, band in enumerate(bands):
        if not band:
            continue
        band_mean = sum(math.log(max(t, 1)) for t in band) / len(band)
        ratio = band_mean / prompt_mean
        pct_lo = 100 * i / n_bands
        pct_hi = 100 * (i + 1) / n_bands

        flag = ""
        is_mid = i in MID_BANDS
        if ratio < LOW_RATIO and is_mid:
            flag = "FILLER (mid)"
            flagged_mid.append(i)
        elif ratio < LOW_RATIO:
            flag = "filler"
        elif ratio > HIGH_RATIO:
            flag = "anchored"
        print(f"  {i:>4}  {pct_lo:>3.0f}-{pct_hi:>3.0f}%  {band_mean:>5.2f}  {ratio:>5.2f}x  {flag}")

    print()
    if flagged_mid:
        zones = ", ".join(
            f"{int(100 * i / n_bands)}-{int(100 * (i + 1) / n_bands)}%" for i in flagged_mid
        )
        print(
            f"verdict: low-entropy mid zones [{zones}] — compress, "
            "or salt with rare jargon / named entities / exact numbers / version tags."
        )
    else:
        print("verdict: middle bands carry their weight — ship.")


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
    mid_entropy(text)
