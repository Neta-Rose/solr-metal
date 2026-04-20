from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from solr_metal.artifacts import ArtifactStore
from solr_metal.builtins import BuiltinRunner
from solr_metal.errors import ErrorCategory, make_error
from solr_metal.models import RunBundle, RunMetadata, Status, Summary, TestDefinition, TestResult


ResultCallback = Callable[[TestResult], None]


class Engine:
    def __init__(
        self,
        builtins: BuiltinRunner,
        artifacts: ArtifactStore,
    ) -> None:
        self.builtins = builtins
        self.artifacts = artifacts

    def run_all(
        self,
        run_id: str,
        tests: list[TestDefinition],
        selected_suite: str | None = None,
        on_result: ResultCallback | None = None,
    ) -> RunBundle:
        results: list[TestResult] = []
        for test in tests:
            result = self.run_one(test, run_id)
            results.append(result)
            if on_result:
                on_result(result)
        return RunBundle(
            metadata=RunMetadata(
                run_id=run_id,
                generated_at=datetime.now(timezone.utc),
                selected_suite=selected_suite,
            ),
            results=results,
            summary=Summary.from_results(results),
        )

    def run_one(self, test: TestDefinition, run_id: str) -> TestResult:
        missing = [binary for binary in test.requires.binaries if shutil.which(binary) is None]
        if missing:
            return self._result(
                test,
                Status.ERROR,
                error=make_error(
                    "REQUIRED_BINARY_MISSING",
                    f"missing required binaries: {', '.join(missing)}",
                    ErrorCategory.DEPENDENCY,
                ).model_dump(mode="json"),
            )

        attempts = max(test.retries.max_attempts, 1)
        last_result: TestResult | None = None
        for attempt in range(1, attempts + 1):
            result = self._run_once(test, run_id)
            result.metadata["attempt"] = str(attempt)
            last_result = result
            if result.status == Status.PASS:
                return result
            retryable = result.status in {Status.ERROR, Status.TIMEOUT, Status.FAIL}
            if result.error:
                retryable = retryable or bool(result.error.get("retryable"))
            if attempt < attempts and retryable:
                time.sleep(test.retries.backoff.total_seconds())
                continue
            return result
        assert last_result is not None
        return last_result

    def _run_once(self, test: TestDefinition, run_id: str) -> TestResult:
        try:
            match test.kind:
                case "builtin":
                    return self.builtins.run(test, run_id)
                case "command":
                    return self._run_command(test)
                case "python":
                    return self._run_python(test)
                case _:
                    return self._result(
                        test,
                        Status.ERROR,
                        error=make_error(
                            "KIND_UNSUPPORTED",
                            f"kind {test.kind!r} is unsupported",
                            ErrorCategory.RUNNER,
                        ).model_dump(mode="json"),
                    )
        except Exception as exc:
            self.artifacts.write_text(test.id, "panic.txt", str(exc))
            return self._result(
                test,
                Status.ERROR,
                error=make_error(
                    "PANIC_RECOVERED",
                    str(exc),
                    ErrorCategory.RUNNER,
                ).model_dump(mode="json"),
            )

    def _run_python(self, test: TestDefinition) -> TestResult:
        module = str(test.spec.get("module", "")).strip()
        entrypoint = str(test.spec.get("entrypoint", "")).strip()
        if module:
            args = [str(item) for item in test.spec.get("args", [])]
            return self._execute_subprocess(
                test,
                [sys.executable, "-m", module, *args],
                cwd=self._spec_path(test.spec.get("cwd")),
                env=self._spec_env(test),
            )
        if not entrypoint:
            return self._result(
                test,
                Status.ERROR,
                error=make_error(
                    "PYTHON_SPEC_INVALID",
                    "spec.module or spec.entrypoint is required",
                    ErrorCategory.RUNNER,
                ).model_dump(mode="json"),
            )
        args = [str(item) for item in test.spec.get("args", [])]
        return self._execute_subprocess(
            test,
            [sys.executable, entrypoint, *args],
            cwd=self._spec_path(test.spec.get("cwd")),
            env=self._spec_env(test),
        )

    def _run_command(self, test: TestDefinition) -> TestResult:
        raw = test.spec.get("command")
        if not isinstance(raw, list) or not raw:
            return self._result(
                test,
                Status.ERROR,
                error=make_error(
                    "COMMAND_SPEC_INVALID",
                    "spec.command must be a non-empty list",
                    ErrorCategory.RUNNER,
                ).model_dump(mode="json"),
            )
        command = [str(part) for part in raw]
        return self._execute_subprocess(
            test,
            command,
            cwd=self._spec_path(test.spec.get("cwd")),
            env=self._spec_env(test),
        )

    def _execute_subprocess(
        self,
        test: TestDefinition,
        command: list[str],
        cwd: Path | None,
        env: dict[str, str] | None,
    ) -> TestResult:
        started_at = datetime.now(timezone.utc)
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=test.timeout_seconds,
                cwd=str(cwd) if cwd else None,
                env=env,
                check=False,
            )
        except FileNotFoundError as exc:
            finished_at = datetime.now(timezone.utc)
            return TestResult(
                id=test.id,
                name=test.name,
                module=test.module,
                kind=test.kind,
                status=Status.ERROR,
                started_at=started_at,
                finished_at=finished_at,
                duration=finished_at - started_at,
                error=make_error(
                    "EXECUTABLE_NOT_FOUND",
                    str(exc),
                    ErrorCategory.DEPENDENCY,
                ).model_dump(mode="json"),
            )
        except subprocess.TimeoutExpired:
            finished_at = datetime.now(timezone.utc)
            return TestResult(
                id=test.id,
                name=test.name,
                module=test.module,
                kind=test.kind,
                status=Status.TIMEOUT,
                started_at=started_at,
                finished_at=finished_at,
                duration=finished_at - started_at,
                error=make_error(
                    "TEST_TIMEOUT",
                    "test exceeded configured timeout",
                    ErrorCategory.TIMEOUT,
                    True,
                ).model_dump(mode="json"),
            )

        artifacts = [
            self.artifacts.write_text(test.id, "stdout.txt", completed.stdout),
            self.artifacts.write_text(test.id, "stderr.txt", completed.stderr),
        ]
        parser_name = str(test.spec.get("parser", "")).lower().strip()
        metadata: dict[str, str] = {"exit_code": str(completed.returncode)}
        if parser_name == "json" and completed.stdout.strip():
            try:
                parsed = json.loads(completed.stdout)
                artifacts.append(self.artifacts.write_json(test.id, "stdout.json", parsed))
            except json.JSONDecodeError as exc:
                finished_at = datetime.now(timezone.utc)
                return TestResult(
                    id=test.id,
                    name=test.name,
                    module=test.module,
                    kind=test.kind,
                    status=Status.ERROR,
                    started_at=started_at,
                    finished_at=finished_at,
                    duration=finished_at - started_at,
                    artifacts=artifacts,
                    error=make_error(
                        "COMMAND_OUTPUT_PARSE_FAILED",
                        str(exc),
                        ErrorCategory.PARSING,
                    ).model_dump(mode="json"),
                )

        finished_at = datetime.now(timezone.utc)
        if completed.returncode == 0:
            return TestResult(
                id=test.id,
                name=test.name,
                module=test.module,
                kind=test.kind,
                status=Status.PASS,
                started_at=started_at,
                finished_at=finished_at,
                duration=finished_at - started_at,
                message="command executed successfully",
                artifacts=artifacts,
                metadata=metadata,
            )

        return TestResult(
            id=test.id,
            name=test.name,
            module=test.module,
            kind=test.kind,
            status=Status.FAIL,
            started_at=started_at,
            finished_at=finished_at,
            duration=finished_at - started_at,
            message=f"command exited with code {completed.returncode}",
            artifacts=artifacts,
            metadata=metadata,
        )

    def _result(self, test: TestDefinition, status: Status, error: dict | None = None) -> TestResult:
        now = datetime.now(timezone.utc)
        return TestResult(
            id=test.id,
            name=test.name,
            module=test.module,
            kind=test.kind,
            status=status,
            started_at=now,
            finished_at=now,
            duration=timedelta(),
            error=error,
        )

    def _spec_path(self, value: object) -> Path | None:
        if not value:
            return None
        return Path(str(value))

    def _spec_env(self, test: TestDefinition) -> dict[str, str] | None:
        raw_env = test.spec.get("env", {})
        if not isinstance(raw_env, dict):
            return None
        env = dict(map(str_pair, raw_env.items()))
        base = dict(os.environ)
        merged = {**base, **env}
        return merged if merged else None


def str_pair(item: tuple[object, object]) -> tuple[str, str]:
    key, value = item
    return str(key), str(value)
