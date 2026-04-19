# Developer Guide

## Tooling

- `uv` for environment and command execution
- `pytest` for tests
- `ruff` for linting
- `mypy` for type checking
- `MkDocs Material` for docs

## Design Notes

- Use `pydantic` models as the canonical contract between the CLI, runner, and report layer.
- Use `junitparser` and `Jinja2` for reports rather than hand-rolled formats.
- Keep the Kubernetes client initialization centralized.
- Prefer rich terminal rendering over plain text dumps, but keep it script-friendly where possible.
