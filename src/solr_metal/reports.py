from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape
from junitparser import Error, Failure, JUnitXml, Skipped, TestCase, TestSuite

from solr_metal.console import print_run
from solr_metal.models import RunBundle, Status, Summary, write_json


def write_bundle(run_dir: Path, bundle: RunBundle) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    write_json(run_dir / "run.json", bundle)
    write_json(run_dir / "summary.json", bundle.summary)
    _write_junit(run_dir / "junit.xml", bundle)
    _write_html(run_dir / "report.html", bundle)


def load_bundle(run_dir: Path) -> RunBundle:
    return RunBundle.model_validate_json((run_dir / "run.json").read_text(encoding="utf-8"))


def print_terminal(bundle: RunBundle) -> None:
    print_run(bundle)


def _write_junit(path: Path, bundle: RunBundle) -> None:
    suite = TestSuite("sm")
    suite.tests = bundle.summary.total
    suite.failures = bundle.summary.failed
    suite.errors = bundle.summary.errored + bundle.summary.timed_out
    suite.skipped = bundle.summary.skipped
    for item in bundle.results:
        case = TestCase(name=item.id, classname=item.module, time=item.duration.total_seconds())
        message = item.message or (item.error or {}).get("message", "")
        if item.status == Status.FAIL:
            case.result = [Failure(message)]
        elif item.status in {Status.ERROR, Status.TIMEOUT}:
            case.result = [Error(message)]
        elif item.status == Status.SKIP:
            case.result = [Skipped(message)]
        suite.add_testcase(case)
    xml = JUnitXml()
    xml.add_testsuite(suite)
    xml.write(str(path))


def _write_html(path: Path, bundle: RunBundle) -> None:
    env = Environment(
        loader=PackageLoader("solr_metal", "templates"),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("report.html.j2")
    payload = bundle.model_dump(mode="json")
    payload["summary_cards"] = _summary_cards(bundle.summary)
    path.write_text(template.render(**payload), encoding="utf-8")


def _summary_cards(summary: Summary) -> list[dict[str, str | int]]:
    return [
        {"label": "Pass", "value": summary.passed, "tone": "pass"},
        {"label": "Fail", "value": summary.failed, "tone": "fail"},
        {"label": "Error", "value": summary.errored, "tone": "error"},
        {"label": "Skip", "value": summary.skipped, "tone": "skip"},
        {"label": "Timeout", "value": summary.timed_out, "tone": "timeout"},
    ]
