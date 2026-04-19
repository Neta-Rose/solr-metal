from __future__ import annotations

import shutil
from pathlib import Path

import typer
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from solr_metal import __version__
from solr_metal.artifacts import ArtifactStore
from solr_metal.builtins import BuiltinRunner
from solr_metal.console import console, render_summary, status_style
from solr_metal.durations import format_duration
from solr_metal.engine import Engine
from solr_metal.kube import load_clients
from solr_metal.models import TestDefinition
from solr_metal.registry import Registry, load_file
from solr_metal.reports import load_bundle, print_terminal, write_bundle
from solr_metal.settings import Settings

app = typer.Typer(
    name="sm",
    help="Bare-metal Kubernetes and OpenShift validation CLI.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
list_app = typer.Typer(help="Inspect suites and tests.")
app.add_typer(list_app, name="list")


def version_callback(value: bool) -> None:
    if value:
        console.print(f"[accent]solr-metal[/accent] {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show the installed version and exit.",
    ),
) -> None:
    return None


@app.command("run")
def run_command(
    suite: str | None = typer.Argument(None, help="Suite to run, such as smoke or health."),
    suite_name: str | None = typer.Option(None, "--suite", help="Suite to run."),
    test_id: str | None = typer.Option(None, "--test", help="Run a single test by ID."),
    test_file: Path | None = typer.Option(None, "--test-file", help="External YAML test definition."),
    output_dir: Path | None = typer.Option(None, "--output-dir", help="Run bundle output directory."),
) -> None:
    settings = Settings()
    selected_suite = suite_name or suite
    run_dir = output_dir or settings.default_run_dir()
    run_dir.mkdir(parents=True, exist_ok=True)

    registry = Registry.load(settings.definitions_dir)
    if test_file:
        registry.add(load_file(test_file))
    tests = select_tests(registry, selected_suite, test_id)

    console.print(
        Panel.fit(
            f"[title]solr-metal[/title]\n[accent]Run directory[/accent]: {run_dir}\n"
            f"[accent]Selection[/accent]: {test_id or selected_suite or 'unknown'}",
            border_style="accent",
        )
    )

    clients = load_clients() if any(test.kind == "builtin" for test in tests) else None
    engine = Engine(
        builtins=BuiltinRunner(clients=clients, settings=settings, artifacts=ArtifactStore(run_dir))
        if clients
        else NullBuiltins(),
        artifacts=ArtifactStore(run_dir),
    )
    bundle = engine.run_all(run_id=run_dir.name, tests=tests, selected_suite=selected_suite, on_result=print_result)
    write_bundle(run_dir, bundle)
    console.print(render_summary(bundle.summary, bundle.metadata.run_id))
    console.print(f"[muted]Artifacts written to[/muted] {run_dir}")


@list_app.command("tests")
def list_tests() -> None:
    settings = Settings()
    registry = Registry.load(settings.definitions_dir)
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("ID")
    table.add_column("Module")
    table.add_column("Kind")
    table.add_column("Timeout")
    table.add_column("Suites")
    table.add_column("Description", overflow="fold")
    for test in registry.all():
        table.add_row(
            test.id,
            test.module,
            test.kind,
            format_duration(test.timeout),
            ",".join(test.suites),
            test.description,
        )
    console.print(table)


@list_app.command("suites")
def list_suites() -> None:
    settings = Settings()
    registry = Registry.load(settings.definitions_dir)
    tree = Tree("[accent]Suites[/accent]")
    for suite in ("smoke", "health"):
        branch = tree.add(f"[bold]{suite}[/bold]")
        for test in registry.by_suite(suite):
            branch.add(test.id)
    console.print(tree)


@app.command("doctor")
def doctor() -> None:
    settings = Settings()
    checks: list[tuple[str, str, str]] = []

    try:
        load_clients()
        checks.append(("kubeconfig", "ok", "loaded Kubernetes client configuration"))
    except Exception as exc:
        checks.append(("kubeconfig", "fail", str(exc)))

    python_path = shutil.which("python") or "active interpreter"
    checks.append(("python", "ok", python_path))

    oc_path = shutil.which("oc")
    checks.append(("oc", "ok" if oc_path else "warn", oc_path or "not found in PATH"))

    settings.output_root.mkdir(parents=True, exist_ok=True)
    probe = settings.output_root / ".doctor.tmp"
    probe.write_text("ok", encoding="utf-8")
    probe.unlink(missing_ok=True)
    checks.append(("output", "ok", str(settings.output_root)))

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Details", overflow="fold")
    for label, status, details in checks:
        style = {"ok": "pass", "warn": "skip", "fail": "fail"}[status]
        table.add_row(label, f"[{style}]{status}[/{style}]", details)
    console.print(table)


@app.command("report")
def report(run: Path = typer.Option(..., "--run", help="Run bundle directory.")) -> None:
    bundle = load_bundle(run)
    write_bundle(run, bundle)
    print_terminal(bundle)


def select_tests(registry: Registry, suite_name: str | None, test_id: str | None):
    if test_id:
        test = registry.get(test_id)
        if test is None:
            raise typer.BadParameter(f"unknown test {test_id!r}")
        return [test]
    if suite_name:
        tests = registry.by_suite(suite_name)
        if not tests:
            raise typer.BadParameter(f"suite {suite_name!r} is empty or undefined")
        return tests
    raise typer.BadParameter("provide a suite argument or --test")


def print_result(result) -> None:
    message = result.message or (result.error or {}).get("message", "")
    console.print(
        f"[{status_style(result.status)}]{result.status.value}[/{status_style(result.status)}] "
        f"{result.id} [muted]{message}[/muted]"
    )


class NullBuiltins:
    def run(self, test: TestDefinition, run_id: str):
        raise RuntimeError("builtin execution requested without initialized Kubernetes clients")
