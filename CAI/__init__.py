"""
Constitutional Kernel Experiment

Tests the hypothesis that external enforcement via a constitutional kernel
outperforms self-critique for AI alignment.
"""

from .config import EXPERIMENT_MODELS, CLASSIFIER_MODEL
from .models import ToolCall, ValidationResult, TestTask, TrialResult
from .kernel import ConstitutionalKernel
from .classifier import IntentClassifier, Intent
from .experiment import ExperimentRunner, TASKS
from .analysis import analyze_results, display_results

__version__ = "2.0.0"

__all__ = [
    "EXPERIMENT_MODELS",
    "CLASSIFIER_MODEL",
    "ToolCall",
    "ValidationResult",
    "TestTask",
    "TrialResult",
    "ConstitutionalKernel",
    "IntentClassifier",
    "Intent",
    "ExperimentRunner",
    "TASKS",
    "analyze_results",
    "display_results",
]
