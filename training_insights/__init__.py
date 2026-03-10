"""
Training Insights
=================
Autonomous training experiment platform that wraps production LLM training
infrastructure with multi-dimensional evaluation methodology.

The training engine measures what the model learned.
The evaluation pipeline measures *how* the model learns.

Public API
----------
    from training_insights.evaluation.checkpoint_eval import (
        CheckpointEvaluator,
        CheckpointReport,
        ExperimentTracker,
        TrainingMetrics,
        ProcessRewards,
        SafetyProfile,
    )
    from training_insights.evaluation.parser import parse_training_output
    from training_insights.evaluation.runner import ExperimentRunner
    from training_insights.evaluation.insights import InsightEngine
"""

__version__ = "0.2.0"
__author__ = "Faycal Farhat"

from training_insights.evaluation.checkpoint_eval import (
    CheckpointEvaluator,
    CheckpointReport,
    ExperimentTracker,
    TrainingMetrics,
    ProcessRewards,
    SafetyProfile,
)

__all__ = [
    "CheckpointEvaluator",
    "CheckpointReport",
    "ExperimentTracker",
    "TrainingMetrics",
    "ProcessRewards",
    "SafetyProfile",
]
