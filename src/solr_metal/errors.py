from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorCategory(str, Enum):
    ASSERTION = "assertion"
    DEPENDENCY = "dependency"
    PERMISSION = "permission"
    PARSING = "parsing"
    RUNNER = "runner"
    TIMEOUT = "timeout"


class StructuredError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    category: ErrorCategory
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


def make_error(
    code: str,
    message: str,
    category: ErrorCategory,
    retryable: bool = False,
    details: dict[str, Any] | None = None,
) -> StructuredError:
    return StructuredError(
        code=code,
        message=message,
        category=category,
        retryable=retryable,
        details=details or {},
    )
