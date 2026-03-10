"""Training Insights evaluation pipeline.

Connects the training engine (BPB, CORE, ChatCORE) with ARENA's
composite reward function and insight extraction layer.

Architecture:
    parser.py       — stdout → TrainingMetrics (crash/OOM/diverge detection)
    checkpoint_eval — TrainingMetrics → CheckpointReport (composite reward)
    runner.py       — closed loop: train → parse → evaluate → log → git
    report.py       — unified markdown artifact per experiment
    insights.py     — experiment history → InsightReport (patterns, Pareto, safety drift)
    behavioral_delta— hidden-state cosine similarity (RL-O-CoV process rewards)
"""
from .checkpoint_eval import (
    CheckpointEvaluator,
    CheckpointReport,
    ExperimentTracker,
    TrainingMetrics,
    ProcessRewards,
    SafetyProfile,
)
from .parser import parse_training_output, ParseResult, RunStatus
from .runner import ExperimentRunner
from .report import ExperimentReportWriter
from .insights import InsightEngine, InsightReport, classify_hypothesis

__all__ = [
    # Core data models
    "TrainingMetrics",
    "ProcessRewards",
    "SafetyProfile",
    "CheckpointReport",
    # Evaluator + tracker
    "CheckpointEvaluator",
    "ExperimentTracker",
    # Parser
    "parse_training_output",
    "ParseResult",
    "RunStatus",
    # Runner (closed loop)
    "ExperimentRunner",
    # Report writer
    "ExperimentReportWriter",
    # Insight extraction
    "InsightEngine",
    "InsightReport",
    "classify_hypothesis",
]
