# solr-metal

`solr-metal` is a Python-first CLI for Kubernetes and OpenShift validation. It focuses on shallow, trustworthy checks first, produces durable run bundles, and is structured to grow without turning into a pile of shell scripts.

The CLI name is `sm`.

## Design Goals

- Strong operator UX with a polished terminal interface
- Typed models and stable run-bundle semantics
- Built on established products instead of bespoke plumbing
- Extensible through builtins, command checks, and Python helpers
- Clean reporting in terminal, JSON, JUnit XML, and static HTML

## Core Stack

- CLI: `typer` + `rich`
- Kubernetes integration: official `kubernetes` Python client
- Models and settings: `pydantic` + `pydantic-settings`
- Definitions: `PyYAML`
- Reports: `junitparser` + `Jinja2`
- Packaging and workflow: `pyproject.toml` + `uv`
- Tests: `pytest`
- Docs: `MkDocs Material`

## Quick Start

```powershell
uv sync --extra dev
uv run sm doctor
uv run sm list tests
uv run sm run smoke
uv run sm run --test kubernetes.nodes.ready
```

## Primary Commands

```text
sm doctor
sm list tests
sm list suites
sm run smoke
sm run --test openshift.clusteroperators.healthy
sm run --test-file .\catalog\examples\custom-route-check.yaml
sm report --run .\runs\<timestamp>
```

## Run Bundle

Each run writes:

- `run.json`
- `summary.json`
- `junit.xml`
- `report.html`
- `artifacts/<test-id>/...`

## Project Layout

- `src/solr_metal`: application package
- `catalog/definitions`: built-in YAML-backed checks
- `catalog/examples`: external example definitions
- `catalog/python`: optional helper scripts
- `docs`: user, architecture, and contributor docs
- `tests`: unit tests

See [docs/index.md](docs/index.md) and [CONTRIBUTING.md](CONTRIBUTING.md).
