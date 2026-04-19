from datetime import datetime, timedelta, timezone

from solr_metal.models import RunBundle, RunMetadata, Status, Summary, TestResult
from solr_metal.reports import write_bundle


def test_write_bundle_creates_expected_files(tmp_path) -> None:
    bundle = RunBundle(
        metadata=RunMetadata(run_id="run-123", generated_at=datetime.now(timezone.utc)),
        results=[
            TestResult(
                id="test.one",
                name="test one",
                module="core",
                kind="builtin",
                status=Status.PASS,
                started_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
                duration=timedelta(seconds=1),
                message="ok",
            )
        ],
        summary=Summary(total=1, passed=1),
    )
    write_bundle(tmp_path, bundle)
    assert (tmp_path / "run.json").exists()
    assert (tmp_path / "summary.json").exists()
    assert (tmp_path / "junit.xml").exists()
    assert (tmp_path / "report.html").exists()
