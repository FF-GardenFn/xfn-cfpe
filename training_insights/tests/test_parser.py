"""Tests for the training output parser.

Verifies:
    - Successful parse of standard summary block → TrainingMetrics
    - Crash detection (traceback, OOM, FAIL signal)
    - Divergence detection (val_bpb outside [0, 10])
    - Empty / missing log → EMPTY status
    - Timeout detection (> 650s total wall time)
    - VRAM conversion (MB → GB)
    - Token conversion (M → int)
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from training_insights.evaluation.parser import (
    ParseResult,
    RunStatus,
    parse_training_output,
)


# ---------------------------------------------------------------------------
# Fixtures: synthetic training outputs
# ---------------------------------------------------------------------------

GOOD_OUTPUT = """\
Training started...
step 100 | loss 2.345 | lr 0.0006
step 200 | loss 1.987 | lr 0.0008
step 953 | loss 1.542 | lr 0.0003
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
"""

OOM_OUTPUT = """\
step 100 | loss 2.345
CUDA error: out of memory
"""

TRACEBACK_OUTPUT = """\
step 100 | loss 2.345
Traceback (most recent call last):
  File "quick_train.py", line 42, in <module>
    model.forward(batch)
RuntimeError: shape mismatch
"""

FAIL_OUTPUT = """\
step 100 | loss 2.345
step 200 | loss 987.123
FAIL
"""

DIVERGE_OUTPUT = """\
step 100 | loss 999.0
---
val_bpb:          15.2340
training_seconds: 120.0
total_seconds:    130.0
peak_vram_mb:     30000.0
mfu_percent:      25.00
total_tokens_M:   200.0
num_steps:        100
num_params_M:     50.3
depth:            8
"""

TIMEOUT_OUTPUT = """\
step 100 | loss 2.345
---
val_bpb:          1.0100
training_seconds: 580.0
total_seconds:    700.0
peak_vram_mb:     40000.0
mfu_percent:      35.00
total_tokens_M:   499.6
num_steps:        953
num_params_M:     50.3
depth:            8
"""


# ---------------------------------------------------------------------------
# Tests: successful parsing
# ---------------------------------------------------------------------------

class TestSuccessfulParse:
    def test_parse_from_string(self):
        result = parse_training_output(GOOD_OUTPUT)
        assert result.status == RunStatus.SUCCESS
        assert result.metrics.val_bpb == pytest.approx(0.9979, abs=1e-4)

    def test_parse_from_file(self, tmp_path):
        log_file = tmp_path / "run.log"
        log_file.write_text(GOOD_OUTPUT)
        result = parse_training_output(log_file)
        assert result.status == RunStatus.SUCCESS
        assert result.metrics.val_bpb == pytest.approx(0.9979, abs=1e-4)

    def test_wall_time(self):
        result = parse_training_output(GOOD_OUTPUT)
        assert result.metrics.wall_time_sec == pytest.approx(300.1, abs=0.1)

    def test_vram_converted_to_gb(self):
        result = parse_training_output(GOOD_OUTPUT)
        assert result.metrics.peak_vram_gb == pytest.approx(45060.2 / 1024.0, abs=0.1)

    def test_mfu(self):
        result = parse_training_output(GOOD_OUTPUT)
        assert result.metrics.mfu_pct == pytest.approx(39.80, abs=0.01)

    def test_tokens_converted(self):
        result = parse_training_output(GOOD_OUTPUT)
        assert result.metrics.total_tokens == 499_600_000

    def test_num_steps(self):
        result = parse_training_output(GOOD_OUTPUT)
        assert result.num_steps == 953

    def test_depth(self):
        result = parse_training_output(GOOD_OUTPUT)
        assert result.depth == 8

    def test_num_params(self):
        result = parse_training_output(GOOD_OUTPUT)
        assert result.num_params_M == pytest.approx(50.3, abs=0.1)

    def test_raw_summary_populated(self):
        result = parse_training_output(GOOD_OUTPUT)
        assert "val_bpb" in result.raw_summary
        assert "peak_vram_mb" in result.raw_summary


# ---------------------------------------------------------------------------
# Tests: crash detection
# ---------------------------------------------------------------------------

class TestCrashDetection:
    def test_oom(self):
        result = parse_training_output(OOM_OUTPUT)
        assert result.status == RunStatus.OOM
        assert result.metrics.val_bpb == 0.0

    def test_traceback(self):
        result = parse_training_output(TRACEBACK_OUTPUT)
        assert result.status == RunStatus.CRASH
        assert "Traceback" in result.crash_hint or "shape mismatch" in result.crash_hint

    def test_fail_signal(self):
        result = parse_training_output(FAIL_OUTPUT)
        assert result.status == RunStatus.CRASH
        assert "FAIL" in result.crash_hint

    def test_empty_string(self):
        """No summary block, no crash → treated as crash."""
        result = parse_training_output("some random output\nno summary here\n")
        assert result.status == RunStatus.CRASH

    def test_empty_file(self, tmp_path):
        log_file = tmp_path / "empty.log"
        log_file.write_text("")
        result = parse_training_output(log_file)
        assert result.status == RunStatus.EMPTY

    def test_missing_file(self, tmp_path):
        result = parse_training_output(tmp_path / "nonexistent.log")
        assert result.status == RunStatus.EMPTY


# ---------------------------------------------------------------------------
# Tests: divergence and timeout
# ---------------------------------------------------------------------------

class TestDivergenceAndTimeout:
    def test_diverge_high_bpb(self):
        result = parse_training_output(DIVERGE_OUTPUT)
        assert result.status == RunStatus.DIVERGE
        assert result.metrics.val_bpb > 10

    def test_timeout(self):
        result = parse_training_output(TIMEOUT_OUTPUT)
        assert result.status == RunStatus.TIMEOUT
        # Metrics should still be populated
        assert result.metrics.val_bpb == pytest.approx(1.01, abs=0.001)

    def test_diverge_negative_bpb(self):
        """val_bpb=-1 → diverge."""
        text = """\
---
val_bpb:          -1.0000
training_seconds: 100.0
total_seconds:    120.0
peak_vram_mb:     30000.0
mfu_percent:      30.00
total_tokens_M:   100.0
num_steps:        100
num_params_M:     50.3
depth:            8
"""
        result = parse_training_output(text)
        assert result.status == RunStatus.DIVERGE
