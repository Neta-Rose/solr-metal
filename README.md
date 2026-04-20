# solr-metal

`solr-metal` is a Python-first CLI for Kubernetes and OpenShift validation. It is designed as a releasable product: installable as a wheel, versioned deliberately, validated by CI against built artifacts, and usable in public, private, and air-gapped environments.

The CLI name is `sm`.

## Product Principles

- Built artifacts are the product. Source checkouts are for development.
- The wheel is the install target and the CI truth source.
- One packaging file defines the product contract: name, version, dependencies, and CLI entrypoint.
- Configuration follows clear precedence: CLI flags > environment variables > config files > defaults.
- Release automation owns packaging and publishing.

## Core Stack

- CLI: `typer` + `rich`
- Kubernetes integration: official `kubernetes` Python client
- Models: `pydantic`
- Definitions: `PyYAML`
- Reports: `junitparser` + `Jinja2`
- Packaging: `hatchling`
- Environment + lockfile workflow: `uv`
- Tests: `pytest`
- Docs: `MkDocs Material`

## Install

From source for development:

```powershell
uv sync --extra dev
uv run sm --version
```

From a built wheel:

```powershell
python -m pip install solr_metal-0.1.0-py3-none-any.whl
sm --version
```

## Quick Start

```powershell
uv run sm doctor
uv run sm list tests
uv run sm run smoke
uv run sm run --test kubernetes.nodes.ready
uv run sm version --check
```

## Command Surface

```text
sm doctor
sm version
sm version --check
sm list tests
sm list suites
sm config show
sm config paths
sm run smoke
sm run --test openshift.clusteroperators.healthy
sm run --test-file .\catalog\examples\custom-route-check.yaml
sm report --run .\runs\<timestamp>
```

## Distribution Modes

- Public package index such as PyPI
- Private internal package index
- Air-gapped delivery using prebuilt wheel and wheelhouse bundles

The same wheel artifact is intended to move through every distribution path.

## Release Model

- Update `project.version` in [pyproject.toml](/C:/Users/netaz/Desktop/Projects/Eclipse/solr-metal/pyproject.toml)
- Merge to `main`
- Create a matching `vX.Y.Z` tag
- CI builds, tests, verifies installability from the wheel, creates the GitHub release, and publishes artifacts

See [RELEASING.md](RELEASING.md) and [docs/distribution.md](docs/distribution.md).

A sample config file is provided at [.solr-metal.example.toml](.solr-metal.example.toml).

## Repo Layout

- `src/solr_metal`: application package
- `src/solr_metal/catalog`: packaged builtin catalog resources included in the wheel
- `catalog/examples`: external definition examples
- `tests`: unit tests
- `docs`: product and operator documentation

## Current Constraint

This workspace currently lacks a usable Python interpreter and `uv` on PATH, so runtime verification is blocked in this shell. The repo changes are structured for artifact-first validation once the toolchain is available.
