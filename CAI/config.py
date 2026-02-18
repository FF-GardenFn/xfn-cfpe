"""
Configuration for Constitutional Kernel Experiment v3.

Model IDs from central catalog, constants, and settings.
"""

from enum import Enum
from pathlib import Path


# =============================================================================
# Model Configuration (Jan 2026 - 4.5 Series)
# =============================================================================

class ModelTier(str, Enum):
    """Model capability tiers."""
    FAST = "fast"          # Haiku-class: cheap, fast, for classification
    BALANCED = "balanced"  # Sonnet-class: good balance
    FRONTIER = "frontier"  # Opus-class: highest capability


# Current 4.5 series model IDs
MODELS = {
    ModelTier.FAST: "claude-haiku-4-5-20251001",
    ModelTier.BALANCED: "claude-4-5-sonnet-20260115",
    ModelTier.FRONTIER: "claude-opus-4-5-20251101",
}

# Models to test in experiment (4.5 series)
EXPERIMENT_MODELS = [
    "claude-sonnet-4-5-20250929",  # Sonnet 4.5
    "claude-opus-4-5-20251101",    # Opus 4.5
]

# Classifier model (fast, cheap - Haiku 4.5)
CLASSIFIER_MODEL = "claude-haiku-4-5-20251001"


# =============================================================================
# Experiment Settings
# =============================================================================

# Number of trials per task/condition/model for statistical stability
N_TRIALS = 5  # Increased from 3 for statistical confidence

# 4-condition grid to isolate effects
# 1. baseline     - no constitution, no kernel gate
# 2. cai          - constitution only, no kernel gate
# 3. kernel_only  - no constitution, kernel gate only (isolates kernel effect)
# 4. cai_kernel   - constitution + kernel gate (full thesis test)
CONDITIONS = ["baseline", "cai", "kernel_only", "cai_kernel"]

# API settings
MAX_TOKENS = 1024
CLASSIFIER_MAX_TOKENS = 20

# Retry settings
MAX_RETRIES = 2
RETRY_DELAY = 1.0


# =============================================================================
# Paths
# =============================================================================

BASE_DIR = Path(__file__).parent
RESULTS_DIR = BASE_DIR / "results"
ENV_FILE = BASE_DIR.parent.parent.parent / ".env"
