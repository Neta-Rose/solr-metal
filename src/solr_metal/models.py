from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from solr_metal.durations import format_duration, parse_duration


class Status(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"
    SKIP = "SKIP"
    TIMEOUT = "TIMEOUT"


class RetryPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_attempts: int = 1
    backoff: timedelta = timedelta()

    @field_validator("backoff", mode="before")
    @classmethod
    def _parse_backoff(cls, value: Any) -> timedelta:
        return parse_duration(value)

    @field_serializer("backoff")
    def _serialize_backoff(self, value: timedelta) -> str:
        return format_duration(value)


class Requirements(BaseModel):
    model_config = ConfigDict(extra="forbid")

    binaries: list[str] = Field(default_factory=list)
    cluster_roles: list[str] = Field(default_factory=list)


class FailurePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    collect: list[str] = Field(default_factory=list)


class ArtifactRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    path: str


class TestDefinition(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str = ""
    description: str = ""
    module: str = "core"
    suites: list[str] = Field(default_factory=list)
    kind: str
    timeout: timedelta = timedelta(seconds=60)
    severity: str = "medium"
    tags: list[str] = Field(default_factory=list)
    retries: RetryPolicy = Field(default_factory=RetryPolicy)
    artifacts: list[str] = Field(default_factory=list)
    on_failure: FailurePolicy = Field(default_factory=FailurePolicy)
    requires: Requirements = Field(default_factory=Requirements)
    spec: dict[str, Any] = Field(default_factory=dict)
    source: str | None = None

    @field_validator("timeout", mode="before")
    @classmethod
    def _parse_timeout(cls, value: Any) -> timedelta:
        return parse_duration(value)

    @field_serializer("timeout")
    def _serialize_timeout(self, value: timedelta) -> str:
        return format_duration(value)

    @property
    def timeout_seconds(self) -> float:
        return max(self.timeout.total_seconds(), 1.0)

    def matches_suite(self, name: str) -> bool:
        return name in self.suites


class TestResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    module: str
    kind: str
    status: Status
    started_at: datetime
    finished_at: datetime
    duration: timedelta
    message: str | None = None
    error: dict[str, Any] | None = None
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("duration", mode="before")
    @classmethod
    def _parse_duration(cls, value: Any) -> timedelta:
        return parse_duration(value)

    @field_serializer("started_at", "finished_at")
    def _serialize_datetime(self, value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat()

    @field_serializer("duration")
    def _serialize_duration(self, value: timedelta) -> str:
        return format_duration(value)


class RunMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    generated_at: datetime
    selected_suite: str | None = None

    @field_serializer("generated_at")
    def _serialize_generated_at(self, value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat()


class Summary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int = 0
    passed: int = 0
    failed: int = 0
    errored: int = 0
    skipped: int = 0
    timed_out: int = 0

    @classmethod
    def from_results(cls, results: list[TestResult]) -> "Summary":
        summary = cls(total=len(results))
        for item in results:
            match item.status:
                case Status.PASS:
                    summary.passed += 1
                case Status.FAIL:
                    summary.failed += 1
                case Status.ERROR:
                    summary.errored += 1
                case Status.SKIP:
                    summary.skipped += 1
                case Status.TIMEOUT:
                    summary.timed_out += 1
        return summary


class RunBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metadata: RunMetadata
    results: list[TestResult]
    summary: Summary


def write_json(path: Path, payload: BaseModel | dict[str, Any]) -> None:
    import json

    if isinstance(payload, BaseModel):
        data = payload.model_dump(mode="json")
    else:
        data = payload
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
