"""
Test task definitions.
"""

from dataclasses import dataclass
from enum import Enum


class TaskCategory(str, Enum):
    """Task categories by expected behavior."""
    BENIGN = "benign"
    BOUNDARY = "boundary"
    ADVERSARIAL = "adversarial"


@dataclass
class TestTask:
    """A test task for the experiment."""
    id: str
    prompt: str
    category: TaskCategory
    expected_tools: list[str]
    is_adversarial: bool = False
    allow_refusal: bool = False
    description: str = ""

    def __post_init__(self):
        if self.category == TaskCategory.ADVERSARIAL:
            self.is_adversarial = True
            self.allow_refusal = True
