# Contributing

## Workflow

```powershell
task sync
task lint
task test
task run -- list tests
task run -- run smoke
```

## Principles

- Prefer official clients and mature libraries over homegrown integrations.
- Keep the result model stable: `PASS`, `FAIL`, `ERROR`, `SKIP`, `TIMEOUT`.
- Use `FAIL` for honest negative assertions and `ERROR` for evaluation problems.
- Do not add deep probes unless cleanup and timeout behavior are trustworthy.
- Keep YAML checks simple and explicit.

## Adding A Builtin Check

1. Implement the builtin in `src/solr_metal/builtins.py`.
2. Register its definition in `src/solr_metal/registry.py`.
3. Add focused unit tests.
4. Document its scope and prerequisites.

## Adding A YAML Check

1. Add a file under `catalog/definitions/smoke` or `catalog/definitions/health`.
2. Use `kind: command` or `kind: python`.
3. Declare `timeout`, `requires`, and `retries` explicitly.
4. Validate it with `uv run sm list tests`.
