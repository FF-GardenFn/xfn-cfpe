"""Tests for the InsightEngine — experiment history analysis.

Verifies:
    - Hypothesis family classification (regex → family name)
    - Family attribution (promising / dead_end / neutral / insufficient_data)
    - Pareto frontier computation
    - Safety drift detection and CAI inversion
    - InsightReport summary and next_hypothesis_context
    - Edge cases: empty history, single experiment
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from training_insights.evaluation.checkpoint_eval import CheckpointReport
from training_insights.evaluation.insights import (
    InsightEngine,
    InsightReport,
    classify_hypothesis,
)


# ---------------------------------------------------------------------------
# Hypothesis classification
# ---------------------------------------------------------------------------

class TestClassifyHypothesis:
    @pytest.mark.parametrize("hypothesis,expected", [
        ("increase embedding_lr 0.6 → 0.8", "embedding_lr"),
        ("embedding learning rate from 0.4 to 0.6", "embedding_lr"),
        ("unembedding_lr 0.3 → 0.5", "unembedding_lr"),
        ("unembed lr adjustment", "unembedding_lr"),
        ("matrix_lr reduced to 0.01", "matrix_lr"),
        ("scalar_lr bump", "scalar_lr"),
        ("lower the learning rate", "learning_rate"),
        ("adjust lr by 10%", "learning_rate"),
        ("WINDOW_PATTERN SSSL → SSLL", "window_pattern"),
        ("try sliding window SLSL", "window_pattern"),
        ("batch_size 512 → 1024", "batch_size"),
        ("total_batch doubled", "batch_size"),
        ("increase depth from 8 to 12", "depth"),
        ("add more n_layers", "depth"),
        ("aspect_ratio 0.5 → 0.7", "width"),
        ("increase width of model", "width"),
        ("warmdown ratio 0.5 → 0.3", "lr_schedule"),
        ("longer warmup phase", "lr_schedule"),
        ("weight_decay 0.01 → 0.001", "weight_decay"),
        ("head_dim 64 → 128", "attention_head"),
        ("baseline (no changes)", "baseline"),
        ("something completely unrelated", "other"),
    ])
    def test_classify(self, hypothesis, expected):
        assert classify_hypothesis(hypothesis) == expected

    def test_case_insensitive(self):
        assert classify_hypothesis("EMBEDDING_LR increase") == "embedding_lr"


# ---------------------------------------------------------------------------
# InsightEngine with synthetic results.tsv
# ---------------------------------------------------------------------------

HEADER = "step\tcommit\tval_bpb\tcore\tmfu%\tvram_gb\treward\tstatus\thypothesis"

def _write_tsv(path: Path, rows: list[str]):
    path.write_text(HEADER + "\n" + "\n".join(rows) + "\n")


class TestInsightEngine:
    def test_empty_history(self, tmp_path):
        tsv = tmp_path / "results.tsv"
        tsv.write_text(HEADER + "\n")
        engine = InsightEngine(results_file=tsv)
        report = engine.analyze()
        assert report.n_total == 0

    def test_single_experiment(self, tmp_path):
        tsv = tmp_path / "results.tsv"
        _write_tsv(tsv, [
            "1\tabc1234\t1.0234\t0.248\t42.3\t38.2\t+0.3821\tkeep\tbaseline (no changes)",
        ])
        engine = InsightEngine(results_file=tsv)
        report = engine.analyze()
        assert report.n_total == 1
        assert report.n_kept == 1
        assert report.best_bpb == pytest.approx(1.0234, abs=1e-4)

    def test_family_attribution_promising(self, tmp_path):
        """2 kept embedding_lr experiments → should be classified promising."""
        tsv = tmp_path / "results.tsv"
        _write_tsv(tsv, [
            "1\tabc\t1.0234\t0.248\t42.3\t38.2\t+0.3821\tkeep\tbaseline (no changes)",
            "2\tdef\t1.0198\t0.251\t42.1\t38.2\t+0.3944\tkeep\tembedding_lr 0.6→0.8",
            "3\tghi\t1.0182\t0.254\t42.0\t38.3\t+0.4012\tkeep\tembedding_lr 0.8→0.9",
        ])
        engine = InsightEngine(results_file=tsv, min_experiments_for_verdict=2)
        report = engine.analyze()
        emb_stats = [fs for fs in report.family_stats if fs.family == "embedding_lr"]
        assert len(emb_stats) == 1
        assert emb_stats[0].n_experiments == 2
        assert emb_stats[0].verdict == "promising"

    def test_family_attribution_dead_end(self, tmp_path):
        """2 discarded window_pattern experiments → dead_end."""
        tsv = tmp_path / "results.tsv"
        _write_tsv(tsv, [
            "1\tabc\t1.0234\t0.248\t42.3\t38.2\t+0.3821\tkeep\tbaseline (no changes)",
            "2\tdef\t1.0280\t0.240\t40.1\t39.5\t+0.3500\tdiscard\twindow_pattern SSLL",
            "3\tghi\t1.0310\t0.238\t39.5\t39.8\t+0.3400\tdiscard\twindow_pattern SLSL",
        ])
        engine = InsightEngine(results_file=tsv, min_experiments_for_verdict=2)
        report = engine.analyze()
        wp_stats = [fs for fs in report.family_stats if fs.family == "window_pattern"]
        assert len(wp_stats) == 1
        assert wp_stats[0].verdict == "dead_end"
        assert "window_pattern" in report.dead_ends

    def test_insufficient_data(self, tmp_path):
        """Single experiment in family → insufficient_data."""
        tsv = tmp_path / "results.tsv"
        _write_tsv(tsv, [
            "1\tabc\t1.0234\t0.248\t42.3\t38.2\t+0.3821\tkeep\tbaseline (no changes)",
            "2\tdef\t1.0198\t0.251\t42.1\t38.2\t+0.3944\tkeep\tweight_decay 0.01→0.001",
        ])
        engine = InsightEngine(results_file=tsv, min_experiments_for_verdict=2)
        report = engine.analyze()
        wd_stats = [fs for fs in report.family_stats if fs.family == "weight_decay"]
        assert len(wd_stats) == 1
        assert wd_stats[0].verdict == "insufficient_data"

    def test_pareto_frontier(self, tmp_path):
        """At least one Pareto-optimal point from kept experiments."""
        tsv = tmp_path / "results.tsv"
        _write_tsv(tsv, [
            "1\tabc\t1.0234\t0.248\t42.3\t38.2\t+0.3821\tkeep\tbaseline (no changes)",
            "2\tdef\t1.0198\t0.251\t42.1\t38.2\t+0.3944\tkeep\tembedding_lr 0.6→0.8",
        ])
        engine = InsightEngine(results_file=tsv)
        report = engine.analyze()
        # Should have at least 1 Pareto-optimal point
        pareto_optimal = [p for p in report.pareto_frontier if p.is_pareto_optimal]
        assert len(pareto_optimal) >= 1

    def test_safety_drift_no_inversion(self, tmp_path):
        """No safety penalties → no inversion."""
        tsv = tmp_path / "results.tsv"
        _write_tsv(tsv, [
            "1\tabc\t1.0234\t0.248\t42.3\t38.2\t+0.3821\tkeep\tbaseline (no changes)",
            "2\tdef\t1.0198\t0.251\t42.1\t38.2\t+0.3944\tkeep\tembedding_lr 0.6→0.8",
        ])
        engine = InsightEngine(results_file=tsv)
        report = engine.analyze()
        assert report.safety_drift.inversion_detected is False
        assert report.safety_drift.drift == 0.0

    def test_crashed_experiment_counted(self, tmp_path):
        """val_bpb=0 → crashed count."""
        tsv = tmp_path / "results.tsv"
        _write_tsv(tsv, [
            "1\tabc\t1.0234\t0.248\t42.3\t38.2\t+0.3821\tkeep\tbaseline (no changes)",
            "2\tdef\t0.0000\t0.000\t0.0\t0.0\t+0.0000\tdiscard\tcrashed experiment",
        ])
        engine = InsightEngine(results_file=tsv)
        report = engine.analyze()
        assert report.n_crashed == 1

    def test_nonexistent_file(self, tmp_path):
        engine = InsightEngine(results_file=tmp_path / "nope.tsv")
        report = engine.analyze()
        assert report.n_total == 0


# ---------------------------------------------------------------------------
# InsightReport output formatting
# ---------------------------------------------------------------------------

class TestInsightReportFormatting:
    def test_summary_contains_key_sections(self, tmp_path):
        tsv = tmp_path / "results.tsv"
        _write_tsv(tsv, [
            "1\tabc\t1.0234\t0.248\t42.3\t38.2\t+0.3821\tkeep\tbaseline (no changes)",
            "2\tdef\t1.0198\t0.251\t42.1\t38.2\t+0.3944\tkeep\tembedding_lr 0.6→0.8",
        ])
        engine = InsightEngine(results_file=tsv)
        report = engine.analyze()
        summary = report.summary()
        assert "Family Attribution" in summary
        assert "Promising" in summary
        assert "Dead Ends" in summary
        assert "Safety Drift" in summary

    def test_next_hypothesis_context(self, tmp_path):
        tsv = tmp_path / "results.tsv"
        _write_tsv(tsv, [
            "1\tabc\t1.0234\t0.248\t42.3\t38.2\t+0.3821\tkeep\tbaseline (no changes)",
            "2\tdef\t1.0198\t0.251\t42.1\t38.2\t+0.3944\tkeep\tembedding_lr 0.6→0.8",
        ])
        engine = InsightEngine(results_file=tsv)
        report = engine.analyze()
        ctx = report.next_hypothesis_context()
        assert "Insight Context" in ctx
        assert "Promising" in ctx
        assert "Dead-end" in ctx
        assert "Safety status" in ctx
