from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.theme import Theme

from solr_metal.durations import format_duration
from solr_metal.models import RunBundle, Status, Summary, TestResult


THEME = Theme(
    {
        "pass": "bold green",
        "fail": "bold red",
        "error": "bold bright_magenta",
        "skip": "bold yellow",
        "timeout": "bold magenta",
        "muted": "grey66",
        "accent": "bold cyan",
        "title": "bold white on dark_green",
    }
)

console = Console(theme=THEME)


def status_style(status: Status) -> str:
    return {
        Status.PASS: "pass",
        Status.FAIL: "fail",
        Status.ERROR: "error",
        Status.SKIP: "skip",
        Status.TIMEOUT: "timeout",
    }[status]


def render_summary(summary: Summary, run_id: str) -> Panel:
    body = (
        f"[accent]Run[/accent]: {run_id}\n"
        f"[pass]PASS[/pass] {summary.passed}    "
        f"[fail]FAIL[/fail] {summary.failed}    "
        f"[error]ERROR[/error] {summary.errored}    "
        f"[skip]SKIP[/skip] {summary.skipped}    "
        f"[timeout]TIMEOUT[/timeout] {summary.timed_out}\n"
        f"[muted]Total[/muted]: {summary.total}"
    )
    return Panel(body, title="solr-metal", border_style="accent")


def render_result_table(results: list[TestResult]) -> Table:
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Status", style="bold")
    table.add_column("ID", style="white")
    table.add_column("Module", style="muted")
    table.add_column("Duration", justify="right")
    table.add_column("Message", overflow="fold")
    for item in results:
        message = item.message or (item.error or {}).get("message", "")
        table.add_row(
            f"[{status_style(item.status)}]{item.status.value}[/{status_style(item.status)}]",
            item.id,
            item.module,
            format_duration(item.duration),
            message,
        )
    return table


def print_run(bundle: RunBundle) -> None:
    console.print(render_summary(bundle.summary, bundle.metadata.run_id))
    console.print(render_result_table(bundle.results))
