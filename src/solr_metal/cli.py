from __future__ import annotations
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import typer
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from solr_metal.artifacts import ArtifactStore
from solr_metal.builtins import BuiltinRunner
from solr_metal.console import console, render_summary, status_style
from solr_metal.durations import format_duration
from solr_metal.engine import Engine
from solr_metal.kube import load_clients_from
from solr_metal.models import TestDefinition
from solr_metal.registry import Registry, load_file
from solr_metal.reports import load_bundle, print_terminal, write_bundle
from solr_metal.settings import LoadedSettings, load_settings
from solr_metal.versioning import check_latest_version, current_version

app = typer.Typer(
    name="sm",
    help="Bare-metal Kubernetes and OpenShift validation CLI.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
list_app = typer.Typer(help="Inspect suites and tests.")
config_app = typer.Typer(help="Inspect the resolved configuration model.")
app.add_typer(list_app, name="list")
app.add_typer(config_app, name="config")


@dataclass
class AppContext:
    loaded: LoadedSettings


def version_callback(value: bool) -> None:
    if value:
        console.print(f"[accent]solr-metal[/accent] {current_version()}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    config: Path | None = typer.Option(
        None,
        "--config",
        help="Explicit TOML configuration file. Precedence is CLI flags > env vars > config files > defaults.",
    ),
    output_root: Path | None = typer.Option(None, "--output-root", help="Root directory for run bundles."),
    extra_definition_dir: list[Path] | None = typer.Option(
        None,
        "--extra-definition-dir",
        help="Additional definition directory. Repeat the flag to add more than one.",
    ),
    kubeconfig: Path | None = typer.Option(None, "--kubeconfig", help="Explicit kubeconfig path."),
    version_check_enabled: bool | None = typer.Option(
        None,
        "--version-check-enabled/--no-version-check",
        help="Enable or disable automatic update notices.",
    ),
    version_source_type: str | None = typer.Option(
        None,
        "--version-source-type",
        help="Version source type: disabled, pypi-json, simple-api, or static-json.",
    ),
    version_source_url: str | None = typer.Option(
        None,
        "--version-source-url",
        help="Version source URL for simple-api or static-json sources.",
    ),
    version: bool = typer.Option(
        False,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show the installed version and exit.",
    ),
) -> None:
    del version
    ctx.obj = AppContext(
        loaded=load_settings(
            config_path=config,
            cli_overrides={
                "output_root": output_root,
                "extra_definition_dirs": extra_definition_dir,
                "kubeconfig": kubeconfig,
                "version_check_enabled": version_check_enabled,
                "version_source_type": version_source_type,
                "version_source_url": version_source_url,
            },
        )
    )


@app.command("run")
def run_command(
    ctx: typer.Context,
    suite: str | None = typer.Argument(None, help="Suite to run, such as smoke or health."),
    suite_name: str | None = typer.Option(None, "--suite", help="Suite to run."),
    test_id: str | None = typer.Option(None, "--test", help="Run a single test by ID."),
    test_file: Path | None = typer.Option(None, "--test-file", help="External YAML test definition."),
    output_dir: Path | None = typer.Option(None, "--output-dir", help="Run bundle output directory."),
    kubeconfig: Path | None = typer.Option(None, "--kubeconfig", help="Explicit kubeconfig path."),
) -> None:
    app_context = require_context(ctx)
    settings = app_context.loaded.settings
    selected_suite = suite_name or suite
    resolved_output_root = output_dir or settings.output_root
    run_dir = resolved_output_root if output_dir else settings.default_run_dir()
    run_dir.mkdir(parents=True, exist_ok=True)

    registry = Registry.load(settings.extra_definition_dirs)
    if test_file:
        registry.add(load_file(test_file))
    tests = select_tests(registry, selected_suite, test_id)

    console.print(
        Panel.fit(
            f"[title]solr-metal[/title]\n"
            f"[accent]Run directory[/accent]: {run_dir}\n"
            f"[accent]Selection[/accent]: {test_id or selected_suite or 'unknown'}\n"
            f"[accent]Config precedence[/accent]: CLI > env > config files > defaults",
            border_style="accent",
        )
    )

    resolved_kubeconfig = kubeconfig or settings.kubeconfig
    clients = load_clients_from(resolved_kubeconfig) if any(test.kind == "builtin" for test in tests) else None
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
    maybe_notify_update(settings)


@app.command("doctor")
def doctor(ctx: typer.Context) -> None:
    app_context = require_context(ctx)
    settings = app_context.loaded.settings
    checks: list[tuple[str, str, str]] = []

    try:
        load_clients_from(settings.kubeconfig)
        checks.append(("kubeconfig", "ok", str(settings.kubeconfig or "default discovery")))
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

    source_desc = settings.version_source_type
    if settings.version_source_url:
        source_desc = f"{source_desc} ({settings.version_source_url})"
    checks.append(("version-check", "ok" if settings.version_check_enabled else "warn", source_desc))

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Details", overflow="fold")
    for label, status, details in checks:
        style = {"ok": "pass", "warn": "skip", "fail": "fail"}[status]
        table.add_row(label, f"[{style}]{status}[/{style}]", details)
    console.print(table)
    maybe_notify_update(settings)


@app.command("report")
def report(run: Path = typer.Option(..., "--run", help="Run bundle directory.")) -> None:
    bundle = load_bundle(run)
    write_bundle(run, bundle)
    print_terminal(bundle)


@app.command("version")
def version_command(
    ctx: typer.Context,
    check: bool = typer.Option(False, "--check", help="Check whether a newer release is available."),
) -> None:
    app_context = require_context(ctx)
    settings = app_context.loaded.settings
    console.print(f"[accent]solr-metal[/accent] {current_version(settings.distribution_name)}")
    if not check:
        return
    try:
        status = check_latest_version(
            source_type=settings.version_source_type,
            package_name=settings.version_source_package,
            source_url=settings.version_source_url,
            timeout_seconds=settings.version_check_timeout_seconds,
        )
    except Exception as exc:
        console.print(f"[fail]version check failed[/fail] {exc}")
        raise typer.Exit(code=1)
    if status.update_available:
        console.print(
            f"[skip]update available[/skip] current={status.current} latest={status.latest} source={status.source}"
        )
    else:
        console.print(f"[pass]up to date[/pass] current={status.current} source={status.source}")


@list_app.command("tests")
def list_tests(ctx: typer.Context) -> None:
    settings = require_context(ctx).loaded.settings
    registry = Registry.load(settings.extra_definition_dirs)
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
    maybe_notify_update(settings)


@list_app.command("suites")
def list_suites(ctx: typer.Context) -> None:
    settings = require_context(ctx).loaded.settings
    registry = Registry.load(settings.extra_definition_dirs)
    tree = Tree("[accent]Suites[/accent]")
    for suite in ("smoke", "health"):
        branch = tree.add(f"[bold]{suite}[/bold]")
        for test in registry.by_suite(suite):
            branch.add(test.id)
    console.print(tree)
    maybe_notify_update(settings)


@config_app.command("show")
def config_show(ctx: typer.Context) -> None:
    app_context = require_context(ctx)
    payload = app_context.loaded.settings.model_dump(mode="json")
    console.print_json(data=payload)


@config_app.command("paths")
def config_paths(ctx: typer.Context) -> None:
    app_context = require_context(ctx)
    tree = Tree("[accent]Config Files[/accent]")
    for path in app_context.loaded.config_files:
        tree.add(str(path))
    if not app_context.loaded.config_files:
        tree.add("[muted]no config files loaded[/muted]")
    console.print(tree)


def select_tests(registry: Registry, suite_name: str | None, test_id: str | None) -> list[TestDefinition]:
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


def print_result(result: Any) -> None:
    message = result.message or (result.error or {}).get("message", "")
    console.print(
        f"[{status_style(result.status)}]{result.status.value}[/{status_style(result.status)}] "
        f"{result.id} [muted]{message}[/muted]"
    )


def require_context(ctx: typer.Context) -> AppContext:
    if isinstance(ctx.obj, AppContext):
        return ctx.obj
    loaded = load_settings()
    ctx.obj = AppContext(loaded=loaded)
    return ctx.obj


def maybe_notify_update(settings) -> None:
    if not settings.version_check_enabled:
        return
    try:
        status = check_latest_version(
            source_type=settings.version_source_type,
            package_name=settings.version_source_package,
            source_url=settings.version_source_url,
            timeout_seconds=settings.version_check_timeout_seconds,
        )
    except Exception as exc:
        console.print(f"[muted]version check skipped: {exc}[/muted]")
        return
    if status.update_available:
        console.print(
            f"[skip]update available[/skip] current={status.current} latest={status.latest} source={status.source}"
        )


class NullBuiltins:
    def run(self, test: TestDefinition, run_id: str):
        raise RuntimeError("builtin execution requested without initialized Kubernetes clients")
