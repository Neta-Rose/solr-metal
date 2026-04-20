# Contributing

## Workflow

```powershell
task sync
task lint
task test
task build
task run -- list tests
task run -- run smoke
```

## Principles

- Prefer official clients and mature libraries over homegrown integrations.
- Keep the result model stable: `PASS`, `FAIL`, `ERROR`, `SKIP`, `TIMEOUT`.
- Use `FAIL` for honest negative assertions and `ERROR` for evaluation problems.
- Do not add deep probes unless cleanup and timeout behavior are trustworthy.
- Keep YAML checks simple and explicit.
- Treat the built wheel as the product artifact and validate it directly.

## Adding A Builtin Check

1. Implement the builtin in `src/solr_metal/builtins.py`.
2. Register its definition in `src/solr_metal/registry.py`.
3. Add focused unit tests.
4. Document its scope and prerequisites.

## Adding A YAML Check

1. Add a packaged file under `src/solr_metal/catalog/definitions/smoke` or `src/solr_metal/catalog/definitions/health`.
2. Use `kind: command` or `kind: python`.
3. Declare `timeout`, `requires`, and `retries` explicitly.
4. Validate it with `uv run sm list tests`.

## Release Contract

- The version source of truth is `project.version` in `pyproject.toml`.
- Tags must match the package version: `vX.Y.Z`.
- CI owns building, wheel verification, release creation, and publishing.
