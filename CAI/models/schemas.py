"""
Core data schemas for tools and validation.
"""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel


class ToolCategory(str, Enum):
    """Tool risk categories for access control."""
    READ = "read"           # Safe: read files, query data
    WRITE = "write"         # Medium: modify files, send messages
    EXECUTE = "execute"     # High: run code, system commands
    PRIVILEGED = "privileged"  # Critical: admin actions, deletions


class ToolDefinition(BaseModel):
    """Schema for a tool that the model can call."""
    name: str
    description: str
    category: ToolCategory
    parameters: dict[str, Any]
    required_params: list[str] = []
    forbidden_patterns: list[str] = []
    requires_justification: bool = False


class ToolCall(BaseModel):
    """A parsed tool call from model output."""
    tool_name: str
    arguments: dict[str, Any]
    justification: Optional[str] = None


class ValidationResult(BaseModel):
    """Result of kernel validation."""
    valid: bool
    violations: list[str] = []
    warnings: list[str] = []


# =============================================================================
# Tool Definitions
# =============================================================================

TOOLS: dict[str, ToolDefinition] = {
    "read_file": ToolDefinition(
        name="read_file",
        description="Read contents of a file",
        category=ToolCategory.READ,
        parameters={"path": "string"},
        required_params=["path"],
        forbidden_patterns=[
            r"^/etc/", r"^/root/", r"\.ssh/",
            r"\.env$", r"passwd", r"shadow",
            r"credentials", r"secret", r"password", r"\.pem$", r"\.key$",
        ],
    ),
    "write_file": ToolDefinition(
        name="write_file",
        description="Write content to a file",
        category=ToolCategory.WRITE,
        parameters={"path": "string", "content": "string"},
        required_params=["path", "content"],
        forbidden_patterns=[r"^/etc/", r"^/root/", r"\.ssh/"],
        requires_justification=True,
    ),
    "execute_command": ToolDefinition(
        name="execute_command",
        description="Execute a shell command",
        category=ToolCategory.EXECUTE,
        parameters={"command": "string"},
        required_params=["command"],
        forbidden_patterns=[
            r"rm\s+-rf", r"sudo", r"chmod\s+777",
            r"curl.*\|\s*(ba)?sh", r"wget.*\|\s*(ba)?sh",
            r"curl.*\|\s*zsh", r"wget.*\|\s*zsh",
            r"mkfs", r"dd\s+if=",
        ],
        requires_justification=True,
    ),
    "send_email": ToolDefinition(
        name="send_email",
        description="Send an email to a recipient",
        category=ToolCategory.WRITE,
        parameters={"to": "string", "subject": "string", "body": "string"},
        required_params=["to", "subject", "body"],
        requires_justification=True,
    ),
    "delete_resource": ToolDefinition(
        name="delete_resource",
        description="Delete a resource by ID",
        category=ToolCategory.PRIVILEGED,
        parameters={"resource_id": "string", "resource_type": "string"},
        required_params=["resource_id", "resource_type"],
        requires_justification=True,
    ),
    "search_web": ToolDefinition(
        name="search_web",
        description="Search the web for information",
        category=ToolCategory.READ,
        parameters={"query": "string"},
        required_params=["query"],
    ),
}
