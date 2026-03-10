"""
Training output parser — converts quick_train.py / base_train.py stdout into
TrainingMetrics so the evaluator can act on real numbers immediately.

The training script prints a summary block at the end:

    ---
    val_bpb:          0.997900
    training_seconds: 300.1
    total_seconds:    325.9
    peak_vram_mb:     45060.2
    mfu_percent:      39.80
    total_tokens_M:   499.6
    num_steps:        953
    num_params_M:     50.3
    depth:            8

This module parses that block (from a file path, string, or list of lines)
into a TrainingMetrics dataclass, with crash/OOM detection built in.

Usage:
    from training_insights.evaluation.parser import parse_training_output

    # from a log file
    metrics, status = parse_training_output("run.log")

    # from captured stdout string
    metrics, status = parse_training_output(output_str)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Union

from training_insights.evaluation.checkpoint_eval import TrainingMetrics


class RunStatus(str, Enum):
    """Outcome of a training run as inferred from its output."""
    SUCCESS = "success"
    CRASH = "crash"       # Python exception / FAIL signal
    OOM = "oom"           # CUDA out-of-memory
    TIMEOUT = "timeout"   # exceeded time budget (> 10 min)
    DIVERGE = "diverge"   # loss > 100, explicit FAIL exit
    EMPTY = "empty"       # log file was empty or not found


@dataclass
class ParseResult:
    """Parsed output from a single training run."""
    metrics: TrainingMetrics
    status: RunStatus
    raw_summary: dict[str, float]
    num_steps: int = 0
    num_params_M: float = 0.0
    depth: int = 0
    total_seconds: float = 0.0
    crash_hint: str = ""   # last 3 lines of traceback if crash


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_KEY_MAP: dict[str, str] = {
    "val_bpb":          "val_bpb",
    "training_seconds": "wall_time_sec",
    "peak_vram_mb":     "_vram_mb",      # converted to GB below
    "mfu_percent":      "mfu_pct",
    "total_tokens_M":   "_tokens_M",     # converted to int below
    "total_seconds":    "_total_sec",
    "num_steps":        "_num_steps",
    "num_params_M":     "_num_params_M",
    "depth":            "_depth",
}

_FLOAT_RE = re.compile(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")


def _extract_summary_block(lines: list[str]) -> dict[str, float]:
    """Extract key: value pairs from the --- summary block."""
    in_block = False
    values: dict[str, float] = {}
    for line in lines:
        stripped = line.strip()
        if stripped == "---":
            in_block = True
            continue
        if in_block:
            if ":" in stripped:
                key, _, rest = stripped.partition(":")
                key = key.strip()
                m = _FLOAT_RE.search(rest)
                if m and key in _KEY_MAP:
                    values[key] = float(m.group())
            elif stripped == "" and values:
                break   # blank line after block ends it
    return values


def _detect_crash(text: str, lines: list[str]) -> tuple[bool, str]:
    """Return (is_crash, hint) based on common failure patterns."""
    text_lower = text.lower()
    if "out of memory" in text_lower or "cuda error" in text_lower:
        return True, "OOM"
    if re.search(r"^FAIL\s*$", text, re.MULTILINE):
        return True, "FAIL signal (loss explosion)"
    # Python traceback
    for i, line in enumerate(lines):
        if "Traceback (most recent call last)" in line:
            tail = lines[max(0, i):i + 5]
            return True, " | ".join(l.strip() for l in tail if l.strip())
    return False, ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_training_output(
    source: Union[str, Path],
) -> ParseResult:
    """Parse training stdout from a file path or a raw string.

    Parameters
    ----------
    source : str | Path
        Either a filesystem path to a log file (e.g. ``run.log``)
        or a raw stdout string captured from the training process.

    Returns
    -------
    ParseResult
        Structured result with TrainingMetrics + run status + diagnostics.
    """
    # Resolve source to text + lines
    if isinstance(source, Path) or (isinstance(source, str) and "\n" not in source):
        p = Path(source)
        if not p.exists() or p.stat().st_size == 0:
            return ParseResult(
                metrics=TrainingMetrics(),
                status=RunStatus.EMPTY,
                raw_summary={},
                crash_hint=f"log file not found or empty: {source}",
            )
        text = p.read_text(errors="replace")
    else:
        text = source

    lines = text.splitlines()

    # Crash detection before anything else
    is_crash, crash_hint = _detect_crash(text, lines)
    summary = _extract_summary_block(lines)

    # If no summary block and no crash → treat as crash
    if not summary and not is_crash:
        is_crash = True
        crash_hint = "no summary block found in output"

    if is_crash:
        status = RunStatus.OOM if "OOM" in crash_hint else RunStatus.CRASH
        return ParseResult(
            metrics=TrainingMetrics(val_bpb=0.0),
            status=status,
            raw_summary=summary,
            crash_hint=crash_hint,
        )

    # Build TrainingMetrics from summary
    val_bpb       = summary.get("val_bpb", 0.0)
    wall_time_sec = summary.get("training_seconds", 0.0)
    vram_mb       = summary.get("peak_vram_mb", 0.0)
    mfu_pct       = summary.get("mfu_percent", 0.0)
    tokens_M      = summary.get("total_tokens_M", 0.0)
    total_sec     = summary.get("total_seconds", 0.0)
    num_steps     = int(summary.get("num_steps", 0))
    num_params_M  = summary.get("num_params_M", 0.0)
    depth         = int(summary.get("depth", 0))

    # Divergence: loss explosion but somehow printed a summary
    if val_bpb > 10 or val_bpb <= 0:
        return ParseResult(
            metrics=TrainingMetrics(val_bpb=val_bpb),
            status=RunStatus.DIVERGE,
            raw_summary=summary,
            num_steps=num_steps,
            depth=depth,
            crash_hint=f"val_bpb={val_bpb:.4f} outside valid range (0, 10]",
        )

    # Timeout heuristic: total wall time > 650 s (5-min budget + generous overhead)
    status = RunStatus.TIMEOUT if total_sec > 650 else RunStatus.SUCCESS

    metrics = TrainingMetrics(
        val_bpb=val_bpb,
        train_loss=0.0,       # not in final summary; live loss logged per-step
        core_score=0.0,       # populated by post-run CORE eval if available
        mfu_pct=mfu_pct,
        peak_vram_gb=vram_mb / 1024.0,
        total_tokens=int(tokens_M * 1_000_000),
        wall_time_sec=wall_time_sec,
    )

    return ParseResult(
        metrics=metrics,
        status=status,
        raw_summary=summary,
        num_steps=num_steps,
        num_params_M=num_params_M,
        depth=depth,
        total_seconds=total_sec,
    )


def parse_training_output_str(text: str) -> ParseResult:
    """Convenience wrapper for callers that already have the stdout string."""
    return parse_training_output(text)
