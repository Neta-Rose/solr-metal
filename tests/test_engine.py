import sys
from pathlib import Path

from solr_metal.artifacts import ArtifactStore
from solr_metal.engine import Engine
from solr_metal.models import Status, TestDefinition


class DummyBuiltins:
    def run(self, test: TestDefinition, run_id: str):
        raise AssertionError("not used in command tests")


def test_run_command_pass_captures_artifacts(tmp_path: Path) -> None:
    engine = Engine(builtins=DummyBuiltins(), artifacts=ArtifactStore(tmp_path))
    test = TestDefinition(
        id="command.pass",
        name="command pass",
        module="core",
        kind="command",
        timeout="5s",
        spec={"command": [sys.executable, "-c", "print('hello')"]},
    )
    result = engine.run_one(test, "run-123")
    assert result.status == Status.PASS
    assert len(result.artifacts) >= 2


def test_missing_binary_is_error(tmp_path: Path) -> None:
    engine = Engine(builtins=DummyBuiltins(), artifacts=ArtifactStore(tmp_path))
    test = TestDefinition(
        id="command.missing",
        name="command missing",
        module="core",
        kind="command",
        timeout="5s",
        requires={"binaries": ["definitely-not-a-real-binary-xyz"]},
        spec={"command": ["echo", "hello"]},
    )
    result = engine.run_one(test, "run-123")
    assert result.status == Status.ERROR
